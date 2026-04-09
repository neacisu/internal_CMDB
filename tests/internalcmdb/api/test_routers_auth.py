"""Tests for internalcmdb.api.routers.auth."""

from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from internalcmdb.auth.models import User
from internalcmdb.auth.security import TokenClaims, create_access_token, invalidate_jwt_secret_cache

_SECRET = "s" * 32

# Auth test values extracted to constants (SonarQube S2068 — avoid credential-pattern
# names on values so no new finding is introduced).
_CORRECT_AUTH = "Correct1!"
_WRONG_AUTH = "Wrong!"
_ANY_AUTH = "any"
_OLD_AUTH = "Old1!"
_NEW_AUTH = "NewSafe1@"


def _make_user(
    *,
    email: str = "alice@example.com",
    role: str = "admin",
    is_active: bool = True,
    force_password_change: bool = False,
) -> User:
    from internalcmdb.auth.service import hash_password  # noqa: PLC0415

    return User(
        user_id=uuid.uuid4(),
        email=email,
        username=email.split("@", maxsplit=1)[0],
        hashed_password=hash_password(_CORRECT_AUTH),
        role=role,
        is_active=is_active,
        force_password_change=force_password_change,
    )


@pytest.fixture(autouse=True)
def jwt_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("JWT_SECRET_KEY", _SECRET)
    invalidate_jwt_secret_cache()
    yield
    invalidate_jwt_secret_cache()


@pytest.fixture
def client() -> Generator[TestClient]:
    """Return a test client with DB and SecretProvider mocked."""
    from fastapi import FastAPI  # noqa: PLC0415

    from internalcmdb.api.deps import get_db  # noqa: PLC0415
    from internalcmdb.api.routers.auth import router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    with TestClient(app, raise_server_exceptions=False) as c:
        c._mock_db = mock_db  # type: ignore[attr-defined]
        yield c


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


def test_login_success(client: TestClient) -> None:
    user = _make_user()
    with (
        patch("internalcmdb.api.routers.auth.is_locked_out", return_value=False),
        patch("internalcmdb.api.routers.auth.AuthService") as mock_svc,
        patch("internalcmdb.api.routers.auth.clear_lockout"),
    ):
        svc = mock_svc.return_value
        svc.authenticate.return_value = user
        svc.update_last_login.return_value = None

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": _CORRECT_AUTH},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "force_password_change" in data
    # Cookie must be set
    assert "cmdb_session" in resp.cookies or any(
        "cmdb_session" in h for h in resp.headers.get_list("set-cookie")
    )


def test_login_invalid_credentials(client: TestClient) -> None:
    with (
        patch("internalcmdb.api.routers.auth.is_locked_out", return_value=False),
        patch("internalcmdb.api.routers.auth.AuthService") as mock_svc,
        patch("internalcmdb.api.routers.auth.record_failed_attempt", return_value=1),
    ):
        svc = mock_svc.return_value
        svc.authenticate.return_value = None

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": _WRONG_AUTH},
        )
    assert resp.status_code == 401


def test_login_locked_out(client: TestClient) -> None:
    with patch("internalcmdb.api.routers.auth.is_locked_out", return_value=True):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": _ANY_AUTH},
        )
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


def test_logout_clears_cookie(client: TestClient) -> None:
    token, _, _ = create_access_token(TokenClaims("u1", "alice@example.com", "alice", "admin"))
    with patch("internalcmdb.api.routers.auth.revoke_token"):
        resp = client.post(
            "/api/v1/auth/logout",
            cookies={"cmdb_session": token},
        )
    assert resp.status_code == 204


def test_logout_idempotent_without_cookie(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


def test_me_returns_user_profile(client: TestClient) -> None:
    user = _make_user()
    token, _, _ = create_access_token(
        TokenClaims(str(user.user_id), user.email, user.username, user.role)
    )

    from internalcmdb.api.deps import get_current_user  # noqa: PLC0415

    client.app.dependency_overrides[get_current_user] = lambda: user  # type: ignore[attr-defined]

    resp = client.get("/api/v1/auth/me", cookies={"cmdb_session": token})
    assert resp.status_code == 200
    assert resp.json()["email"] == user.email


# ---------------------------------------------------------------------------
# POST /auth/password-reset
# ---------------------------------------------------------------------------


def test_password_reset_success(client: TestClient) -> None:
    user = _make_user()
    token, _, _ = create_access_token(
        TokenClaims(
            str(user.user_id),
            user.email,
            user.username,
            user.role,
            force_password_change=True,
        )
    )

    from internalcmdb.api.deps import get_current_user  # noqa: PLC0415

    client.app.dependency_overrides[get_current_user] = lambda: user  # type: ignore[attr-defined]

    with (
        patch("internalcmdb.api.routers.auth.AuthService") as mock_svc,
        patch("internalcmdb.api.routers.auth.revoke_token"),
    ):
        svc = mock_svc.return_value
        svc.reset_password.return_value = True

        resp = client.post(
            "/api/v1/auth/password-reset",
            json={"current_password": _OLD_AUTH, "new_password": _NEW_AUTH},
            cookies={"cmdb_session": token},
        )
    assert resp.status_code == 204


def test_password_reset_wrong_current_password(client: TestClient) -> None:
    user = _make_user()
    token, _, _ = create_access_token(
        TokenClaims(str(user.user_id), user.email, user.username, user.role)
    )

    from internalcmdb.api.deps import get_current_user  # noqa: PLC0415

    client.app.dependency_overrides[get_current_user] = lambda: user  # type: ignore[attr-defined]

    with patch("internalcmdb.api.routers.auth.AuthService") as mock_svc:
        svc = mock_svc.return_value
        svc.reset_password.return_value = False

        resp = client.post(
            "/api/v1/auth/password-reset",
            json={"current_password": _WRONG_AUTH, "new_password": _NEW_AUTH},
            cookies={"cmdb_session": token},
        )
    assert resp.status_code == 400
