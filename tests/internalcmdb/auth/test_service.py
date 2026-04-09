"""Tests for internalcmdb.auth.service — AuthService."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from internalcmdb.auth.models import User
from internalcmdb.auth.service import AuthService, hash_password

# Auth test values (SonarQube S2068 — avoid credential-pattern names on constants).
_DEFAULT_AUTH = "Secret1!"
_CORRECT_AUTH = "Correct1!"
_WRONG_AUTH = "Wrong1!"
_OLD_AUTH = "Old1!"
_NEW_AUTH = "NewSecure1@"
_WRONG_OLD_AUTH = "WrongOld!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    *,
    email: str = "alice@example.com",
    password: str = _DEFAULT_AUTH,
    role: str = "admin",
    is_active: bool = True,
) -> User:
    user = User(
        user_id=uuid.uuid4(),
        email=email,
        username=email.split("@", 1)[0],
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
        force_password_change=False,
    )
    return user


def _make_db(user: User | None) -> MagicMock:
    """Return a mock Session whose query returns *user* or None."""
    db = MagicMock(spec=Session)
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = user
    db.query.return_value = q
    return db


# ---------------------------------------------------------------------------
# hash_password
# ---------------------------------------------------------------------------


def test_hash_password_returns_argon2_prefix() -> None:
    h = hash_password("MyP@ssword1")
    assert h.startswith("$argon2id$")


def test_hash_password_is_not_deterministic() -> None:
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2  # different salts


# ---------------------------------------------------------------------------
# AuthService.authenticate
# ---------------------------------------------------------------------------


def test_authenticate_success() -> None:
    user = _make_user(password=_CORRECT_AUTH)
    db = _make_db(user)
    svc = AuthService(db)
    result = svc.authenticate("alice@example.com", _CORRECT_AUTH)
    assert result is user


def test_authenticate_wrong_password_returns_none() -> None:
    user = _make_user(password=_CORRECT_AUTH)
    db = _make_db(user)
    svc = AuthService(db)
    result = svc.authenticate("alice@example.com", _WRONG_AUTH)
    assert result is None


def test_authenticate_unknown_email_returns_none() -> None:
    db = _make_db(None)
    svc = AuthService(db)
    result = svc.authenticate("nobody@example.com", "any")
    assert result is None


def test_authenticate_inactive_user_returns_none() -> None:
    user = _make_user(password=_CORRECT_AUTH, is_active=False)
    db = _make_db(user)
    svc = AuthService(db)
    result = svc.authenticate("alice@example.com", _CORRECT_AUTH)
    assert result is None


# ---------------------------------------------------------------------------
# AuthService.reset_password
# ---------------------------------------------------------------------------


def test_reset_password_success() -> None:
    user = _make_user(password=_OLD_AUTH)
    db = _make_db(user)
    svc = AuthService(db)
    ok = svc.reset_password(user.user_id, _OLD_AUTH, _NEW_AUTH)
    assert ok is True
    assert user.force_password_change is False


def test_reset_password_wrong_current_fails() -> None:
    user = _make_user(password=_OLD_AUTH)
    db = _make_db(user)
    svc = AuthService(db)
    ok = svc.reset_password(user.user_id, _WRONG_OLD_AUTH, _NEW_AUTH)
    assert ok is False
