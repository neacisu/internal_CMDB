"""ARQ WorkerSettings sanity checks (run.py delegates to this)."""

from __future__ import annotations

from internalcmdb.workers.queue import WorkerSettings


def test_worker_settings_configured() -> None:
    assert WorkerSettings.queue_name == "infraq:arq:queue"
    assert len(WorkerSettings.functions) >= 2
    assert WorkerSettings.max_jobs >= 1
