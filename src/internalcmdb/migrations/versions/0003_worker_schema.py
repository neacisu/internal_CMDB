"""Create worker schema with job_history and worker_schedule tables.

Revision ID: 0003
Revises: 0002
Created: 2026-03-10
"""

# pylint: disable=invalid-name,no-member
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS worker")

    op.create_table(
        "job_history",
        sa.Column("job_id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("schedule_cron", sa.Text(), nullable=True),
        sa.Column("args_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="worker",
    )
    op.create_index(
        "ix_worker_job_history_task_status",
        "job_history",
        ["task_name", "status"],
        schema="worker",
    )
    op.create_index(
        "ix_worker_job_history_created_at",
        "job_history",
        ["created_at"],
        schema="worker",
    )

    op.create_table(
        "worker_schedule",
        sa.Column("schedule_id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_name", sa.Text(), nullable=False),
        sa.Column("cron_expression", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("next_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="worker",
    )


def downgrade() -> None:
    op.drop_table("worker_schedule", schema="worker")
    op.drop_index("ix_worker_job_history_created_at", table_name="job_history", schema="worker")
    op.drop_index("ix_worker_job_history_task_status", table_name="job_history", schema="worker")
    op.drop_table("job_history", schema="worker")
    op.execute("DROP SCHEMA IF EXISTS worker CASCADE")
