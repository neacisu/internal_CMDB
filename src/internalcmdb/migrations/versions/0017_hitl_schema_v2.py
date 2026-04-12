"""Bring governance.hitl_item up to HITL-v2 schema and create hitl_feedback.

Revision ID: 0017
Revises: 0016
Created: 2026-04-12

Changes:
  - Rename hitl_item.hitl_item_id  → item_id
  - Rename hitl_item.entity_type   → item_type
  - Add all columns required by the hitl_workflow / hitl router:
      priority, source_event_id, correlation_id, context_jsonb,
      llm_suggestion, llm_confidence, llm_model_used, expires_at,
      decided_by, decision, decision_reason, decided_at,
      decision_jsonb, escalated_to
  - Create governance.hitl_feedback table
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "governance"
_TABLE = "hitl_item"


def upgrade() -> None:
    # ── rename existing columns ──────────────────────────────────────────
    op.alter_column(_TABLE, "hitl_item_id", new_column_name="item_id", schema=_SCHEMA)
    op.alter_column(_TABLE, "entity_type", new_column_name="item_type", schema=_SCHEMA)

    # ── add missing columns ──────────────────────────────────────────────
    op.add_column(
        _TABLE,
        sa.Column("priority", sa.Text(), nullable=False, server_default="medium"),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("source_event_id", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("correlation_id", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("context_jsonb", postgresql.JSONB(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("llm_suggestion", postgresql.JSONB(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("llm_confidence", sa.Float(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("llm_model_used", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("decided_by", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("decision", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("decision_reason", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("decision_jsonb", postgresql.JSONB(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("escalated_to", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )

    # ── index for queue / history queries ────────────────────────────────
    op.create_index(
        "ix_hitl_item_status_priority",
        _TABLE,
        ["status", "priority", "created_at"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_hitl_item_decided_at",
        _TABLE,
        ["decided_at"],
        schema=_SCHEMA,
    )

    # ── create governance.hitl_feedback ──────────────────────────────────
    op.create_table(
        "hitl_feedback",
        sa.Column("feedback_id", sa.Text(), nullable=False),
        sa.Column("hitl_item_id", sa.Text(), nullable=False),
        sa.Column("llm_suggestion", postgresql.JSONB(), nullable=True),
        sa.Column("human_decision", postgresql.JSONB(), nullable=True),
        sa.Column("agreement", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("feedback_id"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_hitl_feedback_item_id",
        "hitl_feedback",
        ["hitl_item_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("hitl_feedback", schema=_SCHEMA)

    for idx in (
        "ix_hitl_item_decided_at",
        "ix_hitl_item_status_priority",
    ):
        op.drop_index(idx, table_name=_TABLE, schema=_SCHEMA)

    for col in (
        "escalated_to",
        "decision_jsonb",
        "decided_at",
        "decision_reason",
        "decision",
        "decided_by",
        "expires_at",
        "llm_model_used",
        "llm_confidence",
        "llm_suggestion",
        "context_jsonb",
        "correlation_id",
        "source_event_id",
        "priority",
    ):
        op.drop_column(_TABLE, col, schema=_SCHEMA)

    op.alter_column(_TABLE, "item_type", new_column_name="entity_type", schema=_SCHEMA)
    op.alter_column(_TABLE, "item_id", new_column_name="hitl_item_id", schema=_SCHEMA)
