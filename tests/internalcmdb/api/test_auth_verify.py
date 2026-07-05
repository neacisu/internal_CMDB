"""Tests for GET /auth/verify."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.auth.security import TokenClaims, create_access_token, invalidate_jwt_secret_cache

_SECRET = "v" * 32


@pytest.fixture(autouse=True)
def jwt_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("JWT_SECRET_KEY", _SECRET)
    invalidate_jwt_secret_cache()
    yield
    invalidate_jwt_secret_cache()


@pytest.fixture
def client() -> TestClient:
    from internalcmdb.api.routers.auth import router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app, raise_server_exceptions=False)


def test_verify_without_cookie_returns_401(client: TestClient) -> None:
    assert client.get("/api/v1/auth/verify").status_code == 401


def test_verify_with_valid_cookie_returns_claims(client: TestClient) -> None:
    token, _, _ = create_access_token(
        TokenClaims(
            user_id="uid-1",
            email="u@example.com",
            username="u",
            role="admin",
            force_password_change=True,
        )
    )
    with patch("internalcmdb.auth.revocation.is_revoked", return_value=False):
        resp = client.get("/api/v1/auth/verify", cookies={"cmdb_session": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sub"] == "uid-1"
    assert data["role"] == "admin"
    assert data["force_password_change"] is True


def test_verify_revoked_session_returns_401(client: TestClient) -> None:
    token, _, _ = create_access_token(
        TokenClaims(user_id="uid-2", email="x@example.com", username="x", role="viewer")
    )
    with patch("internalcmdb.auth.revocation.is_revoked", return_value=True):
        resp = client.get("/api/v1/auth/verify", cookies={"cmdb_session": token})
    assert resp.status_code == 401
