"""ARQ worker settings and queue configuration."""

from __future__ import annotations

import logging
from typing import Any, ClassVar, cast

from arq.connections import RedisSettings
from arq.cron import cron

from internalcmdb.api.config import get_settings
from internalcmdb.workers.cognitive_tasks import (
    COGNITIVE_TASKS,
    autonomous_reasoning_cycle,
    container_log_audit,
    ingest_knowledge_base,
    process_approved_hitl_items,
    self_heal_check,
)
from internalcmdb.workers.retention import data_retention_job

logger = logging.getLogger(__name__)

_Ctx = dict[str, Any]
_MAX_JOBS = 10
_JOB_TIMEOUT_S = 600
_MAX_TRIES = 3
_HEALTH_CHECK_INTERVAL_S = 60


def _redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(settings.redis_url)


async def _noop(_ctx: _Ctx) -> None:
    """No-op placeholder — ARQ requires at least one registered function."""


async def _health_check(ctx: _Ctx) -> dict[str, Any]:
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

    redis_settings: ClassVar[RedisSettings] = _redis_settings()  # type: ignore[misc]
    functions: ClassVar[list[Any]] = [
        _noop,
        _health_check,
        data_retention_job,
        *COGNITIVE_TASKS.values(),
    ]
    cron_jobs: ClassVar[list[Any]] = [
        cron(cast(Any, self_heal_check), minute={0, 15, 30, 45}),
        cron(cast(Any, container_log_audit), hour={0, 6, 12, 18}, minute={5}),
        cron(
            cast(Any, autonomous_reasoning_cycle),
            minute={2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57},
        ),
        cron(cast(Any, ingest_knowledge_base), minute={0, 15, 30, 45}),
        cron(
            cast(Any, process_approved_hitl_items),
            minute={0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                    16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
                    30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43,
                    44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57,
                    58, 59},
        ),
    ]
    queue_name = "infraq:arq:queue"
    max_jobs = _MAX_JOBS
    job_timeout = _JOB_TIMEOUT_S
    max_tries = _MAX_TRIES
    health_check_interval = _HEALTH_CHECK_INTERVAL_S
