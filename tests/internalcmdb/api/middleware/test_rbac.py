"""Tests for api.middleware.rbac — local JWT (no Zitadel)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from internalcmdb.auth.security import TokenClaims, create_access_token, invalidate_jwt_secret_cache

_SECRET = "t" * 32


def _make_request(
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    req = Request(scope)  # type: ignore[arg-type]
    req._cookies = cookies or {}  # type: ignore[attr-defined]
    return req


@pytest.fixture(autouse=True)
def jwt_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("JWT_SECRET_KEY", _SECRET)
    monkeypatch.setenv("AUTH_DEV_MODE", "false")
    invalidate_jwt_secret_cache()
    import importlib  # noqa: PLC0415

    import internalcmdb.api.middleware.rbac as _rbac  # noqa: PLC0415

    importlib.reload(_rbac)
    yield
    invalidate_jwt_secret_cache()


# ---------------------------------------------------------------------------
# _get_auth_token
# ---------------------------------------------------------------------------


def test_get_auth_token_prefers_cookie():
    from internalcmdb.api.middleware.rbac import _get_auth_token  # noqa: PLC0415

    req = _make_request(
        headers={"authorization": "Bearer header-token"},
        cookies={"cmdb_session": "cookie-token"},
    )
    assert _get_auth_token(req) == "cookie-token"


def test_get_auth_token_falls_back_to_bearer():
    from internalcmdb.api.middleware.rbac import _get_auth_token  # noqa: PLC0415

    req = _make_request(headers={"authorization": "Bearer bearer-token"})
    assert _get_auth_token(req) == "bearer-token"


def test_get_auth_token_returns_none_when_absent():
    from internalcmdb.api.middleware.rbac import _get_auth_token  # noqa: PLC0415

    assert _get_auth_token(_make_request()) is None


# ---------------------------------------------------------------------------
# require_role
# ---------------------------------------------------------------------------


def test_require_role_dev_mode_bypasses():
    import internalcmdb.api.middleware.rbac as rbac_mod  # noqa: PLC0415

    rbac_mod.AUTH_DEV_MODE = True
    dep = rbac_mod.require_role("admin")
    dep(request=_make_request(), token=None)
    rbac_mod.AUTH_DEV_MODE = False


def test_require_role_no_token_raises_401():
    from internalcmdb.api.middleware.rbac import require_role  # noqa: PLC0415

    dep = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        dep(request=_make_request(), token=None)
    assert exc.value.status_code == 401


def test_require_role_invalid_token_raises_401():
    from internalcmdb.api.middleware.rbac import require_role  # noqa: PLC0415

    dep = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        dep(request=_make_request(), token="not.a.jwt.token")
    assert exc.value.status_code == 401


def test_require_role_correct_role_passes():
    from internalcmdb.api.middleware.rbac import require_role  # noqa: PLC0415

    _claims = TokenClaims(user_id="u1", email="a@b.com", username="alice", role="admin")
    token, _, _ = create_access_token(_claims)
    with patch("internalcmdb.api.middleware.rbac.is_revoked", return_value=False):
        dep = require_role("admin")
        dep(request=_make_request(), token=token)  # must not raise


def test_require_role_wrong_role_raises_403():
    from internalcmdb.api.middleware.rbac import require_role  # noqa: PLC0415

    _claims = TokenClaims(user_id="u1", email="a@b.com", username="alice", role="viewer")
    token, _, _ = create_access_token(_claims)
    with patch("internalcmdb.api.middleware.rbac.is_revoked", return_value=False):
        dep = require_role("admin")
        with pytest.raises(HTTPException) as exc:
            dep(request=_make_request(), token=token)
        assert exc.value.status_code == 403


def test_require_role_revoked_token_raises_401():
    from internalcmdb.api.middleware.rbac import require_role  # noqa: PLC0415

    _claims = TokenClaims(user_id="u1", email="a@b.com", username="alice", role="admin")
    token, _, _ = create_access_token(_claims)
    with patch("internalcmdb.api.middleware.rbac.is_revoked", return_value=True):
        dep = require_role("admin")
        with pytest.raises(HTTPException) as exc:
            dep(request=_make_request(), token=token)
        assert exc.value.status_code == 401


def test_require_role_multiple_roles_allowed():
    from internalcmdb.api.middleware.rbac import require_role  # noqa: PLC0415

    _claims = TokenClaims(user_id="u1", email="a@b.com", username="alice", role="operator")
    token, _, _ = create_access_token(_claims)
    with patch("internalcmdb.api.middleware.rbac.is_revoked", return_value=False):
        dep = require_role("admin", "operator")
        dep(request=_make_request(), token=token)  # must not raise


def test_require_role_sets_request_state():
    from internalcmdb.api.middleware.rbac import require_role  # noqa: PLC0415

    _claims = TokenClaims(user_id="u1", email="a@b.com", username="alice", role="admin")
    token, _, _ = create_access_token(_claims)
    req = _make_request()
    with patch("internalcmdb.api.middleware.rbac.is_revoked", return_value=False):
        dep = require_role("admin")
        dep(request=req, token=token)
    assert req.state.rbac_role == "admin"
    assert req.state.rbac_sub == "u1"
