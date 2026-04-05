"""Tests for internalcmdb.api.middleware.rate_limit helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from starlette.requests import Request

from internalcmdb.api.middleware import rate_limit as rl


def test_key_func_exempt_path() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [],
        "client": ("127.0.0.1", 1234),
    }
    req = Request(scope)
    assert rl._key_func(req) == "exempt"


def test_key_func_agent_id() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/x",
        "headers": [
            (b"x-agent-id", b"host-1"),
        ],
        "client": ("127.0.0.1", 1234),
    }
    req = Request(scope)
    assert rl._key_func(req) == "agent:host-1"


def test_key_func_forwarded_for() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/x",
        "headers": [
            (b"x-forwarded-for", b"10.0.0.1, 10.0.0.2"),
        ],
        "client": ("127.0.0.1", 1234),
    }
    req = Request(scope)
    assert rl._key_func(req) == "10.0.0.1"


@patch.dict("os.environ", {"RATE_LIMIT_REDIS_URL": "redis://localhost:6379/0"}, clear=False)
def test_build_storage_uri_prefers_rate_limit_redis() -> None:
    assert rl._build_storage_uri() == "redis://localhost:6379/0"


def test_rate_limit_exceeded_handler_returns_429() -> None:
    req = MagicMock(spec=Request)
    exc = MagicMock()
    exc.detail = "5 per 1 minute"
    resp = rl.rate_limit_exceeded_handler(req, exc)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
