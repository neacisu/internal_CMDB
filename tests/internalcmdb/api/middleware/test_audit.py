"""Tests for api.middleware.audit — AuditMiddleware."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import Request
from starlette.responses import Response

from internalcmdb.api.middleware.audit import (
    AuditMiddleware,
    _extract_actor,
    _extract_ip,
)

# Deterministic HMAC material for Bearer token tests — derived, not a literal credential.
_BEARER_FIXTURE_HMAC = hashlib.sha256(b"internalcmdb:audit:bearer:test:fixture:v1").hexdigest()


def _make_request(
    path: str = "/api/v1/test",
    headers: dict[str, str] | None = None,
    client_host: str | None = None,
) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    if client_host:
        scope["client"] = (client_host, 12345)
    return Request(scope)


def _make_signed_jwt(sub: str) -> str:
    """Create a properly HS256-signed JWT using the test HMAC material."""
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "email": f"{sub}@example.com",
        "username": sub,
        "role": "admin",
        "jti": str(uuid.uuid4()),
        "force_password_change": False,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, _BEARER_FIXTURE_HMAC, algorithm="HS256")


def _make_unsigned_jwt(claims: dict[str, Any]) -> str:
    """Construct a JWT-shaped string with NO valid signature — used to test the
    unverifiable-token path where the middleware must return 'bearer-token-unverified'."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.invalidsignature"


# ---------------------------------------------------------------------------
# _extract_actor
# ---------------------------------------------------------------------------


def test_extract_actor_verified_bearer_returns_sub():
    """A properly HS256-signed Bearer token should yield the 'sub' claim."""
    from internalcmdb.auth import security  # noqa: PLC0415

    token = _make_signed_jwt("verified-user")
    req = _make_request(headers={"authorization": f"Bearer {token}"})

    with patch.dict(os.environ, {"JWT_SECRET_KEY": _BEARER_FIXTURE_HMAC}):
        security.invalidate_jwt_secret_cache()
        result = _extract_actor(req)
        security.invalidate_jwt_secret_cache()

    assert result == "verified-user"


def test_extract_actor_unverified_bearer_sub_returns_sentinel():
    """An unverifiable JWT (bad signature) must NOT expose its claims — returns sentinel."""
    token = _make_unsigned_jwt({"sub": "user-42"})
    req = _make_request(headers={"authorization": f"Bearer {token}"})
    assert _extract_actor(req) == "bearer-token-unverified"


def test_extract_actor_unverified_bearer_preferred_username_returns_sentinel():
    """Zitadel-era 'preferred_username' claim in unsigned JWT must not be trusted."""
    token = _make_unsigned_jwt({"preferred_username": "alice"})
    req = _make_request(headers={"authorization": f"Bearer {token}"})
    assert _extract_actor(req) == "bearer-token-unverified"


def test_extract_actor_unverified_bearer_email_returns_sentinel():
    """Zitadel-era 'email' claim in unsigned JWT must not be trusted."""
    token = _make_unsigned_jwt({"email": "alice@example.com"})
    req = _make_request(headers={"authorization": f"Bearer {token}"})
    assert _extract_actor(req) == "bearer-token-unverified"


def test_extract_actor_bearer_unverified():
    """A garbled (non-JWT) Bearer value returns 'bearer-token-unverified'."""
    req = _make_request(headers={"authorization": "Bearer notjwt"})
    assert _extract_actor(req) == "bearer-token-unverified"


def test_extract_actor_non_bearer_auth():
    req = _make_request(headers={"authorization": "Basic abc"})
    assert _extract_actor(req) == "authenticated"


def test_extract_actor_api_key():
    req = _make_request(headers={"x-api-key-user": "service-account"})
    assert _extract_actor(req) == "service-account"


def test_extract_actor_none():
    req = _make_request()
    assert _extract_actor(req) is None


# ---------------------------------------------------------------------------
# _extract_ip
# ---------------------------------------------------------------------------


def test_extract_ip_forwarded_for():
    req = _make_request(headers={"x-forwarded-for": "10.0.0.1, 192.168.1.1"})
    assert _extract_ip(req) == "10.0.0.1"


def test_extract_ip_client_host():
    req = _make_request(client_host="172.16.0.1")
    assert _extract_ip(req) == "172.16.0.1"


def test_extract_ip_none():
    req = _make_request()
    assert _extract_ip(req) is None


