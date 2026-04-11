"""JWT creation and verification for the local auth module.

Uses PyJWT (HS256) with a module-level sync cache for the secret key so
``decode_access_token`` can be called from both sync and async paths without
an active event loop.

The secret is loaded from ``os.environ["JWT_SECRET_KEY"]`` which the
lifespan hook populates from OpenBao / SecretProvider before any request is
accepted.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt
from fastapi import HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level sync secret cache — populated by lifespan from os.environ
# ---------------------------------------------------------------------------

_jwt_cache: list[str] = [""]
_JWT_SECRET_MIN_LEN: int = 32


def get_jwt_secret() -> str:
    """Return the JWT signing secret, loading from env on first call.

    Raises RuntimeError if the secret is absent or shorter than 32 chars.
    Must already be in ``os.environ["JWT_SECRET_KEY"]`` before any request
    is handled (lifespan guarantees this).
    """
    if not _jwt_cache[0]:
        _jwt_cache[0] = os.environ.get("JWT_SECRET_KEY") or ""
    if len(_jwt_cache[0]) < _JWT_SECRET_MIN_LEN:
        raise RuntimeError(
            f"JWT_SECRET_KEY must be \u2265{_JWT_SECRET_MIN_LEN} characters. "
            "Check OpenBao provisioning or .env file."
        )
    return _jwt_cache[0]


def invalidate_jwt_secret_cache() -> None:
    """Force the next call to get_jwt_secret() to reload from os.environ.

    Used by tests and key-rotation helpers.
    """
    _jwt_cache[0] = ""


# ---------------------------------------------------------------------------
# Token schemas
# ---------------------------------------------------------------------------


@dataclass
class TokenClaims:
    """Identity claims bundled for JWT creation.

    Groups all per-user claim fields so that ``create_access_token`` stays
    within the allowed argument count and callers have a typed, inspectable
    value object rather than a long positional argument list.
    """

    user_id: str
    email: str
    username: str
    role: str
    force_password_change: bool = False


class TokenPayload(BaseModel):
    sub: str
    email: str
    username: str
    role: str
    jti: str
    iat: int
    exp: int
    force_password_change: bool = False


# ---------------------------------------------------------------------------
# Token operations
# ---------------------------------------------------------------------------


def create_access_token(
    claims: TokenClaims,
    *,
    expire_minutes: int = 120,
) -> tuple[str, str, datetime]:
    """Create a signed HS256 JWT.

    Returns:
        (token_string, jti, expires_at)
    """
    jti = str(uuid.uuid4())
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=expire_minutes)

    payload: dict[str, Any] = {
        "sub": claims.user_id,
        "email": claims.email,
        "username": claims.username,
        "role": claims.role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "force_password_change": claims.force_password_change,
    }

    secret = get_jwt_secret()
    token = pyjwt.encode(payload, secret, algorithm="HS256")
    return token, jti, expires_at


def decode_access_token(token: str) -> TokenPayload:
    """Decode and verify a JWT.

    Raises HTTPException 401 on any failure — expired, tampered, malformed,
    missing secret.  Uses a 30-second leeway for clock skew tolerance.
    """
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        secret = get_jwt_secret()
    except RuntimeError as exc:
        logger.critical("JWT_SECRET_KEY not configured — cannot decode tokens")
        raise _401 from exc

    try:
        payload = pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            leeway=30,  # seconds — tolerates minor clock skew
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise _401 from exc
    except pyjwt.InvalidTokenError as exc:
        raise _401 from exc

    try:
        return TokenPayload(**payload)
    except Exception as exc:
        raise _401 from exc
