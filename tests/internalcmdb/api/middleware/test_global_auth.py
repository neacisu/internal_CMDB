"""Tests for global deny-by-default auth middleware."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.auth.security import TokenClaims, create_access_token, invalidate_jwt_secret_cache
from internalcmdb.api.middleware import global_auth as ga_mod

_SECRET = "g" * 32


@pytest.fixture(autouse=True)
def jwt_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", _SECRET)
    monkeypatch.setattr(ga_mod, "AUTH_DEV_MODE", False, raising=False)
    invalidate_jwt_secret_cache()
    yield
    invalidate_jwt_secret_cache()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ga_mod.GlobalAuthMiddleware)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/protected")
    def protected() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/api/v1/collectors/enroll")
    def enroll() -> dict[str, str]:
        return {"enrolled": "yes"}

    return app


def test_health_is_public() -> None:
    client = TestClient(_make_app())
    assert client.get("/health").status_code == 200


def test_protected_without_token_returns_401() -> None:
    client = TestClient(_make_app())
    resp = client.get("/protected")
    assert resp.status_code == 401


def test_protected_with_valid_cookie_sets_rbac_sub() -> None:
    token, _, _ = create_access_token(
        TokenClaims(user_id="user-1", email="a@b.c", username="a", role="admin")
    )
    client = TestClient(_make_app())
    with patch("internalcmdb.api.middleware.global_auth.is_revoked", return_value=False):
        resp = client.get("/protected", cookies={"cmdb_session": token})
    assert resp.status_code == 200


def test_agent_enroll_path_is_public() -> None:
    client = TestClient(_make_app())
    assert client.get("/api/v1/collectors/enroll").status_code == 200


def test_revoked_token_returns_401() -> None:
    token, _, _ = create_access_token(
        TokenClaims(user_id="user-2", email="b@b.c", username="b", role="viewer")
    )
    client = TestClient(_make_app())
    with patch("internalcmdb.api.middleware.global_auth.is_revoked", return_value=True):
        resp = client.get("/protected", cookies={"cmdb_session": token})
    assert resp.status_code == 401


def test_force_password_change_blocks_non_auth_paths() -> None:
    token, _, _ = create_access_token(
        TokenClaims(
            user_id="user-3",
            email="c@b.c",
            username="c",
            role="viewer",
            force_password_change=True,
        )
    )
    app = FastAPI()
    app.add_middleware(ga_mod.GlobalAuthMiddleware)

    @app.get("/hosts")
    def hosts() -> dict[str, str]:
        return {"hosts": "ok"}

    client = TestClient(app)
    with patch("internalcmdb.api.middleware.global_auth.is_revoked", return_value=False):
        resp = client.get("/hosts", cookies={"cmdb_session": token})
    assert resp.status_code == 403


def test_force_password_change_allows_auth_verify_path() -> None:
    token, _, _ = create_access_token(
        TokenClaims(
            user_id="user-4",
            email="d@b.c",
            username="d",
            role="viewer",
            force_password_change=True,
        )
    )
    app = FastAPI()
    app.add_middleware(ga_mod.GlobalAuthMiddleware)

    @app.get("/api/v1/auth/verify")
    def verify() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    with patch("internalcmdb.api.middleware.global_auth.is_revoked", return_value=False):
        resp = client.get("/api/v1/auth/verify", cookies={"cmdb_session": token})
    assert resp.status_code == 200
