"""CronScheduler entrypoint — evaluates DB schedules and enqueues ARQ jobs."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from internalcmdb.api.config import get_settings
from internalcmdb.config.db_credentials import build_database_url_sync

logger = logging.getLogger(__name__)


def _database_url() -> str:
    return build_database_url_sync(get_settings())


def _redis_url() -> str:
    return get_settings().redis_url


async def _main() -> None:
    from internalcmdb.workers.scheduler import CronScheduler  # noqa: PLC0415

    scheduler = CronScheduler(
        redis_url=_redis_url(),
        database_url=_database_url(),
    )

    loop = asyncio.get_running_loop()

    def _request_shutdown() -> None:
        logger.info("Scheduler received shutdown signal")
        loop.create_task(scheduler.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _request_shutdown)

    await scheduler.run()


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    asyncio.run(_main())
