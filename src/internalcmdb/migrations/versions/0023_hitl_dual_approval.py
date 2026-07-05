"""Add dual-approval tracking to governance.hitl_item.

Revision ID: 0023
Revises: 0022
Created: 2026-07-05

Changes:
  - Add approvals_jsonb column to governance.hitl_item for RC-3
    two-person approval workflow (array of {decided_by, reason, decided_at}).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "governance"
_TABLE = "hitl_item"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            "approvals_jsonb",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "approvals_jsonb", schema=_SCHEMA)
