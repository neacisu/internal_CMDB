"""internalCMDB — Rate Limiting Middleware (Phase 16, F16.3).

Uses slowapi to enforce per-endpoint rate limits keyed by agent ID or
client IP.  When Redis is reachable the limiter shares counters across
workers; otherwise it falls back to in-memory storage with a warning.

Registration::

    from internalcmdb.api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, cast

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = frozenset(
    {
        "/health",
        "/metrics",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    }
)


def _key_func(request: Request) -> str:
    """Extract rate-limit key: prefer X-Agent-ID, then X-Forwarded-For, then client IP."""
    if request.url.path in _EXEMPT_PATHS:
        return "exempt"
    agent_id = request.headers.get("x-agent-id")
    if agent_id:
        return f"agent:{agent_id}"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "anonymous"


def _build_storage_uri() -> str | None:
    """Resolve a Redis URI for shared rate-limit counters across workers.

    Falls back to in-memory storage when REDIS_URL is unset or when the
    URL scheme is not supported by limits (e.g. ``rediss://`` with
    client-cert auth is fine, but totally custom schemes are not).
    """
    rate_limit_redis = os.getenv("RATE_LIMIT_REDIS_URL", "")
    if rate_limit_redis:
        return rate_limit_redis

    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        logger.warning(
            "REDIS_URL not set — rate-limit counters are per-worker (in-memory). "
            "Set REDIS_URL for shared counters in multi-worker deployments."
        )
        return None
    if not re.match(r"^rediss?://", redis_url):
        logger.warning("REDIS_URL scheme unsupported by rate limiter; using in-memory storage")
        return None
    return redis_url


def _safe_build_storage_uri() -> str | None:
    """Try Redis, fall back to in-memory if connectivity fails."""
    uri = _build_storage_uri()
    if uri is None:
        return None
    try:
        from redis import Redis as _Redis  # noqa: PLC0415

        client = _Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            uri, socket_connect_timeout=3
        )
        client.ping()  # pyright: ignore[reportUnknownMemberType]
        test_key = "internalcmdb:rate_limit:probe"
        client.set(test_key, "1", ex=10)
        client.delete(test_key)
        return uri
    except Exception as exc:
        logger.warning(
            "Redis rate-limit storage unreachable (%s) — falling back to in-memory.",
            exc,
        )
        return None


_storage_uri = _safe_build_storage_uri()

limiter = Limiter(
    key_func=_key_func,
    storage_uri=_storage_uri,  # type: ignore[arg-type]
    default_limits=["200/minute"],
)

_P = ParamSpec("_P")
_R = TypeVar("_R")


def rate_limit(limit_string: str) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Type-safe wrapper around slowapi Limiter.limit() for Pylance compatibility.

    slowapi does not ship complete PEP 561 stubs — ``Limiter.limit()`` returns
    a decorator whose type is ``Unknown`` to Pylance, triggering both
    ``reportUntypedFunctionDecorator`` and ``reportUnknownMemberType`` in
    strict-mode analysis.  This wrapper absorbs the single suppression comment
    and re-exports a fully-typed ``Callable`` that preserves the decorated
    function's complete signature via ``ParamSpec``.
    """
    # cast() overrides Pylance's inference at the assignment site — the only
    # correct tool when a third-party call returns Unknown due to incomplete
    # PEP 561 stubs.  The pyright suppression on the inner call covers
    # reportUnknownMemberType; cast() covers reportUnknownVariableType by
    # telling Pylance the concrete type we know the decorator to have.
    raw_decorator = cast(
        Callable[[Callable[_P, _R]], Callable[_P, _R]],
        limiter.limit(limit_string),  # pyright: ignore[reportUnknownMemberType]
    )

    def _typed_decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        return raw_decorator(func)

    return _typed_decorator


RATE_LIMITS: dict[str, str] = {
    "/api/v1/auth/login": "10/minute",
    "/api/v1/collectors/ingest": "60/minute",
    "/api/v1/cognitive/query": "10/minute",
    "/api/v1/hitl/bulk-decide": "5/minute",
}


def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> Response:
    """Return 429 with Retry-After header derived from the limit window."""
    retry_match = re.search(r"(\d+) per (\d+) (\w+)", str(exc.detail))
    if retry_match:
        window_seconds = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }.get(retry_match.group(3), 60)
        retry_after = str(int(retry_match.group(2)) * window_seconds)
    else:
        retry_after = "60"

    logger.warning("Rate limit exceeded: %s", exc.detail)
    return Response(
        content=f'{{"detail": "Rate limit exceeded: {exc.detail}"}}',
        status_code=429,
        media_type="application/json",
        headers={"Retry-After": retry_after},
    )


def get_rate_limit_decorators() -> dict[str, Any]:
    """Return a mapping of path → limiter.limit decorator for router-level use."""
    return {path: limiter.limit(limit) for path, limit in RATE_LIMITS.items()}  # pyright: ignore[reportUnknownMemberType]
