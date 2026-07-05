"""JWT creation and verification for the local auth module.

Uses PyJWT (HS256) with a module-level sync cache for the secret key ring so
``decode_access_token`` can be called from both sync and async paths without
an active event loop.

The ring is populated by the lifespan hook from OpenBao / SecretProvider
before any request is accepted.  Signing always uses the first (current) key;
verification tries every key in the ring for zero-downtime rotation.
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
# Module-level sync secret ring — populated by lifespan from SecretProvider
# ---------------------------------------------------------------------------

_jwt_ring: list[str] = [""]
_JWT_SECRET_MIN_LEN: int = 32


def set_jwt_secret_ring(ring: list[str]) -> None:
    """Install the JWT verification ring (current key first)."""
    global _jwt_ring  # noqa: PLW0603
    validated = [key for key in ring if key and len(key) >= _JWT_SECRET_MIN_LEN]
    if not validated:
        raise RuntimeError(
            f"JWT secret ring must contain at least one key of "
            f"\u2265{_JWT_SECRET_MIN_LEN} characters."
        )
    _jwt_ring = validated
    os.environ["JWT_SECRET_KEY"] = validated[0]


def get_jwt_secret() -> str:
    """Return the current JWT signing secret (first key in the ring).

    Raises RuntimeError if the secret is absent or shorter than 32 chars.
    Falls back to ``os.environ["JWT_SECRET_KEY"]`` when the ring is empty.
    """
    if not _jwt_ring or not _jwt_ring[0]:
        env_secret = os.environ.get("JWT_SECRET_KEY") or ""
        if env_secret:
            set_jwt_secret_ring([env_secret])
    if not _jwt_ring or len(_jwt_ring[0]) < _JWT_SECRET_MIN_LEN:
        raise RuntimeError(
            f"JWT_SECRET_KEY must be \u2265{_JWT_SECRET_MIN_LEN} characters. "
            "Check OpenBao provisioning or .env file."
        )
    return _jwt_ring[0]


def get_jwt_secret_ring() -> list[str]:
    """Return a copy of the active JWT verification ring."""
    get_jwt_secret()
    return list(_jwt_ring)


def invalidate_jwt_secret_cache() -> None:
    """Clear the in-memory JWT ring so the next access reloads secrets."""
    global _jwt_ring  # noqa: PLW0603
    _jwt_ring = [""]


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
    """Decode and verify a JWT against every key in the ring.

    Raises HTTPException 401 on any failure — expired, tampered, malformed,
    missing secret.  Uses a 30-second leeway for clock skew tolerance.
    """
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        ring = get_jwt_secret_ring()
    except RuntimeError as exc:
        logger.critical("JWT_SECRET_KEY not configured — cannot decode tokens")
        raise _401 from exc

    last_error: Exception | None = None
    for secret in ring:
        try:
            payload = pyjwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                leeway=30,
            )
            return TokenPayload(**payload)
        except pyjwt.ExpiredSignatureError as exc:
            raise _401 from exc
        except pyjwt.InvalidTokenError as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            continue

    raise _401 from last_error
