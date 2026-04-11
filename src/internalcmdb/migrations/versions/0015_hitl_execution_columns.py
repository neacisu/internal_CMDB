"""Add executed_at and execution_result to governance.hitl_item.

Revision ID: 0015
Revises: 0014
Created: 2026-04-10

Enables the HITL re-execution worker: after an operator approves a
tool-call request, the worker sets ``executed_at`` and writes the
tool output into ``execution_result``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "hitl_item",
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="governance",
    )
    op.add_column(
        "hitl_item",
        sa.Column("execution_result", postgresql.JSONB(), nullable=True),
        schema="governance",
    )
    op.create_index(
        "ix_hitl_item_approved_pending_exec",
        "hitl_item",
        ["status", "executed_at"],
        schema="governance",
        postgresql_where=sa.text("status = 'approved' AND executed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hitl_item_approved_pending_exec",
        table_name="hitl_item",
        schema="governance",
    )
    op.drop_column("hitl_item", "execution_result", schema="governance")
    op.drop_column("hitl_item", "executed_at", schema="governance")
