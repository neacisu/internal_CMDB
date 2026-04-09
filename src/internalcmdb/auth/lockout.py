"""Brute-force login lockout via Redis.

Tracks failed login attempts per (IP, email) pair with a sliding window.
After *MAX_ATTEMPTS* failures within *WINDOW_SECONDS* the account is locked.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from redis import Redis
    from starlette.requests import Request

logger = logging.getLogger(__name__)

_PREFIX = "auth:lockout:"
MAX_ATTEMPTS: int = 5
WINDOW_SECONDS: int = 900  # 15 minutes


def get_client_ip(request: Request) -> str:
    """Return the best-effort client IP from the request."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _key(ip: str, email: str) -> str:
    email_hash = hashlib.sha256(email.lower().encode()).hexdigest()[:16]
    return f"{_PREFIX}{ip}:{email_hash}"


def _redis_client() -> Redis | None:
    try:
        from redis import Redis as _Redis  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415

        url = get_settings().redis_url
        return _Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            url, decode_responses=True, socket_connect_timeout=2
        )
    except Exception:
        return None


def record_failed_attempt(ip: str, email: str) -> int:
    """Increment the failure counter and return the new count.

    Returns 0 (fail-open) if Redis is unavailable.
    """
    client = _redis_client()
    if client is None:
        logger.warning("Redis unavailable — lockout tracking skipped ip=%s", ip)
        return 0

    key = _key(ip, email)
    try:
        count = client.incr(key)
        # (Re)set TTL on every failure so the window slides forward.
        client.expire(key, WINDOW_SECONDS)
        return cast(int, count)  # sync Redis.incr() always returns int
    except Exception:
        logger.warning("Redis error — lockout tracking skipped ip=%s", ip, exc_info=True)
        return 0


def is_locked_out(ip: str, email: str) -> bool:
    """Return True if the (ip, email) pair has exceeded the failure threshold."""
    client = _redis_client()
    if client is None:
        logger.warning("Redis unavailable — lockout check skipped ip=%s", ip)
        return False

    try:
        raw = cast("str | None", client.get(_key(ip, email)))
        if raw is None:
            return False
        return int(raw) >= MAX_ATTEMPTS
    except Exception:
        logger.warning("Redis error — lockout check skipped ip=%s", ip, exc_info=True)
        return False


def clear_lockout(ip: str, email: str) -> None:
    """Remove the lockout record on successful login."""
    client = _redis_client()
    if client is None:
        return

    try:
        client.delete(_key(ip, email))
    except Exception:
        logger.warning("Redis error — lockout clear skipped ip=%s", ip, exc_info=True)
