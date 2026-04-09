"""Tests for internalcmdb.workers.scheduler — CronScheduler."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.workers.models import JobHistory, WorkerSchedule
from internalcmdb.workers.scheduler import CronScheduler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_schedule(
    task_name: str = "test_task",
    cron_expression: str = "* * * * *",
    next_run_at: str | None = None,
    is_active: bool = True,
) -> WorkerSchedule:
    sched = WorkerSchedule()
    sched.schedule_id = uuid.uuid4()
    sched.task_name = task_name
    sched.cron_expression = cron_expression
    sched.is_active = is_active
    sched.next_run_at = next_run_at
    return sched


def _make_job(task_name: str, status: str = "queued") -> JobHistory:
    job = JobHistory()
    job.job_id = uuid.uuid4()
    job.task_name = task_name
    job.status = status
    job.triggered_by = "scheduler"
    return job


def _make_scheduler(**kwargs) -> CronScheduler:
    defaults = {
        "redis_url": "redis://localhost:6379",
        "database_url": "postgresql+psycopg://user:pass@localhost/db",
    }
    defaults.update(kwargs)
    with (
        patch("internalcmdb.workers.scheduler.create_engine"),
        patch("internalcmdb.workers.scheduler.sessionmaker"),
    ):
        return CronScheduler(**defaults)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestSchedulerConstructor:
    def test_scheduler_constructor(self):
        with (
            patch("internalcmdb.workers.scheduler.create_engine"),
            patch("internalcmdb.workers.scheduler.sessionmaker"),
        ):
            scheduler = CronScheduler(
                redis_url="redis://localhost:6379",
                database_url="postgresql+psycopg://user:pass@localhost/db",
                tick_seconds=30,
                queue_name="custom:queue",
            )

        assert scheduler._redis_url == "redis://localhost:6379"
        assert scheduler._database_url == "postgresql+psycopg://user:pass@localhost/db"
        assert scheduler._tick_seconds == 30
        assert scheduler._queue_name == "custom:queue"
        assert scheduler._running is False
        assert not scheduler._shutdown_event.is_set()

    def test_scheduler_constructor_defaults(self):
        with (
            patch("internalcmdb.workers.scheduler.create_engine"),
            patch("internalcmdb.workers.scheduler.sessionmaker"),
        ):
            scheduler = CronScheduler(
                redis_url="redis://localhost:6379",
                database_url="postgresql+psycopg://user:pass@localhost/db",
            )

        assert scheduler._tick_seconds == 15
        assert scheduler._queue_name == "infraq:arq:queue"


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


class TestSchedulerShutdown:
    @pytest.mark.asyncio
    async def test_scheduler_shutdown_sets_event(self):
        scheduler = _make_scheduler()
        assert not scheduler._shutdown_event.is_set()
        assert scheduler.is_running is False

        await scheduler.shutdown()

        assert scheduler._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_scheduler_is_running_false_after_shutdown(self):
        scheduler = _make_scheduler()
        scheduler._running = True

        await scheduler.shutdown()

        assert scheduler._shutdown_event.is_set()


# ---------------------------------------------------------------------------
# _get_due_schedules
# ---------------------------------------------------------------------------


class TestGetDueSchedules:
    def test_get_due_schedules_empty(self):
        scheduler = _make_scheduler()
        db = MagicMock()
        db.execute.return_value.scalars.return_value.all.return_value = []

        now = datetime.now(tz=UTC)
        result = scheduler._get_due_schedules(db, now)

        assert result == []

    def test_get_due_schedules_due(self):
        scheduler = _make_scheduler()
        db = MagicMock()
        past = (datetime.now(tz=UTC) - timedelta(minutes=5)).isoformat()
        sched = _make_schedule(next_run_at=past)
        db.execute.return_value.scalars.return_value.all.return_value = [sched]

        now = datetime.now(tz=UTC)
        result = scheduler._get_due_schedules(db, now)

        assert len(result) == 1
        assert result[0].task_name == sched.task_name

    def test_get_due_schedules_no_next_run(self):
        scheduler = _make_scheduler()
        db = MagicMock()
        sched = _make_schedule(next_run_at=None)
        db.execute.return_value.scalars.return_value.all.return_value = [sched]

        result = scheduler._get_due_schedules(db, datetime.now(tz=UTC))

        assert len(result) == 1


# ---------------------------------------------------------------------------
# _has_pending_job
# ---------------------------------------------------------------------------


class TestHasPendingJob:
    def test_has_pending_job_false(self):
        scheduler = _make_scheduler()
        db = MagicMock()
        db.execute.return_value.scalars.return_value.first.return_value = None

        assert scheduler._has_pending_job(db, "some_task") is False

    def test_has_pending_job_true(self):
        scheduler = _make_scheduler()
        db = MagicMock()
        job = _make_job("some_task", status="queued")
        db.execute.return_value.scalars.return_value.first.return_value = job

        assert scheduler._has_pending_job(db, "some_task") is True

    def test_has_pending_job_running(self):
        scheduler = _make_scheduler()
        db = MagicMock()
        job = _make_job("some_task", status="running")
        db.execute.return_value.scalars.return_value.first.return_value = job

        assert scheduler._has_pending_job(db, "some_task") is True


# ---------------------------------------------------------------------------
# _connect_redis
# ---------------------------------------------------------------------------


class TestConnectRedis:
    @pytest.mark.asyncio
    async def test_connect_redis_success(self):
        scheduler = _make_scheduler()

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with patch("internalcmdb.workers.scheduler.Redis") as mock_redis_cls:
            mock_redis_cls.from_url.return_value = mock_redis
            result = await scheduler._connect_redis()

        assert result is mock_redis
        mock_redis.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_redis_all_fail(self):
        scheduler = _make_scheduler()

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=ConnectionRefusedError("refused"))

        with (
            patch("internalcmdb.workers.scheduler.Redis") as mock_redis_cls,
            patch("internalcmdb.workers.scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_redis_cls.from_url.return_value = mock_redis
            with pytest.raises(ConnectionError, match="Failed to connect to Redis"):
                await scheduler._connect_redis()

    @pytest.mark.asyncio
    async def test_connect_redis_succeeds_on_second_attempt(self):
        scheduler = _make_scheduler()

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=[ConnectionRefusedError("refused"), True])

        with (
            patch("internalcmdb.workers.scheduler.Redis") as mock_redis_cls,
            patch("internalcmdb.workers.scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_redis_cls.from_url.return_value = mock_redis
            result = await scheduler._connect_redis()

        assert result is mock_redis
        assert mock_redis.ping.await_count == 2


# ---------------------------------------------------------------------------
# _enqueue_sync
# ---------------------------------------------------------------------------


class TestEnqueueSync:
    def test_enqueue_skip_if_pending(self):
        scheduler = _make_scheduler()
        db = MagicMock()

        sched = _make_schedule(task_name="my_task", cron_expression="* * * * *")
        job = _make_job("my_task", status="queued")
        db.execute.return_value.scalars.return_value.first.return_value = job

        redis_mock = MagicMock()
        now = datetime.now(tz=UTC)

        scheduler._enqueue_sync(redis_mock, sched, db, now)

        db.add.assert_not_called()
        db.commit.assert_called_once()

    def test_enqueue_creates_job(self):
        scheduler = _make_scheduler()
        db = MagicMock()

        sched = _make_schedule(task_name="my_task", cron_expression="0 * * * *")
        db.execute.return_value.scalars.return_value.first.return_value = None

        redis_mock = MagicMock()
        now = datetime.now(tz=UTC)

        with (
            patch(
                "internalcmdb.workers.scheduler.asyncio.get_running_loop",
                side_effect=RuntimeError("no loop"),
            ),
            patch("redis.from_url") as mock_sync_redis_from_url,
        ):
            mock_sync_conn = MagicMock()
            mock_sync_redis_from_url.return_value = mock_sync_conn

            scheduler._enqueue_sync(redis_mock, sched, db, now)

        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert isinstance(added_obj, JobHistory)
        assert added_obj.task_name == "my_task"
        assert added_obj.status == "queued"
        assert added_obj.triggered_by == "scheduler"
        db.commit.assert_called_once()
