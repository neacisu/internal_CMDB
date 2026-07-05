"""Redis-backed JWT token revocation.

Stores revoked JTI values in Redis with TTL equal to the remaining token
lifetime.  Fail-closed: if Redis is unavailable, tokens are treated as revoked.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis

logger = logging.getLogger(__name__)

_PREFIX = "infraq:auth:revoked:"


def _redis_client() -> Redis | None:
    """Lazy import of the shared Redis client to avoid circular imports."""
    try:
        from redis import Redis as _Redis  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415

        url = get_settings().redis_url
        return _Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            url, decode_responses=True, socket_connect_timeout=2
        )
    except Exception:
        return None


def revoke_token(jti: str, expires_at: datetime) -> None:
    """Add *jti* to the revocation set, expiring when the token would expire."""
    now = datetime.now(UTC)
    remaining = int((expires_at - now).total_seconds())
    if remaining <= 0:
        return  # already expired — nothing to revoke

    client = _redis_client()
    if client is None:
        logger.warning("Redis unavailable — token revocation skipped for jti=%s", jti)
        return

    try:
        client.setex(f"{_PREFIX}{jti}", remaining, "1")
    except Exception:
        logger.warning("Redis error — token revocation skipped for jti=%s", jti, exc_info=True)


def is_revoked(jti: str) -> bool:
    """Return True if *jti* has been revoked.

    Fail-closed when Redis is hard-down in production.  Transient loading errors
    fail open so sessions remain usable during Redis recovery.
    """
    from internalcmdb.config.secrets import is_production_env  # noqa: PLC0415

    client = _redis_client()
    if client is None:
        if is_production_env():
            logger.warning("Redis unavailable — treating jti=%s as revoked (fail-closed)", jti)
            return True
        logger.warning("Redis unavailable — revocation check skipped jti=%s (dev fail-open)", jti)
        return False

    try:
        return bool(client.exists(f"{_PREFIX}{jti}"))
    except Exception as exc:
        exc_name = type(exc).__name__
        if exc_name in ("BusyLoadingError", "ConnectionError", "TimeoutError"):
            logger.warning(
                "Redis transient error (%s) — revocation skipped jti=%s", exc_name, jti
            )
            return False
        if is_production_env():
            logger.warning(
                "Redis error — treating jti=%s as revoked (fail-closed)", jti, exc_info=True
            )
            return True
        logger.warning(
            "Redis error — revocation check skipped jti=%s (dev fail-open)", jti, exc_info=True
        )
        return False
