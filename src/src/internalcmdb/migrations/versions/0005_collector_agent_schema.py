"""Add collector agent, snapshot, and diff tables.

Revision ID: 0005
Revises: 0004
Created: 2026-03-15
"""
# pylint: disable=invalid-name,no-member

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- collector_agent --
    op.create_table(
        "collector_agent",
        sa.Column("agent_id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "host_id",
            sa.Uuid(),
            sa.ForeignKey("registry.host.host_id"),
            nullable=True,
        ),
        sa.Column("host_code", sa.Text(), nullable=False),
        sa.Column("agent_version", sa.Text(), nullable=False),
        sa.Column(
            "enrolled_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_heartbeat_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("agent_config_jsonb", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'online'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        schema="discovery",
    )
    op.create_index(
        "ix_collector_agent_host_code",
        "collector_agent",
        ["host_code"],
        schema="discovery",
    )
    op.create_index(
        "ix_collector_agent_status",
        "collector_agent",
        ["status"],
        schema="discovery",
    )

    # -- collector_snapshot --
    op.create_table(
        "collector_snapshot",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "agent_id",
            sa.Uuid(),
            sa.ForeignKey("discovery.collector_agent.agent_id"),
            nullable=False,
        ),
        sa.Column(
            "collection_run_id",
            sa.Uuid(),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=True,
        ),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_kind", sa.Text(), nullable=False),
        sa.Column("payload_jsonb", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("collected_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("tier_code", sa.Text(), nullable=False),
        schema="discovery",
    )
    op.create_unique_constraint(
        "uq_agent_snapshot_version",
        "collector_snapshot",
        ["agent_id", "snapshot_version"],
        schema="discovery",
    )
    op.create_index(
        "ix_snapshot_agent_kind_collected",
        "collector_snapshot",
        ["agent_id", "snapshot_kind", "collected_at"],
        schema="discovery",
    )
    op.create_index(
        "ix_snapshot_payload_hash",
        "collector_snapshot",
        ["payload_hash"],
        schema="discovery",
    )

    # -- snapshot_diff --
    op.create_table(
        "snapshot_diff",
        sa.Column("diff_id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("discovery.collector_snapshot.snapshot_id"),
            nullable=False,
        ),
        sa.Column(
            "previous_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("discovery.collector_snapshot.snapshot_id"),
            nullable=False,
        ),
        sa.Column("diff_jsonb", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="discovery",
    )
    op.create_index(
        "ix_snapshot_diff_snapshot",
        "snapshot_diff",
        ["snapshot_id"],
        schema="discovery",
    )


def downgrade() -> None:
    op.drop_table("snapshot_diff", schema="discovery")
    op.drop_table("collector_snapshot", schema="discovery")
    op.drop_table("collector_agent", schema="discovery")
