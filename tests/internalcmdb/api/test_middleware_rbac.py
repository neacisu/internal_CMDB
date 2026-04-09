"""Tests for internalcmdb.api.middleware.rbac (local JWT, no Zitadel)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request as StarletteRequest

from internalcmdb.api.middleware import rbac as rbac_mod
from internalcmdb.auth.security import invalidate_jwt_secret_cache

_SECRET = "x" * 32


def _make_request(
    cookies: dict[str, str] | None = None,
    auth_header: str | None = None,
) -> StarletteRequest:
    headers: list[tuple[bytes, bytes]] = []
    if auth_header:
        headers.append((b"authorization", auth_header.encode()))
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": headers,
        "cookies": cookies or {},
    }
    req = StarletteRequest(scope)  # type: ignore[arg-type]
    # Starlette parses cookies from headers; inject directly for tests.
    req._cookies = cookies or {}  # type: ignore[attr-defined]
    return req


@pytest.fixture(autouse=True)
def jwt_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("JWT_SECRET_KEY", _SECRET)
    monkeypatch.setenv("AUTH_DEV_MODE", "false")
    invalidate_jwt_secret_cache()
    # Reload module-level AUTH_DEV_MODE for the test
    import importlib  # noqa: PLC0415

    importlib.reload(rbac_mod)
    yield
    invalidate_jwt_secret_cache()


# ---------------------------------------------------------------------------
# require_role — no token
# ---------------------------------------------------------------------------


def test_require_role_raises_401_missing_token() -> None:
    dep = rbac_mod.require_role("admin")
    req = _make_request()
    with pytest.raises(HTTPException) as ei:
        dep(request=req, token=None)
    assert ei.value.status_code == 401


# ---------------------------------------------------------------------------
# require_role — valid token
# ---------------------------------------------------------------------------


def test_require_role_passes_with_correct_role() -> None:
    from internalcmdb.auth.security import TokenClaims, create_access_token  # noqa: PLC0415

    token, _, _ = create_access_token(TokenClaims("u1", "u@e.com", "u", "admin"))

    with patch("internalcmdb.api.middleware.rbac.is_revoked", return_value=False):
        dep = rbac_mod.require_role("admin")
        req = _make_request(auth_header=f"Bearer {token}")
        dep(request=req, token=token)  # should not raise


def test_require_role_raises_403_wrong_role() -> None:
    from internalcmdb.auth.security import TokenClaims, create_access_token  # noqa: PLC0415

    token, _, _ = create_access_token(TokenClaims("u1", "u@e.com", "u", "viewer"))

    with patch("internalcmdb.api.middleware.rbac.is_revoked", return_value=False):
        dep = rbac_mod.require_role("admin")
        req = _make_request(auth_header=f"Bearer {token}")
        with pytest.raises(HTTPException) as ei:
            dep(request=req, token=token)
        assert ei.value.status_code == 403


def test_require_role_raises_401_revoked_token() -> None:
    from internalcmdb.auth.security import TokenClaims, create_access_token  # noqa: PLC0415

    token, _, _ = create_access_token(TokenClaims("u1", "u@e.com", "u", "admin"))

    with patch("internalcmdb.api.middleware.rbac.is_revoked", return_value=True):
        dep = rbac_mod.require_role("admin")
        req = _make_request(auth_header=f"Bearer {token}")
        with pytest.raises(HTTPException) as ei:
            dep(request=req, token=token)
        assert ei.value.status_code == 401


# ---------------------------------------------------------------------------
# AUTH_DEV_MODE bypass
# ---------------------------------------------------------------------------


def test_require_role_dev_mode_bypasses_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rbac_mod, "AUTH_DEV_MODE", True)
    dep = rbac_mod.require_role("admin")
    req = _make_request()
    dep(request=req, token=None)  # no error in dev mode
