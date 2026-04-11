"""Performance indexes, cognitive schema (insight + report), materialized views.

Revision ID: 0008
Revises: 0007
Created: 2026-03-22

This migration creates:
  - Additional performance indexes on telemetry and governance tables
  - cognitive schema with insight and report tables
  - Materialized views: mv_fleet_health_live, mv_llm_accuracy_daily
"""

# pylint: disable=invalid-name,no-member
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TELEMETRY = "telemetry"
_GOVERNANCE = "governance"
_COGNITIVE = "cognitive"


def upgrade() -> None:
    # ── Performance indexes ────────────────────────────────────────────

    # BRIN on collected_at only — BRIN requires physical correlation between
    # column value and disk order.  host_id / metric_name are random; only
    # collected_at is sequential (RANGE-partitioned time-series table).
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS idx_metric_point_collected_brin "
            f"ON {_TELEMETRY}.metric_point "
            f"USING BRIN (collected_at)"
        )
    )

    # NOTE: correlation lookup index on governance.audit_event(correlation_id)
    # already exists as ix_audit_event_correlation from migration 0007.
    # Do NOT create a duplicate.

    # Composite index for HITL queue ordering
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS idx_hitl_item_status_priority "
            f"ON {_GOVERNANCE}.hitl_item (status, priority, created_at)"
        )
    )

    # Partial index on active insights (created after the cognitive table below)
    # — deferred to after table creation

    # LLM call log lookups by model + time
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS idx_llm_call_model_time "
            f"ON {_TELEMETRY}.llm_call_log (model_id, called_at DESC)"
        )
    )

    # ── cognitive schema ───────────────────────────────────────────────
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {_COGNITIVE}"))

    # -- cognitive.insight -----------------------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE {_COGNITIVE}.insight (
                insight_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                insight_type      TEXT,
                severity          TEXT,
                category          TEXT,
                entity_type       TEXT,
                entity_id         UUID,
                title             TEXT,
                explanation       TEXT,
                confidence        DOUBLE PRECISION,
                risk_class        TEXT,
                status            TEXT NOT NULL DEFAULT 'active',
                correlation_id    UUID,
                remediation_plan  JSONB,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                acknowledged_at   TIMESTAMPTZ,
                acknowledged_by   TEXT,
                dismissed_at      TIMESTAMPTZ,
                dismissed_reason  TEXT
            )
        """)
    )

    # Partial index on active insights
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS idx_insight_active "
            f"ON {_COGNITIVE}.insight (created_at DESC) "
            f"WHERE status = 'active'"
        )
    )

    # -- cognitive.report ------------------------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE {_COGNITIVE}.report (
                report_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                report_type       TEXT,
                title             TEXT,
                content_markdown  TEXT,
                data_snapshot     JSONB,
                generated_by      TEXT,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    )

    # ── Materialized views ─────────────────────────────────────────────

    op.execute(
        sa.text(f"""
            CREATE MATERIALIZED VIEW {_COGNITIVE}.mv_fleet_health_live AS
            SELECT
                h.host_id,
                h.hostname,
                COUNT(mp.point_id)                             AS metric_count,
                MAX(mp.collected_at)                           AS last_metric_at,
                CASE
                    WHEN MAX(mp.collected_at) > now() - INTERVAL '5 minutes'
                    THEN 'healthy'
                    WHEN MAX(mp.collected_at) > now() - INTERVAL '15 minutes'
                    THEN 'degraded'
                    ELSE 'stale'
                END                                            AS health_status
            FROM registry.host h
            LEFT JOIN {_TELEMETRY}.metric_point mp ON mp.host_id = h.host_id
            GROUP BY h.host_id, h.hostname
        """)
    )

    # Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY
    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_fleet_health_host "
            f"ON {_COGNITIVE}.mv_fleet_health_live (host_id)"
        )
    )

    op.execute(
        sa.text(f"""
            CREATE MATERIALIZED VIEW {_COGNITIVE}.mv_llm_accuracy_daily AS
            SELECT
                DATE(f.created_at)                             AS day,
                COUNT(*)                                       AS total_feedback,
                COUNT(*) FILTER (WHERE f.agreement = true)     AS agreed,
                COUNT(*) FILTER (WHERE f.agreement = false)    AS disagreed,
                CASE
                    WHEN COUNT(*) FILTER (WHERE f.agreement IS NOT NULL) > 0
                    THEN ROUND(
                        COUNT(*) FILTER (WHERE f.agreement = true)::numeric
                        / COUNT(*) FILTER (WHERE f.agreement IS NOT NULL)::numeric, 4
                    )
                    ELSE NULL
                END                                            AS accuracy_rate
            FROM {_GOVERNANCE}.hitl_feedback f
            GROUP BY DATE(f.created_at)
            ORDER BY day DESC
        """)
    )

    # Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY
    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_llm_accuracy_day "
            f"ON {_COGNITIVE}.mv_llm_accuracy_daily (day)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP MATERIALIZED VIEW IF EXISTS {_COGNITIVE}.mv_llm_accuracy_daily"))
    op.execute(sa.text(f"DROP MATERIALIZED VIEW IF EXISTS {_COGNITIVE}.mv_fleet_health_live"))

    op.execute(sa.text(f"DROP TABLE IF EXISTS {_COGNITIVE}.report CASCADE"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_COGNITIVE}.insight CASCADE"))

    op.execute(sa.text(f"DROP INDEX IF EXISTS {_TELEMETRY}.idx_metric_point_collected_brin"))
    op.execute(sa.text(f"DROP INDEX IF EXISTS {_GOVERNANCE}.idx_hitl_item_status_priority"))
    op.execute(sa.text(f"DROP INDEX IF EXISTS {_TELEMETRY}.idx_llm_call_model_time"))

    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {_COGNITIVE}"))
