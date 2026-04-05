"""Tests for internalcmdb.workers.queue health and noop tasks."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from internalcmdb.workers import queue as queue_mod


@pytest.mark.asyncio
async def test_noop() -> None:
    await queue_mod._noop({})


@pytest.mark.asyncio
async def test_health_check_with_redis_ok() -> None:
    redis = AsyncMock()
    redis.ping = AsyncMock()
    out = await queue_mod._health_check({"redis": redis})
    assert out["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_redis_ping_fails() -> None:
    redis = AsyncMock()
    redis.ping = AsyncMock(side_effect=RuntimeError("down"))
    out = await queue_mod._health_check({"redis": redis})
    assert out["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_check_no_redis() -> None:
    out = await queue_mod._health_check({})
    assert out["status"] == "healthy"
