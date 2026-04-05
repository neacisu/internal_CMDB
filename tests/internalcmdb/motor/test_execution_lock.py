"""Tests for motor.execution_lock — ExecutionLock."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch
import pytest
from internalcmdb.motor.execution_lock import ExecutionLock


def _make_lock() -> tuple[ExecutionLock, AsyncMock]:
    """Construct an ExecutionLock with an injected mock Redis client."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.eval = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.aclose = AsyncMock()

    with patch("internalcmdb.motor.execution_lock.Redis") as mock_cls:
        mock_cls.from_url.return_value = redis
        lock = ExecutionLock("redis://localhost:6379")

    return lock, redis


@pytest.mark.asyncio
async def test_acquire_success():
    lock, redis = _make_lock()
    redis.set.return_value = True
    token = await lock.acquire("entity-001", "shutdown")
    assert token is not None
    assert isinstance(token, str)


@pytest.mark.asyncio
async def test_acquire_already_locked():
    lock, redis = _make_lock()
    redis.set.return_value = None
    token = await lock.acquire("entity-001", "shutdown")
    assert token is None


@pytest.mark.asyncio
async def test_acquire_redis_error_returns_none():
    lock, redis = _make_lock()
    redis.set.side_effect = RuntimeError("redis unavailable")
    token = await lock.acquire("entity-001", "shutdown")
    assert token is None


@pytest.mark.asyncio
async def test_release_success():
    lock, redis = _make_lock()
    redis.set.return_value = True
    redis.eval.return_value = 1
    token = await lock.acquire("entity-001", "shutdown")
    assert token is not None
    result = await lock.release("entity-001", "shutdown", token)
    assert result is True


@pytest.mark.asyncio
async def test_release_not_owner():
    lock, redis = _make_lock()
    redis.eval.return_value = 0
    result = await lock.release("entity-001", "shutdown", "wrong-token")
    assert result is False


@pytest.mark.asyncio
async def test_release_redis_error():
    lock, redis = _make_lock()
    redis.eval.side_effect = RuntimeError("redis down")
    result = await lock.release("entity-001", "shutdown", "some-token")
    assert result is False


@pytest.mark.asyncio
async def test_is_locked_true():
    lock, redis = _make_lock()
    redis.exists.return_value = 1
    result = await lock.is_locked("entity-001", "shutdown")
    assert result is True


@pytest.mark.asyncio
async def test_is_locked_false():
    lock, redis = _make_lock()
    redis.exists.return_value = 0
    result = await lock.is_locked("entity-001", "shutdown")
    assert result is False


@pytest.mark.asyncio
async def test_is_locked_redis_error_fail_closed():
    lock, redis = _make_lock()
    redis.exists.side_effect = RuntimeError("redis down")
    result = await lock.is_locked("entity-001", "shutdown")
    assert result is True  # fail-closed


@pytest.mark.asyncio
async def test_extend_success():
    lock, redis = _make_lock()
    redis.set.return_value = True
    redis.eval.return_value = 1
    token = await lock.acquire("entity-001", "shutdown")
    assert token is not None
    # signature: extend(token, entity_id, action_type, extra_seconds)
    result = await lock.extend(token, "entity-001", "shutdown", 30)
    assert result is True


@pytest.mark.asyncio
async def test_extend_not_owner():
    lock, redis = _make_lock()
    redis.eval.return_value = 0
    result = await lock.extend("wrong-token", "entity-001", "shutdown", 30)
    assert result is False


@pytest.mark.asyncio
async def test_extend_redis_error():
    lock, redis = _make_lock()
    redis.eval.side_effect = RuntimeError("redis down")
    result = await lock.extend("some-token", "entity-001", "shutdown", 30)
    assert result is False


@pytest.mark.asyncio
async def test_close_no_error():
    lock, redis = _make_lock()
    await lock.close()
    redis.aclose.assert_called()
