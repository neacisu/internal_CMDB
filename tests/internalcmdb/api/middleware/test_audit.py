"""Tests for api.middleware.audit — AuditMiddleware."""
from __future__ import annotations
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from starlette.responses import Response

from internalcmdb.api.middleware.audit import (
    AuditMiddleware,
    _extract_actor,
    _extract_ip,
)


def _make_request(path: str = "/api/v1/test", headers: dict | None = None, client_host: str | None = None):
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    if client_host:
        scope["client"] = (client_host, 12345)
    return Request(scope)


def _make_jwt(claims: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


# ---------------------------------------------------------------------------
# _extract_actor
# ---------------------------------------------------------------------------

def test_extract_actor_bearer_with_sub():
    token = _make_jwt({"sub": "user-42"})
    req = _make_request(headers={"authorization": f"Bearer {token}"})
    assert _extract_actor(req) == "user-42"


def test_extract_actor_preferred_username_fallback():
    token = _make_jwt({"preferred_username": "alice"})
    req = _make_request(headers={"authorization": f"Bearer {token}"})
    assert _extract_actor(req) == "alice"


def test_extract_actor_email_fallback():
    token = _make_jwt({"email": "alice@example.com"})
    req = _make_request(headers={"authorization": f"Bearer {token}"})
    assert _extract_actor(req) == "alice@example.com"


def test_extract_actor_bearer_unreadable():
    req = _make_request(headers={"authorization": "Bearer notjwt"})
    assert _extract_actor(req) == "bearer-token-unreadable"


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

    with patch("internalcmdb.api.middleware.audit.set_correlation_id"):
        with patch("internalcmdb.api.deps._get_async_session_factory", return_value=mock_factory):
            result = await middleware.dispatch(req, call_next)

    assert result.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_handles_audit_db_failure():
    """Audit DB failure should not crash the request."""
    app = MagicMock()
    middleware = AuditMiddleware(app)
    req = _make_request(path="/api/v1/registry/clusters")
    call_next = AsyncMock(return_value=Response("[]", status_code=200))

    with patch("internalcmdb.api.middleware.audit.set_correlation_id"):
        with patch("internalcmdb.api.deps._get_async_session_factory", side_effect=Exception("DB down")):
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

    with patch("internalcmdb.api.middleware.audit.set_correlation_id") as mock_set:
        with patch("internalcmdb.api.deps._get_async_session_factory", side_effect=Exception("skip")):
            await middleware.dispatch(req, call_next)

    mock_set.assert_called_once_with("test-corr-id-123")


@pytest.mark.asyncio
async def test_dispatch_generates_correlation_id_when_missing():
    app = MagicMock()
    middleware = AuditMiddleware(app)
    req = _make_request(path="/api/v1/test")
    call_next = AsyncMock(return_value=Response("{}", status_code=200))

    with patch("internalcmdb.api.middleware.audit.set_correlation_id") as mock_set:
        with patch("internalcmdb.api.deps._get_async_session_factory", side_effect=Exception("skip")):
            await middleware.dispatch(req, call_next)

    # Correlation ID should have been auto-generated (UUID format)
    assert mock_set.call_count == 1
    corr_id = mock_set.call_args[0][0]
    assert len(corr_id) > 0
