"""ARQ worker settings and queue configuration."""

from __future__ import annotations

from arq.connections import RedisSettings

from internalcmdb.api.config import get_settings


def _redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(settings.redis_url)


async def _noop(_ctx: dict) -> None:  # type: ignore[type-arg]
    """No-op placeholder — ARQ requires at least one registered function."""


class WorkerSettings:
    """ARQ worker settings — picked up by ``arq internalcmdb.workers.queue.WorkerSettings``."""

    redis_settings = _redis_settings()
    functions = [_noop]  # noqa: RUF012
    queue_name = "infraq:arq:queue"
