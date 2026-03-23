"""SLO framework — slo_definition and slo_measurement tables.

Revision ID: 0010
Revises: 0009
Created: 2026-03-22

This migration creates:
  telemetry.slo_definition  — SLO target definitions (per service)
  telemetry.slo_measurement — time-series SLI measurements (range-partitioned)
"""

# pylint: disable=invalid-name,no-member
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TELEMETRY = "telemetry"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {_TELEMETRY}"))

    # -- slo_definition --------------------------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE {_TELEMETRY}.slo_definition (
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
            f"CREATE INDEX idx_slo_def_service "
            f"ON {_TELEMETRY}.slo_definition (service_id)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX idx_slo_def_active "
            f"ON {_TELEMETRY}.slo_definition (is_active) WHERE is_active = true"
        )
    )

    # -- slo_measurement (partitioned) -----------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE {_TELEMETRY}.slo_measurement (
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
            f"CREATE INDEX idx_slo_meas_slo_id "
            f"ON {_TELEMETRY}.slo_measurement (slo_id, measured_at DESC)"
        )
    )

    now = datetime.now(tz=UTC)
    for month_offset in (0, 1):
        m = now.month + month_offset
        y = now.year
        if m > 12:
            m -= 12
            y += 1
        p_start = f"{y}-{m:02d}-01"
        if m == 12:
            p_end = f"{y + 1}-01-01"
        else:
            p_end = f"{y}-{m + 1:02d}-01"
        part_name = f"slo_measurement_{y}_{m:02d}"
        op.execute(
            sa.text(
                f"CREATE TABLE IF NOT EXISTS {_TELEMETRY}.{part_name} "
                f"PARTITION OF {_TELEMETRY}.slo_measurement "
                f"FOR VALUES FROM ('{p_start}') TO ('{p_end}')"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT inhrelid::regclass::text FROM pg_inherits "
            f"WHERE inhparent = '{_TELEMETRY}.slo_measurement'::regclass"
        )
    ).fetchall()
    for (child,) in rows:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {child} CASCADE"))

    op.execute(sa.text(f"DROP TABLE IF EXISTS {_TELEMETRY}.slo_measurement CASCADE"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_TELEMETRY}.slo_definition CASCADE"))
