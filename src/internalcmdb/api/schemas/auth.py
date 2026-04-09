"""Pydantic schemas for the auth module."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, SecretStr, field_validator

# ---------------------------------------------------------------------------
# Password policy constants (shared across LoginRequest and PasswordResetRequest)
# ---------------------------------------------------------------------------

_PASSWORD_MAX_LEN: int = 128  # bcrypt/Argon2 input cap; guards against DoS via huge inputs
_PASSWORD_MIN_LEN: int = 8  # NIST SP 800-63B minimum


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr

    @field_validator("password")
    @classmethod
    def _password_max_length(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) > _PASSWORD_MAX_LEN:
            raise ValueError("password too long")
        return v


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    user_id: UUID
    email: str
    username: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    force_password_change: bool


class PasswordResetRequest(BaseModel):
    current_password: SecretStr
    new_password: SecretStr

    @field_validator("new_password")
    @classmethod
    def _password_complexity(cls, v: SecretStr) -> SecretStr:
        pwd = v.get_secret_value()
        errors: list[str] = []
        if len(pwd) < _PASSWORD_MIN_LEN:
            errors.append("at least 8 characters")
        if not re.search(r"[A-Z]", pwd):
            errors.append("one uppercase letter")
        if not re.search(r"[a-z]", pwd):
            errors.append("one lowercase letter")
        if not re.search(r"\d", pwd):
            errors.append("one digit")
        if not re.search(r"[^A-Za-z0-9]", pwd):
            errors.append("one special character")
        if errors:
            raise ValueError("password must contain " + ", ".join(errors))
        return v
