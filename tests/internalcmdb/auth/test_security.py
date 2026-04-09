"""Tests for internalcmdb.auth.security."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from internalcmdb.auth.security import (
    TokenClaims,
    create_access_token,
    decode_access_token,
    get_jwt_secret,
    invalidate_jwt_secret_cache,
)

_SECRET = "a" * 32  # 32-char test secret


@pytest.fixture(autouse=True)
def jwt_secret_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("JWT_SECRET_KEY", _SECRET)
    invalidate_jwt_secret_cache()
    yield
    invalidate_jwt_secret_cache()


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------


def test_create_returns_three_tuple() -> None:
    token, jti, expires_at = create_access_token(
        TokenClaims(user_id="user-1", email="alice@example.com", username="alice", role="admin"),
    )
    assert isinstance(token, str)
    assert isinstance(jti, str)
    assert isinstance(expires_at, datetime)
    assert expires_at.tzinfo is not None


def test_token_expires_in_correct_window() -> None:
    before = datetime.now(UTC)
    _token, _jti, expires_at = create_access_token(
        TokenClaims(user_id="u", email="u@e.com", username="u", role="viewer"),
        expire_minutes=60,
    )
    after = datetime.now(UTC)
    assert before + timedelta(minutes=59) < expires_at <= after + timedelta(minutes=61)


def test_jti_is_unique_across_calls() -> None:
    _, jti1, _ = create_access_token(TokenClaims("u", "u@e.com", "u", "viewer"))
    _, jti2, _ = create_access_token(TokenClaims("u", "u@e.com", "u", "viewer"))
    assert jti1 != jti2


# ---------------------------------------------------------------------------
# decode_access_token
# ---------------------------------------------------------------------------


def test_roundtrip_encode_decode() -> None:
    token, jti, _ = create_access_token(
        TokenClaims(
            user_id="user-42",
            email="bob@example.com",
            username="bob",
            role="operator",
            force_password_change=True,
        ),
    )
    payload = decode_access_token(token)
    assert payload.sub == "user-42"
    assert payload.email == "bob@example.com"
    assert payload.username == "bob"
    assert payload.role == "operator"
    assert payload.jti == jti
    assert payload.force_password_change is True


def test_decode_raises_401_on_invalid_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("not.a.valid.token")
    assert exc_info.value.status_code == 401


def test_decode_raises_401_on_wrong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    token, _, _ = create_access_token(TokenClaims("u", "u@e.com", "u", "admin"))

    monkeypatch.setenv("JWT_SECRET_KEY", "b" * 32)
    invalidate_jwt_secret_cache()

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_decode_raises_401_on_expired_token() -> None:
    token, _, _ = create_access_token(TokenClaims("u", "u@e.com", "u", "admin"), expire_minutes=-1)
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_jwt_secret validation
# ---------------------------------------------------------------------------


def test_get_jwt_secret_raises_if_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    invalidate_jwt_secret_cache()
    with pytest.raises(RuntimeError, match="32"):
        get_jwt_secret()


def test_get_jwt_secret_raises_if_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    invalidate_jwt_secret_cache()
    with pytest.raises(RuntimeError):
        get_jwt_secret()
