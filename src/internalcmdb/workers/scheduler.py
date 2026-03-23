"""F3.3 — CronScheduler.

Evaluates cron expressions from the ``worker.worker_schedule`` table,
enqueues due jobs via Redis (ARQ-compatible), and tracks
``last_run_at`` / ``next_run_at`` timestamps.

Usage::

    scheduler = CronScheduler(redis_url="redis://…", database_url="postgresql+psycopg://…")
    await scheduler.run()          # blocks until shutdown
    await scheduler.shutdown()     # request graceful stop from another coroutine
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from croniter import croniter
from redis.asyncio import Redis
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from internalcmdb.workers.models import JobHistory, WorkerSchedule

logger = logging.getLogger(__name__)

_DEFAULT_TICK_SECONDS = 15
_ARQ_QUEUE = "infraq:arq:queue"
_REDIS_CONNECT_RETRIES = 5
_REDIS_RETRY_DELAY_S = 3


class CronScheduler:
    """Persistent cron scheduler backed by PostgreSQL schedules and Redis enqueue."""

    def __init__(
        self,
        redis_url: str,
        database_url: str,
        *,
        tick_seconds: int = _DEFAULT_TICK_SECONDS,
        queue_name: str = _ARQ_QUEUE,
    ) -> None:
        self._redis_url = redis_url
        self._database_url = database_url
        self._tick_seconds = tick_seconds
        self._queue_name = queue_name

        self._running = False
        self._shutdown_event = asyncio.Event()

        engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main loop — evaluates cron schedules every *tick_seconds*."""
        self._running = True
        logger.info(
            "CronScheduler started. tick=%ds queue=%s", self._tick_seconds, self._queue_name
        )

        redis = await self._connect_redis()
        try:
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.to_thread(self._tick_sync, redis)
                except Exception:
                    logger.exception("Scheduler tick failed — will retry next cycle.")

                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=self._tick_seconds
                    )
                except TimeoutError:
                    pass
        finally:
            await redis.aclose()
            self._running = False
            logger.info("CronScheduler stopped.")

    async def shutdown(self) -> None:
        """Request graceful shutdown of the scheduler loop.

        Uses a cooperative yield so the coroutine suspends (S7503) while keeping
        the public API async for callers that ``await`` shutdown alongside I/O.
        """
        logger.info("CronScheduler shutdown requested.")
        self._shutdown_event.set()
        await asyncio.sleep(0)

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Redis connection with retry
    # ------------------------------------------------------------------

    async def _connect_redis(self) -> Redis:  # type: ignore[type-arg]
        """Connect to Redis with retries."""
        for attempt in range(1, _REDIS_CONNECT_RETRIES + 1):
            try:
                redis = Redis.from_url(self._redis_url, decode_responses=True)
                await redis.ping()
                logger.info("Redis connected (attempt %d).", attempt)
                return redis
            except Exception:
                logger.warning(
                    "Redis connection attempt %d/%d failed.",
                    attempt,
                    _REDIS_CONNECT_RETRIES,
                    exc_info=True,
                )
                if attempt < _REDIS_CONNECT_RETRIES:
                    await asyncio.sleep(_REDIS_RETRY_DELAY_S * attempt)
        raise ConnectionError(
            f"Failed to connect to Redis after {_REDIS_CONNECT_RETRIES} attempts"
        )

    # ------------------------------------------------------------------
    # Tick logic (runs in thread pool to avoid blocking event loop)
    # ------------------------------------------------------------------

    def _tick_sync(self, redis: Redis) -> None:  # type: ignore[type-arg]
        """Single scheduler tick: find due schedules, enqueue them, update timestamps.

        Runs inside ``asyncio.to_thread`` so DB I/O does not block the event loop.
        Redis ``lpush`` is synchronous-safe when called from a sync context on the
        async redis client (it schedules to the loop). We use loop.run_until_complete
        for the async lpush.
        """
        now = datetime.now(tz=UTC)
        db = self._session_factory()
        try:
            schedules = self._get_due_schedules(db, now)
            if not schedules:
                return

            logger.debug("Found %d due schedule(s).", len(schedules))
            for sched in schedules:
                self._enqueue_sync(redis, sched, db, now)
        finally:
            db.close()

    def _get_due_schedules(self, db: Session, now: datetime) -> list[WorkerSchedule]:
        """Return active schedules whose ``next_run_at`` is in the past or null."""
        stmt = (
            select(WorkerSchedule)
            .where(WorkerSchedule.is_active.is_(True))
            .where(
                (WorkerSchedule.next_run_at.is_(None))
                | (WorkerSchedule.next_run_at <= str(now.isoformat()))
            )
        )
        return list(db.execute(stmt).scalars().all())

    def _has_pending_job(self, db: Session, task_name: str) -> bool:
        """Check if a job is already queued/running for this task."""
        stmt = (
            select(JobHistory)
            .where(JobHistory.task_name == task_name)
            .where(JobHistory.status.in_(["queued", "running"]))
            .limit(1)
        )
        return db.execute(stmt).scalars().first() is not None

    def _enqueue_sync(
        self,
        redis: Redis,  # type: ignore[type-arg]
        sched: WorkerSchedule,
        db: Session,
        now: datetime,
    ) -> None:
        """Enqueue a job into Redis and update the schedule timestamps."""
        if self._has_pending_job(db, sched.task_name):
            logger.info(
                "Skipping enqueue for task=%s — already queued/running.",
                sched.task_name,
            )
            cron = croniter(sched.cron_expression, now)
            next_run = cron.get_next(datetime)
            db.execute(
                update(WorkerSchedule)
                .where(WorkerSchedule.schedule_id == sched.schedule_id)
                .values(next_run_at=str(next_run.isoformat()))
            )
            db.commit()
            return

        job_id = str(uuid.uuid4())

        job = JobHistory(
            job_id=uuid.UUID(job_id),
            task_name=sched.task_name,
            status="queued",
            triggered_by="scheduler",
            schedule_cron=sched.cron_expression,
            args_json=json.dumps([]),
        )
        db.add(job)

        cron = croniter(sched.cron_expression, now)
        next_run = cron.get_next(datetime)

        db.execute(
            update(WorkerSchedule)
            .where(WorkerSchedule.schedule_id == sched.schedule_id)
            .values(
                last_run_at=str(now.isoformat()),
                next_run_at=str(next_run.isoformat()),
            )
        )
        db.commit()

        payload = json.dumps(
            {
                "job_id": job_id,
                "task_name": sched.task_name,
                "enqueue_time": now.isoformat(),
                "args": [],
            }
        )

        import asyncio as _asyncio  # noqa: PLC0415

        try:
            loop = _asyncio.get_running_loop()
            loop.call_soon_threadsafe(
                lambda: _asyncio.ensure_future(redis.lpush(self._queue_name, payload))
            )
        except RuntimeError:
            import redis as _sync_redis  # noqa: PLC0415

            sync_r = _sync_redis.from_url(self._redis_url, decode_responses=True)
            sync_r.lpush(self._queue_name, payload)
            sync_r.close()

        logger.info(
            "Enqueued task=%s job=%s next_run=%s",
            sched.task_name,
            job_id,
            next_run.isoformat(),
        )
