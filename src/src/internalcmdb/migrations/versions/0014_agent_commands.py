"""Add agent_control schema: command_log and tool_definition tables.

Revision ID: 0014
Revises: 0013
Created: 2026-04-09

Introduces bidirectional agent command channel:
  - ``agent_control`` PostgreSQL schema
  - ``agent_control.command_log`` — records commands sent to agents
  - ``agent_control.tool_definition`` — cognitive tool catalog persisted in DB
  - ``cognitive.agent_session`` — ReAct agent sessions
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Reusable server-default expressions
# ---------------------------------------------------------------------------
_DEFAULT_UUID = sa.text("gen_random_uuid()")
_DEFAULT_NOW = sa.text("now()")


def upgrade() -> None:
    # -- agent_control schema -----------------------------------------------
    op.execute("CREATE SCHEMA IF NOT EXISTS agent_control")
    op.execute("GRANT USAGE ON SCHEMA agent_control TO internalcmdb")

    op.create_table(
        "command_log",
        sa.Column(
            "command_id",
            sa.UUID(),
            server_default=_DEFAULT_UUID,
            nullable=False,
        ),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("command_type", sa.VARCHAR(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.VARCHAR(32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("issued_by", sa.VARCHAR(128), nullable=False),
        sa.Column("approved_by", sa.VARCHAR(128), nullable=True),
        sa.Column("hitl_item_id", sa.UUID(), nullable=True),
        sa.Column("error", sa.TEXT(), nullable=True),
        sa.Column("duration_ms", sa.INTEGER(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=_DEFAULT_NOW,
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("command_id"),
        schema="agent_control",
    )

    op.create_index(
        "ix_command_log_agent_status",
        "command_log",
        ["agent_id", "status"],
        schema="agent_control",
    )
    op.create_index(
        "ix_command_log_created",
        "command_log",
        ["created_at"],
        schema="agent_control",
    )

    op.create_table(
        "tool_definition",
        sa.Column(
            "tool_id",
            sa.VARCHAR(128),
            nullable=False,
        ),
        sa.Column("name", sa.VARCHAR(256), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=False),
        sa.Column("parameters_schema", sa.JSON(), nullable=False),
        sa.Column("risk_class", sa.VARCHAR(8), nullable=False),
        sa.Column(
            "is_active",
            sa.BOOLEAN(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("tags", sa.ARRAY(sa.TEXT()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("cooldown_s", sa.INTEGER(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=_DEFAULT_NOW,
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tool_id"),
        schema="agent_control",
    )

    # -- cognitive.agent_session --------------------------------------------
    op.create_table(
        "agent_session",
        sa.Column(
            "session_id",
            sa.UUID(),
            server_default=_DEFAULT_UUID,
            nullable=False,
        ),
        sa.Column("goal", sa.TEXT(), nullable=False),
        sa.Column(
            "status",
            sa.VARCHAR(32),
            server_default=sa.text("'running'"),
            nullable=False,
        ),
        sa.Column("model_used", sa.VARCHAR(128), nullable=True),
        sa.Column("iterations", sa.INTEGER(), server_default=sa.text("0"), nullable=False),
        sa.Column("tokens_used", sa.INTEGER(), server_default=sa.text("0"), nullable=False),
        sa.Column("tool_calls", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("conversation", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("final_answer", sa.TEXT(), nullable=True),
        sa.Column("error", sa.TEXT(), nullable=True),
        sa.Column("triggered_by", sa.VARCHAR(128), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=_DEFAULT_NOW,
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("session_id"),
        schema="cognitive",
    )

    op.create_index(
        "ix_agent_session_status",
        "agent_session",
        ["status"],
        schema="cognitive",
    )

    # -- audit trail for tool executions ------------------------------------
    op.create_table(
        "tool_execution_log",
        sa.Column(
            "audit_id",
            sa.UUID(),
            server_default=_DEFAULT_UUID,
            nullable=False,
        ),
        sa.Column("tool_id", sa.VARCHAR(128), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("success", sa.BOOLEAN(), nullable=False),
        sa.Column("error", sa.TEXT(), nullable=True),
        sa.Column("execution_time_ms", sa.INTEGER(), nullable=True),
        sa.Column("risk_class", sa.VARCHAR(8), nullable=False),
        sa.Column("triggered_by", sa.VARCHAR(128), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=_DEFAULT_NOW,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("audit_id"),
        schema="agent_control",
    )

    op.create_index(
        "ix_tool_execution_log_tool",
        "tool_execution_log",
        ["tool_id"],
        schema="agent_control",
    )


def downgrade() -> None:
    op.drop_table("tool_execution_log", schema="agent_control")
    op.drop_table("agent_session", schema="cognitive")
    op.drop_table("tool_definition", schema="agent_control")
    op.drop_table("command_log", schema="agent_control")
    op.execute("DROP SCHEMA IF EXISTS agent_control CASCADE")
