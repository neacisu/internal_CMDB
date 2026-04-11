"""internalCMDB — RBAC middleware (local JWT, no Zitadel).

Provides a ``require_role()`` FastAPI dependency factory that enforces
role-based access control using the local JWT tokens issued by the
internalCMDB auth module.

Usage::

    from internalcmdb.api.middleware.rbac import require_role

    @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    async def admin_only(): ...

Dev-mode: set ``AUTH_DEV_MODE=true`` (or ``1`` / ``yes``) to bypass all
role checks.  Only valid in non-production environments.
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, HTTPException, Request

from internalcmdb.auth.revocation import is_revoked
from internalcmdb.auth.security import decode_access_token

logger = logging.getLogger(__name__)

AUTH_DEV_MODE: bool = os.getenv("AUTH_DEV_MODE", "false").lower() in ("true", "1", "yes")

if AUTH_DEV_MODE:
    logger.warning(
        "RBAC AUTH_DEV_MODE is ACTIVE — all role checks are BYPASSED. "
        "Set AUTH_DEV_MODE=false for production."
    )


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------


def _get_auth_token(request: Request) -> str | None:
    """Return the JWT string from the session cookie, falling back to Bearer header."""
    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    cookie_val = request.cookies.get(settings.jwt_cookie_name)
    if cookie_val:
        return cookie_val

    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]

    return None


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------


def require_role(*required_roles: str):
    """FastAPI dependency factory — raises 403 if the caller lacks the role.

    Example::

        @router.post("/endpoint", dependencies=[Depends(require_role("admin", "operator"))])
        async def protected(): ...
    """

    def _check_role(
        request: Request,
        token: str | None = Depends(_get_auth_token),
    ) -> None:
        if AUTH_DEV_MODE:
            logger.debug("RBAC dev-mode: skipping role check for %s", required_roles)
            return

        if token is None:
            raise HTTPException(
                status_code=401,
                detail="Not authenticated.",
            )

        payload = decode_access_token(token)  # raises HTTP 401 on any failure

        if is_revoked(payload.jti):
            raise HTTPException(
                status_code=401,
                detail="Session has been revoked.",
            )

        required_lower = {r.lower() for r in required_roles}
        caller_role = payload.role.lower()
        # 'admin' is a super-role that satisfies any role requirement
        if caller_role != "admin" and caller_role not in required_lower:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Insufficient role: requires one of {sorted(required_lower)}, "
                    f"caller has '{payload.role}'."
                ),
            )

        request.state.rbac_role = payload.role
        request.state.rbac_sub = payload.sub

    return _check_role
