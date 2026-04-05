"""Tests for internalcmdb.workers.models ORM mapping."""

from __future__ import annotations

import uuid

from internalcmdb.workers.models import JobHistory, WorkerSchedule


def test_job_history_tablename() -> None:
    assert JobHistory.__tablename__ == "job_history"
    assert JobHistory.__table_args__ == {"schema": "worker"}


def test_worker_schedule_tablename() -> None:
    assert WorkerSchedule.__tablename__ == "worker_schedule"


def test_job_history_instantiation() -> None:
    j = JobHistory(
        job_id=uuid.uuid4(),
        task_name="t",
        status="queued",
        triggered_by="manual",
    )
    assert j.task_name == "t"
