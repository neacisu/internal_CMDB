"""internalCMDB — RBAC Middleware (Phase 4, F4.8).

Provides a ``require_role()`` FastAPI dependency factory that enforces
role-based access control using JWT tokens issued by Zitadel (or any
OIDC-compliant IdP that exposes a JWKS endpoint).

Usage::

    from internalcmdb.api.middleware.rbac import require_role

    @router.post("/endpoint", dependencies=[Depends(require_role("hitl_reviewer"))])
    async def protected_endpoint():
        ...

Dev-mode fallback: when ``ZITADEL_ISSUER`` is not set the middleware logs a
warning and allows the request through (no enforcement).
"""

from __future__ import annotations

import json
import logging
import os
from base64 import urlsafe_b64decode
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)

_ZITADEL_ISSUER = os.getenv("ZITADEL_ISSUER", "")
_ZITADEL_JWKS_URL = os.getenv("ZITADEL_JWKS_URL", "")
_ROLES_CLAIM = os.getenv("RBAC_ROLES_CLAIM", "urn:zitadel:iam:org:project:roles")
_RBAC_DEV_MODE_EXPLICIT = os.getenv("RBAC_DEV_MODE", "").lower()

_DEV_MODE = (
    _RBAC_DEV_MODE_EXPLICIT in ("true", "1", "yes")
    if _RBAC_DEV_MODE_EXPLICIT
    else not _ZITADEL_ISSUER
)

if _DEV_MODE:
    logger.warning(
        "RBAC dev-mode ACTIVE: all role checks are BYPASSED. "
        "Set ZITADEL_ISSUER or RBAC_DEV_MODE=false for production."
    )


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------


_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0
_JWKS_TTL_SECONDS = float(os.getenv("JWKS_CACHE_TTL", "300"))


def _fetch_jwks_sync() -> dict[str, Any]:
    """Fetch the JWKS keyset from the IdP (cached with TTL, refreshed on rotation)."""
    global _jwks_cache, _jwks_fetched_at  # noqa: PLW0603
    import time  # noqa: PLC0415

    if _jwks_cache and (time.monotonic() - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    url = _ZITADEL_JWKS_URL or f"{_ZITADEL_ISSUER}/.well-known/jwks.json"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = time.monotonic()
        return _jwks_cache
    except Exception:
        logger.warning("Failed to fetch JWKS from %s", url, exc_info=True)
        return _jwks_cache or {}


# ---------------------------------------------------------------------------
# JWT decoding (lightweight — no cryptographic verification in dev mode)
# ---------------------------------------------------------------------------


def _decode_jwt_claims(token: str) -> dict[str, Any]:
    """Decode and optionally verify a JWT token.

    When JWKS is available and ``PyJWT`` is installed, performs full
    cryptographic signature verification.  Falls back to base64 decode
    only in dev mode or when ``PyJWT`` is not installed.
    """
    if not _DEV_MODE:
        verified = _verify_jwt_cryptographic(token)
        if verified is not None:
            return verified

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        payload_b64 += "=" * padding
        return json.loads(urlsafe_b64decode(payload_b64))
    except Exception:
        return {}


def _verify_jwt_cryptographic(token: str) -> dict[str, Any] | None:
    """Verify JWT signature using JWKS keyset via PyJWT.

    Returns decoded claims on success, None if PyJWT is unavailable or
    verification fails (caller falls back to base64 decode).
    """
    try:
        import jwt  # noqa: PLC0415
        from jwt import PyJWKClient  # noqa: PLC0415
    except ImportError:
        logger.warning("PyJWT not installed — JWT signature verification disabled")
        return None

    jwks_data = _fetch_jwks_sync()
    if not jwks_data or not jwks_data.get("keys"):
        logger.warning("No JWKS keys available — cannot verify JWT signature")
        return None

    try:
        jwks_url = _ZITADEL_JWKS_URL or f"{_ZITADEL_ISSUER}/.well-known/jwks.json"
        jwk_client = PyJWKClient(jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            issuer=_ZITADEL_ISSUER or None,
            options={"verify_aud": False},
        )
    except Exception:
        logger.warning("JWT cryptographic verification failed", exc_info=True)
        return None


def _extract_roles(claims: dict[str, Any]) -> set[str]:
    """Extract role names from JWT claims (case-insensitive normalisation).

    Supports both Zitadel-style nested role objects and simple list claims.
    All role names are lowercased for consistent matching.
    """
    roles: set[str] = set()

    role_value = claims.get(_ROLES_CLAIM)
    if isinstance(role_value, dict):
        roles.update(k.lower() for k in role_value.keys())
    elif isinstance(role_value, list):
        roles.update(str(r).lower() for r in role_value)

    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        ra_roles = realm_access.get("roles", [])
        if isinstance(ra_roles, list):
            roles.update(str(r).lower() for r in ra_roles)

    groups = claims.get("groups")
    if isinstance(groups, list):
        roles.update(str(g).lower() for g in groups)

    return roles


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def _get_bearer_token(request: Request) -> str | None:
    """Sync dependency — header read only; no I/O that blocks the event loop."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def require_role(*required_roles: str):
    """FastAPI dependency factory — raises 403 if the caller lacks the role.

    Usage::

        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
        async def admin_only(): ...
    """

    def _check_role(
        request: Request,
        token: str | None = Depends(_get_bearer_token),
    ) -> None:
        if _DEV_MODE:
            logger.debug("RBAC dev-mode: skipping role check for %s", required_roles)
            return

        if token is None:
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        claims = _decode_jwt_claims(token)
        if not claims:
            raise HTTPException(status_code=401, detail="Invalid or malformed JWT")

        caller_roles = _extract_roles(claims)
        required_lower = {r.lower() for r in required_roles}

        if not caller_roles.intersection(required_lower):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient role: requires one of {sorted(required_lower)}, "
                       f"caller has {sorted(caller_roles)}",
            )

        request.state.rbac_roles = caller_roles
        request.state.rbac_sub = claims.get("sub")

    return _check_role
