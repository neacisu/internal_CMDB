"""Global deny-by-default authentication middleware.

Every request must present a valid, non-revoked JWT unless the path is on
the explicit allowlist or uses agent HMAC authentication at the route level.

Sets ``request.state.rbac_sub`` and ``request.state.rbac_role`` on success.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from internalcmdb.auth.revocation import is_revoked
from internalcmdb.auth.security import decode_access_token
from internalcmdb.auth.spiffe import SpiffeJwtValidator

from .rbac import AUTH_DEV_MODE

if TYPE_CHECKING:
    from internalcmdb.auth.security import TokenPayload

logger = logging.getLogger(__name__)

_UNAUTH_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/metrics",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
        "/api/v1/auth/login",
    }
)

_AGENT_HMAC_PATHS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^/api/v1/collectors/enroll$"),
    re.compile(r"^/api/v1/collectors/ingest$"),
    re.compile(r"^/api/v1/collectors/heartbeat$"),
    re.compile(r"^/api/v1/agent-commands/[^/]+/commands/[^/]+/result$"),
)

_SSE_CHAT_STREAM = "/api/v1/cognitive/chat/stream"

_PASSWORD_CHANGE_ALLOWED: frozenset[str] = frozenset(
    {
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
        "/api/v1/auth/password-reset",
        "/api/v1/auth/verify",
        "/api/v1/auth/login",
    }
)


def _is_agent_hmac_path(path: str) -> bool:
    return any(pattern.match(path) for pattern in _AGENT_HMAC_PATHS)


async def _spiffe_gate(request: Request) -> Response | None:
    """Fail-closed SPIFFE check for collector agent paths when enabled."""
    if not SpiffeJwtValidator.is_enabled():
        return None
    if not _is_agent_hmac_path(request.url.path):
        return None
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "SPIFFE auth required"})
    validator = SpiffeJwtValidator()
    try:
        await validator.validate(auth)
    except Exception as exc:
        logger.warning("SPIFFE validation failed: %s", exc)
        return JSONResponse(status_code=401, content={"detail": "Invalid SPIFFE credentials"})
    return None


def _extract_token(request: Request) -> str | None:
    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    cookie_val = request.cookies.get(settings.jwt_cookie_name)
    if cookie_val:
        return cookie_val

    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]

    if request.url.path == _SSE_CHAT_STREAM:
        query_token = request.query_params.get("token")
        if query_token:
            return query_token

    return None


def _authenticate(request: Request) -> TokenPayload | JSONResponse:
    token = _extract_token(request)
    if not token:
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    if is_revoked(payload.jti):
        return JSONResponse(
            status_code=401,
            content={"detail": "Session has been revoked."},
        )

    return payload


class GlobalAuthMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests unless the path is explicitly public."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        if path in _UNAUTH_PATHS or _is_agent_hmac_path(path):
            spiffe_response = await _spiffe_gate(request)
            if spiffe_response is not None:
                return spiffe_response
            return await call_next(request)

        if AUTH_DEV_MODE:
            request.state.rbac_sub = "dev"
            request.state.rbac_role = "admin"
            request.state.rbac_force_password_change = False
            return await call_next(request)

        auth_result = _authenticate(request)
        if isinstance(auth_result, JSONResponse):
            return auth_result

        payload = auth_result
        request.state.rbac_sub = payload.sub
        request.state.rbac_role = payload.role
        request.state.rbac_force_password_change = payload.force_password_change

        if payload.force_password_change and path not in _PASSWORD_CHANGE_ALLOWED:
            return JSONResponse(
                status_code=403,
                content={"detail": "Password change required before accessing this resource."},
            )

        return await call_next(request)
