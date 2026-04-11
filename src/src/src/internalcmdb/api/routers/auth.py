"""Router: auth — local JWT authentication."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from internalcmdb.auth.models import User

from internalcmdb.auth.lockout import (
    MAX_ATTEMPTS,
    clear_lockout,
    get_client_ip,
    is_locked_out,
    record_failed_attempt,
)
from internalcmdb.auth.revocation import revoke_token
from internalcmdb.auth.security import TokenClaims, create_access_token, decode_access_token
from internalcmdb.auth.service import AuthService
from internalcmdb.observability.metrics import (
    LOCKOUT_TRIGGERED,
    LOGIN_FAILURE,
    LOGIN_SUCCESS,
    TOKEN_REVOCATIONS,
)

from ..config import get_settings
from ..deps import get_current_user, get_db
from ..middleware.rate_limit import rate_limit
from ..schemas.auth import LoginRequest, PasswordResetRequest, UserOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post("/login")
@rate_limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    """Authenticate with email + password; set httpOnly session cookie."""
    settings = get_settings()
    email = body.email.lower()
    ip = get_client_ip(request)

    if is_locked_out(ip, email):
        LOGIN_FAILURE.labels(reason="account_locked").inc()
        LOCKOUT_TRIGGERED.inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    svc = AuthService(db)
    user = svc.authenticate(email, body.password.get_secret_value())

    if user is None:
        count = record_failed_attempt(ip, email)
        LOGIN_FAILURE.labels(reason="wrong_pwd").inc()
        if count >= MAX_ATTEMPTS:
            LOCKOUT_TRIGGERED.inc()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Try again in 15 minutes.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    clear_lockout(ip, email)
    svc.update_last_login(user.user_id)

    token, _jti, expires_at = create_access_token(
        TokenClaims(
            user_id=str(user.user_id),
            email=user.email,
            username=user.username,
            role=user.role,
            force_password_change=user.force_password_change,
        ),
        expire_minutes=settings.jwt_access_token_expire_minutes,
    )

    LOGIN_SUCCESS.labels(role=user.role).inc()

    response.set_cookie(
        key=settings.jwt_cookie_name,
        value=token,
        httponly=settings.jwt_cookie_httponly,
        secure=settings.jwt_cookie_secure,
        samesite=settings.jwt_cookie_samesite,
        expires=int((expires_at - datetime.now(UTC)).total_seconds()),
        path="/",
    )

    return {"force_password_change": user.force_password_change}


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> None:
    """Revoke the current session token and clear the cookie."""
    settings = get_settings()
    cookie_val = request.cookies.get(settings.jwt_cookie_name)
    if cookie_val:
        try:
            payload = decode_access_token(cookie_val)
            expires_at = datetime.fromtimestamp(payload.exp, tz=UTC)
            revoke_token(payload.jti, expires_at)
            TOKEN_REVOCATIONS.labels(reason="logout").inc()
        except Exception:
            logger.debug(
                "Token invalid/expired during logout, clearing cookie anyway",
                exc_info=True,
            )

    response.delete_cookie(
        key=settings.jwt_cookie_name,
        path="/",
        httponly=True,
        secure=settings.jwt_cookie_secure,
        samesite=settings.jwt_cookie_samesite,
    )


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserOut)
async def me(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserOut:
    """Return the authenticated user's profile."""
    return UserOut.model_validate(current_user)


# ---------------------------------------------------------------------------
# POST /auth/password-reset
# ---------------------------------------------------------------------------


@router.post("/password-reset", status_code=status.HTTP_204_NO_CONTENT)
async def password_reset(
    request: Request,
    body: PasswordResetRequest,
    response: Response,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> None:
    """Reset the authenticated user's password."""
    settings = get_settings()
    svc = AuthService(db)
    ok = svc.reset_password(
        user_id=current_user.user_id,
        current_password=body.current_password.get_secret_value(),
        new_password=body.new_password.get_secret_value(),
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    # Invalidate current session so the user must re-login with the new password.
    cookie_val = request.cookies.get(settings.jwt_cookie_name)
    if cookie_val:
        try:
            payload = decode_access_token(cookie_val)
            expires_at = datetime.fromtimestamp(payload.exp, tz=UTC)
            revoke_token(payload.jti, expires_at)
            TOKEN_REVOCATIONS.labels(reason="password_change").inc()
        except Exception:
            logger.debug("Token invalid during password_reset, clearing cookie", exc_info=True)

    response.delete_cookie(
        key=settings.jwt_cookie_name,
        path="/",
        httponly=True,
        secure=settings.jwt_cookie_secure,
        samesite=settings.jwt_cookie_samesite,
    )
