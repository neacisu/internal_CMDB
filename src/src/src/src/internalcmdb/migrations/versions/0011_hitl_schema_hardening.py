"""Harden HITL schema — updated_at, CHECK constraints, rules_jsonb column.

Revision ID: 0011
Revises: 0010
Created: 2026-03-23

Adds:
  governance.hitl_item.updated_at  — auto-updated timestamp
  CHECK constraints on status, risk_class, priority for data integrity
  governance.policy_record.rules_jsonb — policy rule definitions (JSONB)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GOV = "governance"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"ALTER TABLE {_GOV}.hitl_item "
            f"ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        )
    )

    op.execute(
        sa.text(f"""
            DO $$ BEGIN
                ALTER TABLE {_GOV}.hitl_item
                    ADD CONSTRAINT ck_hitl_item_status
                    CHECK (status IN (
                        'pending', 'escalated', 'approved', 'rejected',
                        'blocked', 'approved_with_modifications'
                    ));
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """)
    )

    op.execute(
        sa.text(f"""
            DO $$ BEGIN
                ALTER TABLE {_GOV}.hitl_item
                    ADD CONSTRAINT ck_hitl_item_risk_class
                    CHECK (risk_class IN ('RC-1', 'RC-2', 'RC-3', 'RC-4'));
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """)
    )

    op.execute(
        sa.text(f"""
            DO $$ BEGIN
                ALTER TABLE {_GOV}.hitl_item
                    ADD CONSTRAINT ck_hitl_item_priority
                    CHECK (priority IN ('critical', 'high', 'medium', 'low'));
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """)
    )

    op.execute(
        sa.text(f"""
            CREATE OR REPLACE FUNCTION {_GOV}.fn_hitl_item_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = now();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
    )

    op.execute(
        sa.text(f"""
            DROP TRIGGER IF EXISTS trg_hitl_item_updated_at ON {_GOV}.hitl_item;
            CREATE TRIGGER trg_hitl_item_updated_at
                BEFORE UPDATE ON {_GOV}.hitl_item
                FOR EACH ROW EXECUTE FUNCTION {_GOV}.fn_hitl_item_updated_at()
        """)
    )

    bind = op.get_bind()
    table_exists = bind.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_schema = :schema AND table_name = :table"
            ")"
        ),
        {"schema": _GOV, "table": "policy_record"},
    ).scalar()
    if table_exists:
        op.execute(
            sa.text(f"ALTER TABLE {_GOV}.policy_record ADD COLUMN IF NOT EXISTS rules_jsonb JSONB")
        )


def downgrade() -> None:
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_hitl_item_updated_at ON {_GOV}.hitl_item"))
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {_GOV}.fn_hitl_item_updated_at()"))
    op.execute(
        sa.text(f"ALTER TABLE {_GOV}.hitl_item DROP CONSTRAINT IF EXISTS ck_hitl_item_status")
    )
    op.execute(
        sa.text(f"ALTER TABLE {_GOV}.hitl_item DROP CONSTRAINT IF EXISTS ck_hitl_item_risk_class")
    )
    op.execute(
        sa.text(f"ALTER TABLE {_GOV}.hitl_item DROP CONSTRAINT IF EXISTS ck_hitl_item_priority")
    )
    op.execute(sa.text(f"ALTER TABLE {_GOV}.hitl_item DROP COLUMN IF EXISTS updated_at"))
    bind = op.get_bind()
    table_exists = bind.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_schema = :schema AND table_name = :table"
            ")"
        ),
        {"schema": _GOV, "table": "policy_record"},
    ).scalar()
    if table_exists:
        op.execute(sa.text(f"ALTER TABLE {_GOV}.policy_record DROP COLUMN IF EXISTS rules_jsonb"))
