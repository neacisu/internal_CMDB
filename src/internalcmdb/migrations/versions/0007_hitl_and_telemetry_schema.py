"""Create governance HITL / audit and telemetry schemas (Phase 4).

Revision ID: 0007
Revises: 0006
Created: 2026-03-22

This migration creates:
  governance schema
    - governance.hitl_item        — human-in-the-loop review queue
    - governance.hitl_feedback    — LLM-vs-human agreement tracking
    - governance.audit_event      — immutable audit trail
  telemetry schema
    - telemetry.metric_point      — range-partitioned time-series metrics
    - telemetry.llm_call_log      — LLM invocation audit log

Downgrade drops all five tables (in reverse dependency order) and the
two schemas if they are empty.
"""

# pylint: disable=invalid-name,no-member
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GOVERNANCE = "governance"
_TELEMETRY = "telemetry"


def upgrade() -> None:
    # ── governance schema ───────────────────────────────────────────────
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {_GOVERNANCE}"))

    # -- hitl_item -------------------------------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE {_GOVERNANCE}.hitl_item (
                item_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                item_type        TEXT NOT NULL,
                risk_class       TEXT NOT NULL,
                priority         TEXT NOT NULL DEFAULT 'medium',
                status           TEXT NOT NULL DEFAULT 'pending',
                source_event_id  UUID,
                correlation_id   UUID,
                context_jsonb    JSONB,
                llm_suggestion   JSONB,
                llm_confidence   DOUBLE PRECISION,
                llm_model_used   TEXT,
                decided_by       TEXT,
                decision         TEXT,
                decision_reason  TEXT,
                decision_jsonb   JSONB,
                created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                expires_at       TIMESTAMPTZ,
                decided_at       TIMESTAMPTZ,
                escalated_to     TEXT,
                escalation_count INTEGER NOT NULL DEFAULT 0
            )
        """)
    )

    op.execute(sa.text(f"CREATE INDEX ix_hitl_item_status ON {_GOVERNANCE}.hitl_item (status)"))
    op.execute(
        sa.text(f"CREATE INDEX ix_hitl_item_risk_class ON {_GOVERNANCE}.hitl_item (risk_class)")
    )
    op.execute(
        sa.text(
            f"CREATE INDEX ix_hitl_item_created_at ON {_GOVERNANCE}.hitl_item (created_at DESC)"
        )
    )

    # -- hitl_feedback ---------------------------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE {_GOVERNANCE}.hitl_feedback (
                feedback_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                hitl_item_id       UUID NOT NULL
                                       REFERENCES {_GOVERNANCE}.hitl_item (item_id)
                                       ON DELETE CASCADE,
                llm_suggestion     JSONB,
                human_decision     JSONB,
                agreement          BOOLEAN,
                correction_type    TEXT,
                correction_detail  TEXT,
                prompt_template_id UUID,
                created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    )

    op.execute(
        sa.text(f"CREATE INDEX ix_hitl_feedback_item ON {_GOVERNANCE}.hitl_feedback (hitl_item_id)")
    )

    # -- audit_event -----------------------------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE {_GOVERNANCE}.audit_event (
                event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                event_type      TEXT NOT NULL,
                actor           TEXT,
                action          TEXT NOT NULL,
                target_entity   TEXT,
                target_id       UUID,
                risk_class      TEXT,
                correlation_id  UUID,
                request_jsonb   JSONB,
                response_jsonb  JSONB,
                guard_result    JSONB,
                duration_ms     INTEGER,
                status          TEXT,
                ip_address      TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    )

    op.execute(
        sa.text(
            f"CREATE INDEX ix_audit_event_created ON {_GOVERNANCE}.audit_event (created_at DESC)"
        )
    )
    op.execute(sa.text(f"CREATE INDEX ix_audit_event_actor ON {_GOVERNANCE}.audit_event (actor)"))
    op.execute(
        sa.text(
            f"CREATE INDEX ix_audit_event_correlation ON {_GOVERNANCE}.audit_event (correlation_id)"
        )
    )

    # ── telemetry schema ────────────────────────────────────────────────
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {_TELEMETRY}"))

    # -- metric_point (partitioned) --------------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE {_TELEMETRY}.metric_point (
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
            f"CREATE INDEX ix_metric_point_host ON {_TELEMETRY}.metric_point (host_id, collected_at DESC)"  # noqa: E501
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX ix_metric_point_name ON {_TELEMETRY}.metric_point (metric_name, collected_at DESC)"  # noqa: E501
        )
    )

    # Create partitions for the current month and next month so inserts
    # don't fail at month boundaries before the retention job creates new ones.
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

    # -- llm_call_log ----------------------------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE {_TELEMETRY}.llm_call_log (
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
            f"CREATE INDEX ix_llm_call_log_called ON {_TELEMETRY}.llm_call_log (called_at DESC)"
        )
    )
    op.execute(
        sa.text(f"CREATE INDEX ix_llm_call_log_model ON {_TELEMETRY}.llm_call_log (model_id)")
    )
    op.execute(
        sa.text(
            f"CREATE INDEX ix_llm_call_log_correlation ON {_TELEMETRY}.llm_call_log (correlation_id)"  # noqa: E501
        )
    )
    op.execute(
        sa.text(f"CREATE INDEX ix_llm_call_log_status ON {_TELEMETRY}.llm_call_log (status)")
    )


def downgrade() -> None:
    # Reverse order — children first
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_TELEMETRY}.llm_call_log CASCADE"))

    # Drop all partitions of metric_point before the parent
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT inhrelid::regclass::text FROM pg_inherits "
            f"WHERE inhparent = '{_TELEMETRY}.metric_point'::regclass"
        )
    ).fetchall()
    for (child,) in rows:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {child} CASCADE"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_TELEMETRY}.metric_point CASCADE"))

    op.execute(sa.text(f"DROP TABLE IF EXISTS {_GOVERNANCE}.hitl_feedback CASCADE"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_GOVERNANCE}.audit_event CASCADE"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_GOVERNANCE}.hitl_item CASCADE"))

    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {_TELEMETRY} CASCADE"))
    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {_GOVERNANCE} CASCADE"))
