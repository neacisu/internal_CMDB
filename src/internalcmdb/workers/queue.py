"""ARQ worker settings and queue configuration."""

from __future__ import annotations

import logging

from arq.connections import RedisSettings
from arq.cron import cron

from internalcmdb.api.config import get_settings
from internalcmdb.workers.cognitive_tasks import COGNITIVE_TASKS, self_heal_check
from internalcmdb.workers.retention import data_retention_job

logger = logging.getLogger(__name__)

_MAX_JOBS = 10
_JOB_TIMEOUT_S = 600
_MAX_TRIES = 3
_HEALTH_CHECK_INTERVAL_S = 60


def _redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(settings.redis_url)


async def _noop(_ctx: dict) -> None:  # type: ignore[type-arg]
    """No-op placeholder — ARQ requires at least one registered function."""


async def _health_check(ctx: dict) -> dict:  # type: ignore[type-arg]
    """Periodic worker health check. Returns connection status for Redis and basic metrics."""
    redis = ctx.get("redis")
    status = "healthy"
    try:
        if redis:
            await redis.ping()
    except Exception:
        status = "degraded"
        logger.warning("Health check: Redis ping failed", exc_info=True)

    return {"status": status, "max_jobs": _MAX_JOBS}


class WorkerSettings:
    """ARQ worker settings — picked up by ``arq internalcmdb.workers.queue.WorkerSettings``."""

    redis_settings = _redis_settings()
    functions = [_noop, _health_check, data_retention_job, *COGNITIVE_TASKS.values()]  # noqa: RUF012
    cron_jobs = [  # noqa: RUF012
        cron(self_heal_check, minute={0, 15, 30, 45}),
    ]
    queue_name = "infraq:arq:queue"
    max_jobs = _MAX_JOBS
    job_timeout = _JOB_TIMEOUT_S
    max_tries = _MAX_TRIES
    health_check_interval = _HEALTH_CHECK_INTERVAL_S
