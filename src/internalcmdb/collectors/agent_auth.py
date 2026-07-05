"""Agent token generation, hashing, and Redis-backed signing cache."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis

logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "infraq:agent:token:"
_BOOTSTRAP_PREFIX = "discovery:bootstrap:"


def hash_agent_token(token: str) -> str:
    """Return a SHA-256 hex digest of *token*."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_agent_token() -> tuple[str, str]:
    """Return ``(plaintext_token, token_hash)``."""
    token = secrets.token_urlsafe(32)
    return token, hash_agent_token(token)


def verify_agent_token_hash(token: str, stored_hash: str) -> bool:
    """Timing-safe comparison of *token* against a stored SHA-256 hash."""
    expected = hash_agent_token(token)
    return hmac.compare_digest(expected, stored_hash)


def hash_bootstrap_token(token: str) -> str:
    """Hash a bootstrap enrollment token."""
    return hash_agent_token(token)


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


def cache_agent_token(agent_id: uuid.UUID, token: str) -> None:
    """Cache the plaintext agent token for server-side command signing."""
    client = _redis_client()
    if client is None:
        logger.warning("Redis unavailable — agent token not cached for %s", agent_id)
        return
    try:
        client.set(f"{_TOKEN_PREFIX}{agent_id}", token)
    except Exception:
        logger.warning("Redis error — agent token cache failed for %s", agent_id, exc_info=True)


def get_cached_agent_token(agent_id: uuid.UUID) -> str | None:
    """Return the cached plaintext agent token, if available."""
    client = _redis_client()
    if client is None:
        return None
    try:
        return client.get(f"{_TOKEN_PREFIX}{agent_id}")
    except Exception:
        logger.warning("Redis error — agent token lookup failed for %s", agent_id, exc_info=True)
        return None
