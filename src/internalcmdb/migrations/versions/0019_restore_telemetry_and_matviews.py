"""Restore telemetry tables and cognitive materialized views if missing.

Revision ID: 0019
Revises: 0018
Created: 2026-07-05

Production lost the telemetry schema and two cognitive materialized views
(manually dropped after migrations 0007/0008/0010 had run). This migration
recreates them idempotently so a healthy database is a no-op.

DDL is copied verbatim from:
  - 0007_hitl_and_telemetry_schema.py (metric_point, llm_call_log)
  - 0010_slo_framework.py (slo_definition, slo_measurement)
  - 0008_indexes_and_views.py (mv_fleet_health_live, mv_llm_accuracy_daily)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TELEMETRY = "telemetry"
_COGNITIVE = "cognitive"
_GOVERNANCE = "governance"


def _matview_exists(bind: sa.engine.Connection, schema: str, name: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM pg_matviews"
                "  WHERE schemaname = :schema AND matviewname = :name"
                ")"
            ),
            {"schema": schema, "name": name},
        ).scalar()
    )


def upgrade() -> None:
    bind = op.get_bind()

    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {_TELEMETRY}"))

    # ── metric_point (from 0007) ───────────────────────────────────────
    op.execute(
        sa.text(f"""
            CREATE TABLE IF NOT EXISTS {_TELEMETRY}.metric_point (
                point_id      BIGSERIAL,
                host_id       UUID,
                metric_name   TEXT NOT NULL,
                metric_value  DOUBLE PRECISION NOT NULL,
                labels_jsonb  JSONB,
                collected_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (collected_at, point_id)
            ) PARTITION BY RANGE (collected_at)
        """)
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_metric_point_host "
            f"ON {_TELEMETRY}.metric_point (host_id, collected_at DESC)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_metric_point_name "
            f"ON {_TELEMETRY}.metric_point (metric_name, collected_at DESC)"
        )
    )
    now = datetime.now(tz=UTC)
    for month_offset in (0, 1):
        m = now.month + month_offset
        y = now.year
        if m > 12:  # noqa: PLR2004
            m -= 12
            y += 1
        p_start = f"{y}-{m:02d}-01"
        p_end = f"{y + 1}-01-01" if m == 12 else f"{y}-{m + 1:02d}-01"  # noqa: PLR2004
        part_name = f"metric_point_{y}_{m:02d}"
        op.execute(
            sa.text(
                f"CREATE TABLE IF NOT EXISTS {_TELEMETRY}.{part_name} "
                f"PARTITION OF {_TELEMETRY}.metric_point "
                f"FOR VALUES FROM ('{p_start}') TO ('{p_end}')"
            )
        )

    # ── llm_call_log (from 0007) ───────────────────────────────────────
    op.execute(
        sa.text(f"""
            CREATE TABLE IF NOT EXISTS {_TELEMETRY}.llm_call_log (
                call_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                correlation_id  UUID,
                model_id        TEXT,
                endpoint        TEXT,
                input_tokens    INTEGER,
                output_tokens   INTEGER,
                latency_ms      INTEGER,
                status          TEXT,
                guard_input     JSONB,
                guard_output    JSONB,
                error_detail    TEXT,
                called_at       TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_llm_call_log_called "
            f"ON {_TELEMETRY}.llm_call_log (called_at DESC)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_llm_call_log_model "
            f"ON {_TELEMETRY}.llm_call_log (model_id)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_llm_call_log_correlation "
            f"ON {_TELEMETRY}.llm_call_log (correlation_id)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_llm_call_log_status "
            f"ON {_TELEMETRY}.llm_call_log (status)"
        )
    )

    # ── slo_definition + slo_measurement (from 0010) ───────────────────
    op.execute(
        sa.text(f"""
            CREATE TABLE IF NOT EXISTS {_TELEMETRY}.slo_definition (
                slo_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                service_id      UUID,
                sli_type        TEXT NOT NULL,
                target          DOUBLE PRECISION NOT NULL
                                    CHECK (target > 0.0 AND target <= 1.0),
                window_days     INTEGER NOT NULL DEFAULT 30
                                    CHECK (window_days >= 1 AND window_days <= 365),
                burn_rate_fast  DOUBLE PRECISION NOT NULL DEFAULT 14.4,
                burn_rate_slow  DOUBLE PRECISION NOT NULL DEFAULT 1.0,
                is_active       BOOLEAN NOT NULL DEFAULT true,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS idx_slo_def_service "
            f"ON {_TELEMETRY}.slo_definition (service_id)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS idx_slo_def_active "
            f"ON {_TELEMETRY}.slo_definition (is_active) WHERE is_active = true"
        )
    )
    op.execute(
        sa.text(f"""
            CREATE TABLE IF NOT EXISTS {_TELEMETRY}.slo_measurement (
                measurement_id  BIGSERIAL,
                slo_id          UUID NOT NULL,
                good_events     BIGINT NOT NULL DEFAULT 0,
                total_events    BIGINT NOT NULL DEFAULT 0,
                measured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (measured_at, measurement_id)
            ) PARTITION BY RANGE (measured_at)
        """)
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS idx_slo_meas_slo_id "
            f"ON {_TELEMETRY}.slo_measurement (slo_id, measured_at DESC)"
        )
    )
    for month_offset in (0, 1):
        m = now.month + month_offset
        y = now.year
        if m > 12:  # noqa: PLR2004
            m -= 12
            y += 1
        p_start = f"{y}-{m:02d}-01"
        p_end = f"{y + 1}-01-01" if m == 12 else f"{y}-{m + 1:02d}-01"  # noqa: PLR2004
        part_name = f"slo_measurement_{y}_{m:02d}"
        op.execute(
            sa.text(
                f"CREATE TABLE IF NOT EXISTS {_TELEMETRY}.{part_name} "
                f"PARTITION OF {_TELEMETRY}.slo_measurement "
                f"FOR VALUES FROM ('{p_start}') TO ('{p_end}')"
            )
        )

    # ── Materialized views (from 0008) ─────────────────────────────────
    if not _matview_exists(bind, _COGNITIVE, "mv_fleet_health_live"):
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
        op.execute(
            sa.text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_fleet_health_host "
                f"ON {_COGNITIVE}.mv_fleet_health_live (host_id)"
            )
        )

    if not _matview_exists(bind, _COGNITIVE, "mv_llm_accuracy_daily"):
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
        op.execute(
            sa.text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_llm_accuracy_day "
                f"ON {_COGNITIVE}.mv_llm_accuracy_daily (day)"
            )
        )


def downgrade() -> None:
    # Intentional no-op: objects are owned by migrations 0007/0008/0010.
    pass