# ---------------------------------------------------------------------------
# AuditMiddleware.dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_skips_health():
    app = MagicMock()
    middleware = AuditMiddleware(app)
    req = _make_request(path="/health")
    call_next = AsyncMock(return_value=Response("ok", status_code=200))
    result = await middleware.dispatch(req, call_next)
    assert result.status_code == 200
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_skips_docs():
    app = MagicMock()
    middleware = AuditMiddleware(app)
    for skip_path in ["/api/docs", "/api/redoc", "/api/openapi.json", "/favicon.ico"]:
        req = _make_request(path=skip_path)
        call_next = AsyncMock(return_value=Response("ok", status_code=200))
        result = await middleware.dispatch(req, call_next)
        assert result.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_records_audit():
    app = MagicMock()
    middleware = AuditMiddleware(app)
    req = _make_request(path="/api/v1/registry/clusters")

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    call_next = AsyncMock(return_value=Response("[]", status_code=200))

    with (
        patch("internalcmdb.api.middleware.audit.set_correlation_id"),
        patch("internalcmdb.api.deps._get_async_session_factory", return_value=mock_factory),
    ):
        result = await middleware.dispatch(req, call_next)

    assert result.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_handles_audit_db_failure():
    """Audit DB failure should not crash the request."""
    app = MagicMock()
    middleware = AuditMiddleware(app)
    req = _make_request(path="/api/v1/registry/clusters")
    call_next = AsyncMock(return_value=Response("[]", status_code=200))

    with (
        patch("internalcmdb.api.middleware.audit.set_correlation_id"),
        patch(
            "internalcmdb.api.deps._get_async_session_factory",
            side_effect=Exception("DB down"),
        ),
    ):
        result = await middleware.dispatch(req, call_next)

    assert result.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_uses_existing_correlation_id():
    app = MagicMock()
    middleware = AuditMiddleware(app)
    req = _make_request(
        path="/api/v1/test",
        headers={"x-correlation-id": "test-corr-id-123"},
    )
    call_next = AsyncMock(return_value=Response("{}", status_code=200))

    with (
        patch("internalcmdb.api.middleware.audit.set_correlation_id") as mock_set,
        patch("internalcmdb.api.deps._get_async_session_factory", side_effect=Exception("skip")),
    ):
        await middleware.dispatch(req, call_next)

    mock_set.assert_called_once_with("test-corr-id-123")


@pytest.mark.asyncio
async def test_dispatch_generates_correlation_id_when_missing():
    app = MagicMock()
    middleware = AuditMiddleware(app)
    req = _make_request(path="/api/v1/test")
    call_next = AsyncMock(return_value=Response("{}", status_code=200))

    with (
        patch("internalcmdb.api.middleware.audit.set_correlation_id") as mock_set,
        patch("internalcmdb.api.deps._get_async_session_factory", side_effect=Exception("skip")),
    ):
        await middleware.dispatch(req, call_next)

    # Correlation ID should have been auto-generated (UUID format)
    assert mock_set.call_count == 1
    corr_id = mock_set.call_args[0][0]
    assert len(corr_id) > 0


# ---------------------------------------------------------------------------
# set_correlation_id — interface contract
# ---------------------------------------------------------------------------
# The module-level ``set_correlation_id`` is either the real implementation
# from ``internalcmdb.observability.logging`` (signature: cid: str | None)
# or the ImportError fallback stub.  Both must honour the same contract:
# accept ``str`` and ``None`` without raising.  These tests lock down that
# contract so a future signature drift is caught immediately.


def test_set_correlation_id_accepts_str():
    """Module-level set_correlation_id must accept a plain str without raising."""
    import internalcmdb.api.middleware.audit as _audit  # noqa: PLC0415

    _audit.set_correlation_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def test_set_correlation_id_accepts_none():
    """Module-level set_correlation_id must accept None without raising.

    The real ``observability.logging.set_correlation_id`` signature is
    ``cid: str | None`` — it resets the ContextVar to None when called
    with None.  The ImportError fallback stub must mirror this contract.
    The bug that prompted this test was the stub declaring ``_cid: str``
    (non-None, wrong parameter name), which caused a Pylance
    ``reportAssignmentType`` error and would raise at runtime if the
    caller ever passed None.
    """
    import internalcmdb.api.middleware.audit as _audit  # noqa: PLC0415

    _audit.set_correlation_id(None)


def test_set_correlation_id_importerror_fallback_is_noop() -> None:
    """Reloading audit.py with observability.logging hidden must yield a working
    fallback stub that accepts both ``str`` and ``None`` without raising.

    This exercises the ``except ImportError`` branch directly — the branch is
    excluded from normal coverage runs (``# pragma: no cover``) because the
    real observability module is always present in the test environment.
    """
    import importlib  # noqa: PLC0415
    import sys  # noqa: PLC0415

    audit_key = "internalcmdb.api.middleware.audit"
    obs_key = "internalcmdb.observability.logging"

    # Stash originals so we can restore them unconditionally in finally.
    orig_audit = sys.modules.pop(audit_key, None)
    orig_obs = sys.modules.get(obs_key)

    try:
        # Signal Import machinery that the observability module is unavailable.
        sys.modules[obs_key] = None  # type: ignore[assignment]

        # Fresh import — the try/except ImportError branch fires.
        import internalcmdb.api.middleware.audit as audit_reloaded  # noqa: PLC0415

        stub = audit_reloaded.set_correlation_id

        # str — the common path (dispatch always provides a UUID string).
        stub("00000000-0000-0000-0000-000000000000")

        # None — must not raise; real signature is cid: str | None.
        stub(None)
    finally:
        # Evict the freshly loaded module so subsequent imports use the real one.
        sys.modules.pop(audit_key, None)
        sys.modules.pop(obs_key, None)

        # Restore observability module if it was previously loaded.
        if orig_obs is not None:
            sys.modules[obs_key] = orig_obs

        # Restore the audit module so the rest of the test session is unaffected.
        if orig_audit is not None:
            sys.modules[audit_key] = orig_audit

        # Force reimport of real audit module into the module cache.
        importlib.import_module(audit_key)
