"""Worker entrypoint — works around Python 3.12+ asyncio.get_event_loop() removal."""

# ruff: noqa: I001  — imports intentionally follow asyncio event loop setup
import asyncio

# Must be set before arq Worker is instantiated (arq 0.27 calls get_event_loop in __init__)
asyncio.set_event_loop(asyncio.new_event_loop())

from arq.worker import run_worker  # noqa: E402  # pylint: disable=wrong-import-position
from internalcmdb.workers.queue import WorkerSettings  # noqa: E402  # pylint: disable=wrong-import-position

if __name__ == "__main__":
    run_worker(WorkerSettings)  # type: ignore[arg-type]
