"""internalCMDB — Audit Trail Middleware (Phase 4, F4.6).

Starlette-based middleware that logs every HTTP request/response pair to
``governance.audit_event``.  The middleware is intentionally lightweight —
it captures timing, actor identity, correlation ID, and status but does
**not** buffer request/response bodies (which could contain sensitive data).

Registration::

    from internalcmdb.api.middleware.audit import AuditMiddleware
    app.add_middleware(AuditMiddleware)
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_SKIP_PATHS = frozenset({"/health", "/api/docs", "/api/redoc", "/api/openapi.json", "/favicon.ico"})


class AuditMiddleware(BaseHTTPMiddleware):
    """Records an ``audit_event`` row for every API request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        from internalcmdb.observability.logging import set_correlation_id

        set_correlation_id(correlation_id)

        start = time.monotonic()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            status_code = response.status_code if response else 500

            try:
                from internalcmdb.observability.metrics import API_REQUEST_DURATION

                API_REQUEST_DURATION.labels(
                    method=request.method,
                    path=request.url.path,
                    status=str(status_code),
                ).observe(duration_ms / 1000)
            except Exception:
                pass

            await self._record(request, correlation_id, duration_ms, status_code)

    async def _record(
        self,
        request: Request,
        correlation_id: str,
        duration_ms: int,
        status_code: int,
    ) -> None:
        actor = _extract_actor(request)
        ip_address = _extract_ip(request)
        method = request.method
        path = request.url.path

        try:
            from internalcmdb.api.deps import _get_async_session_factory

            factory = _get_async_session_factory()
            async with factory() as session:
                from sqlalchemy import text

                await session.execute(
                    text("""
                        INSERT INTO governance.audit_event
                            (event_type, actor, action, target_entity,
                             correlation_id, duration_ms, status, ip_address)
                        VALUES
                            (:event_type, :actor, :action, :target_entity,
                             :correlation_id, :duration_ms, :status, :ip_address)
                    """),
                    {
                        "event_type": "http_request",
                        "actor": actor,
                        "action": f"{method} {path}",
                        "target_entity": path,
                        "correlation_id": correlation_id,
                        "duration_ms": duration_ms,
                        "status": str(status_code),
                        "ip_address": ip_address,
                    },
                )
                await session.commit()
        except Exception:
            logger.warning("Audit write failed — event lost (table may not exist yet)", exc_info=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_actor(request: Request) -> str | None:
    """Extract caller identity from the Authorization header or API key."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            import base64
            import json

            payload_b64 = token.split(".")[1]
            padding = 4 - len(payload_b64) % 4
            payload_b64 += "=" * padding
            claims: dict[str, Any] = json.loads(base64.urlsafe_b64decode(payload_b64))
            return claims.get("sub") or claims.get("preferred_username") or claims.get("email")
        except Exception:
            return "bearer-token-unreadable"
    if auth:
        return "authenticated"
    return request.headers.get("x-api-key-user")


def _extract_ip(request: Request) -> str | None:
    """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
