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

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

try:
    from internalcmdb.observability.logging import set_correlation_id
except ImportError:  # pragma: no cover — missing in minimal test envs

    def set_correlation_id(cid: str | None) -> None:  # type: ignore[misc]
        pass


logger = logging.getLogger(__name__)

_SKIP_PATHS = frozenset({"/health", "/api/docs", "/api/redoc", "/api/openapi.json", "/favicon.ico"})


class AuditMiddleware(BaseHTTPMiddleware):
    """Records an ``audit_event`` row for every API request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

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
                from internalcmdb.observability.metrics import API_REQUEST_DURATION  # noqa: PLC0415

                API_REQUEST_DURATION.labels(
                    method=request.method,
                    path=request.url.path,
                    status=str(status_code),
                ).observe(duration_ms / 1000)
            except Exception:
                logger.debug("Metrics observation skipped", exc_info=True)

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
            from internalcmdb.api.deps import _get_async_session_factory  # noqa: PLC0415

            factory = _get_async_session_factory()
            async with factory() as session:
                from sqlalchemy import text  # noqa: PLC0415

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
            logger.warning(
                "Audit write failed — event lost (table may not exist yet)",
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_actor(request: Request) -> str | None:
    """Extract caller identity from the session cookie first, then Bearer header."""
    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    settings = get_settings()

    # 1. Try session cookie (preferred — local JWT auth)
    cookie_val = request.cookies.get(settings.jwt_cookie_name)
    if cookie_val:
        try:
            from internalcmdb.auth.security import decode_access_token  # noqa: PLC0415

            payload = decode_access_token(cookie_val)
            return payload.sub
        except Exception:
            logger.debug("Malformed session cookie, falling through", exc_info=True)

    # 2. Fall back to Bearer header — verified HMAC decode only; untrusted tokens
    #    must NOT contribute identity to the audit trail (OWASP ASVS 8.3.7).
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            from internalcmdb.auth.security import decode_access_token  # noqa: PLC0415

            payload = decode_access_token(token)
            return payload.sub
        except Exception:
            # Signature invalid, expired, or malformed — record the state accurately;
            # do NOT trust any claim from an unverified token.
            return "bearer-token-unverified"

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
