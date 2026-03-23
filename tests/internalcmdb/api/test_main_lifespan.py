"""Tests for lifespan background task management (S7497 fix).

Covers:
  - CancelledError is handled via asyncio.gather(return_exceptions=True)
  - Background tasks are properly cancelled during shutdown
  - asyncio.gather pattern does not propagate CancelledError
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_background_tasks_cancelled_cleanly() -> None:
    """Verify that background tasks are cancelled via gather(return_exceptions=True)
    instead of catching CancelledError directly (S7497 fix)."""
    task1 = asyncio.create_task(asyncio.sleep(3600))
    task2 = asyncio.create_task(asyncio.sleep(3600))

    task1.cancel()
    task2.cancel()

    results = await asyncio.gather(task1, task2, return_exceptions=True)

    for r in results:
        assert isinstance(r, asyncio.CancelledError)


@pytest.mark.asyncio
async def test_gather_return_exceptions_does_not_propagate() -> None:
    """asyncio.gather with return_exceptions=True must not raise."""
    async def _fail() -> None:
        raise RuntimeError("boom")

    async def _cancel() -> None:
        await asyncio.sleep(0)
        raise asyncio.CancelledError()

    results = await asyncio.gather(
        _fail(), _cancel(), return_exceptions=True
    )
    assert isinstance(results[0], RuntimeError)
    assert isinstance(results[1], asyncio.CancelledError)


@pytest.mark.asyncio
async def test_gather_vs_try_except_pattern() -> None:
    """The gather(return_exceptions=True) pattern is superior to
    try/await/except CancelledError: pass because it:
    1. Does not suppress external cancellations
    2. Collects all exceptions atomically
    3. Satisfies S7497 (CancelledError re-raised)"""
    tasks_completed = []

    async def background(name: str) -> None:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            tasks_completed.append(name)
            raise

    t1 = asyncio.create_task(background("staleness"))
    t2 = asyncio.create_task(background("escalation"))

    await asyncio.sleep(0)
    t1.cancel()
    t2.cancel()

    results = await asyncio.gather(t1, t2, return_exceptions=True)

    assert len(results) == 2
    assert all(isinstance(r, asyncio.CancelledError) for r in results)
    assert set(tasks_completed) == {"staleness", "escalation"}


def test_main_py_uses_gather_not_try_except() -> None:
    """Verify the source code of main.py uses asyncio.gather(return_exceptions=True)
    instead of try/except CancelledError."""
    from pathlib import Path

    content = Path("src/internalcmdb/api/main.py").read_text()

    assert "return_exceptions=True" in content, (
        "main.py must use asyncio.gather(return_exceptions=True)"
    )

    lines = content.split("\n")
    cancelled_catches = [
        i for i, line in enumerate(lines)
        if "except asyncio.CancelledError" in line
        or "except CancelledError" in line
    ]
    assert len(cancelled_catches) == 0, (
        f"main.py still has CancelledError catch on lines: {cancelled_catches}"
    )
