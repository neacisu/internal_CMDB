"""Redis-backed JWT token revocation.

Stores revoked JTI values in Redis with TTL equal to the remaining token
lifetime.  Fail-open: if Redis is unavailable, revocation is skipped and
a WARNING is logged (availability preferred over security for internal tool).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis

logger = logging.getLogger(__name__)

_PREFIX = "auth:revoked:"


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

    Returns False (fail-open) if Redis is unavailable.
    """
    client = _redis_client()
    if client is None:
        logger.warning("Redis unavailable — revocation check skipped for jti=%s", jti)
        return False

    try:
        return bool(client.exists(f"{_PREFIX}{jti}"))
    except Exception:
        logger.warning("Redis error — revocation check skipped for jti=%s", jti, exc_info=True)
        return False
