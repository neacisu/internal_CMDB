"""SQLAlchemy models for the worker job system (schema: worker)."""

from __future__ import annotations

import uuid
from typing import ClassVar

from sqlalchemy import Integer, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from internalcmdb.models.base import Base


class JobHistory(Base):
    """Persisted record of every worker task execution."""

    __tablename__ = "job_history"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "worker"}

    job_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="queued"
    )  # queued | running | completed | failed | cancelled
    started_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    finished_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    exit_code: Mapped[int | None] = mapped_column(Integer)
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    schedule_cron: Mapped[str | None] = mapped_column(Text)
    args_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class WorkerSchedule(Base):
    """Cron-based schedule for recurring worker tasks."""

    __tablename__ = "worker_schedule"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "worker"}

    schedule_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    cron_expression: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    next_run_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    last_run_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
