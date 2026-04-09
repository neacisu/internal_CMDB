"""F3.5 — Execution Lock (Idempotency Guard).

Distributed lock using Redis ``SET NX EX`` with ownership tokens to prevent
duplicate playbook executions on the same entity within a configurable
time window.

Usage::

    lock = ExecutionLock(redis_url="redis://…")
    token = await lock.acquire("host-07", "restart_container", window_seconds=300)
    if token:
        try:
            await run_playbook(…)
            await lock.extend(token, "host-07", "restart_container", extra_seconds=120)
        finally:
            await lock.release("host-07", "restart_container", token)
"""

from __future__ import annotations

import logging
import uuid

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_KEY_PREFIX = "infraq:execlock"


def _lock_key(entity_id: str, action_type: str) -> str:
    """Build the Redis key for a given entity + action pair."""
    safe_entity = entity_id.replace(":", "_")
    safe_action = action_type.replace(":", "_")
    return f"{_KEY_PREFIX}:{safe_entity}:{safe_action}"


class ExecutionLock:
    """Distributed idempotency lock backed by Redis SET NX EX with ownership tokens."""

    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def acquire(
        self,
        entity_id: str,
        action_type: str,
        window_seconds: int = 300,
    ) -> str | None:
        """Attempt to acquire the lock.

        Returns a unique ownership token if the lock was acquired,
        ``None`` if another execution is already in progress.

        The lock auto-expires after *window_seconds* to prevent orphan locks.
        """
        key = _lock_key(entity_id, action_type)
        token = str(uuid.uuid4())
        try:
            acquired = await self._redis.set(key, token, nx=True, ex=window_seconds)
        except Exception:
            logger.error(
                "Redis error acquiring lock: entity=%s action=%s — FAIL-CLOSED (lock denied)",
                entity_id,
                action_type,
                exc_info=True,
            )
            return None

        if acquired:
            logger.info(
                "Lock acquired: entity=%s action=%s window=%ds token=%s",
                entity_id,
                action_type,
                window_seconds,
                token[:8],
            )
            return token

        logger.warning(
            "Lock denied (already held): entity=%s action=%s",
            entity_id,
            action_type,
        )
        return None

    async def release(self, entity_id: str, action_type: str, token: str) -> bool:
        """Release the lock only if the caller holds the correct ownership token.

        Uses a Lua script for atomic compare-and-delete to avoid releasing
        a lock held by a different process.
        """
        key = _lock_key(entity_id, action_type)
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            result = await self._redis.eval(lua_script, 1, key, token)  # type: ignore[arg-type]
        except Exception:
            logger.error(
                "Redis error releasing lock: entity=%s action=%s",
                entity_id,
                action_type,
                exc_info=True,
            )
            return False

        if result:
            logger.info(
                "Lock released: entity=%s action=%s token=%s", entity_id, action_type, token[:8]
            )
            return True

        logger.warning(
            "Lock release denied (token mismatch or expired): entity=%s action=%s",
            entity_id,
            action_type,
        )
        return False

    async def extend(
        self,
        token: str,
        entity_id: str,
        action_type: str,
        extra_seconds: int = 300,
    ) -> bool:
        """Extend the lock TTL if the caller still holds it.

        Uses a Lua script for atomic compare-and-expire.
        """
        key = _lock_key(entity_id, action_type)
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        try:
            result = await self._redis.eval(lua_script, 1, key, token, str(extra_seconds))  # type: ignore[arg-type]
        except Exception:
            logger.error(
                "Redis error extending lock: entity=%s action=%s",
                entity_id,
                action_type,
                exc_info=True,
            )
            return False

        if result:
            logger.info(
                "Lock extended by %ds: entity=%s action=%s",
                extra_seconds,
                entity_id,
                action_type,
            )
            return True

        logger.warning(
            "Lock extend denied (token mismatch or expired): entity=%s action=%s",
            entity_id,
            action_type,
        )
        return False

    async def is_locked(self, entity_id: str, action_type: str) -> bool:
        """Check whether a lock is currently held (without acquiring)."""
        key = _lock_key(entity_id, action_type)
        try:
            return await self._redis.exists(key) > 0
        except Exception:
            logger.error(
                "Redis error checking lock: entity=%s action=%s",
                entity_id,
                action_type,
                exc_info=True,
            )
            return True  # fail-closed: assume locked

    async def close(self) -> None:
        """Close the underlying Redis connection."""
        await self._redis.aclose()
