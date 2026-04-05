"""Tests for api.middleware.rate_limit."""
from __future__ import annotations
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request
from slowapi.errors import RateLimitExceeded

from internalcmdb.api.middleware.rate_limit import (
    RATE_LIMITS,
    _build_storage_uri,
    _key_func,
    get_rate_limit_decorators,
    rate_limit_exceeded_handler,
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


# ---------------------------------------------------------------------------
# _key_func
# ---------------------------------------------------------------------------

def test_key_func_exempt_path():
    req = _make_request(path="/health")
    assert _key_func(req) == "exempt"


def test_key_func_exempt_metrics():
    req = _make_request(path="/metrics")
    assert _key_func(req) == "exempt"


def test_key_func_agent_id_header():
    req = _make_request(headers={"x-agent-id": "agent-007"})
    assert _key_func(req) == "agent:agent-007"


def test_key_func_forwarded_for_single():
    req = _make_request(headers={"x-forwarded-for": "10.0.0.1"})
    assert _key_func(req) == "10.0.0.1"


def test_key_func_forwarded_for_multiple():
    req = _make_request(headers={"x-forwarded-for": "10.0.0.1, 192.168.1.1"})
    assert _key_func(req) == "10.0.0.1"


def test_key_func_client_host():
    req = _make_request(client_host="172.16.0.1")
    assert _key_func(req) == "172.16.0.1"


def test_key_func_anonymous_no_client():
    req = _make_request()
    assert _key_func(req) == "anonymous"


# ---------------------------------------------------------------------------
# _build_storage_uri
# ---------------------------------------------------------------------------

def test_build_storage_uri_from_rate_limit_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", "redis://ratelimit:6379")
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert _build_storage_uri() == "redis://ratelimit:6379"


def test_build_storage_uri_from_redis_url(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://cache:6379")
    assert _build_storage_uri() == "redis://cache:6379"


def test_build_storage_uri_none_when_no_env(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert _build_storage_uri() is None


def test_build_storage_uri_none_for_unsupported_scheme(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "memcached://localhost:11211")
    assert _build_storage_uri() is None


# ---------------------------------------------------------------------------
# rate_limit_exceeded_handler
# ---------------------------------------------------------------------------

def test_rate_limit_exceeded_handler_with_pattern():
    req = _make_request()
    exc = RateLimitExceeded("10 per 1 minute")
    response = rate_limit_exceeded_handler(req, exc)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_rate_limit_exceeded_handler_no_pattern():
    req = _make_request()
    exc = RateLimitExceeded("custom limit message")
    response = rate_limit_exceeded_handler(req, exc)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_rate_limit_exceeded_handler_hour_window():
    req = _make_request()
    exc = RateLimitExceeded("5 per 1 hour")
    response = rate_limit_exceeded_handler(req, exc)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "3600"


def test_rate_limit_exceeded_handler_day_window():
    req = _make_request()
    exc = RateLimitExceeded("100 per 1 day")
    response = rate_limit_exceeded_handler(req, exc)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "86400"


# ---------------------------------------------------------------------------
# RATE_LIMITS and get_rate_limit_decorators
# ---------------------------------------------------------------------------

def test_rate_limits_dict_has_expected_keys():
    assert "/api/v1/collectors/ingest" in RATE_LIMITS
    assert "/api/v1/cognitive/query" in RATE_LIMITS
    assert "/api/v1/hitl/bulk-decide" in RATE_LIMITS


def test_get_rate_limit_decorators_returns_dict():
    decorators = get_rate_limit_decorators()
    assert isinstance(decorators, dict)
    assert len(decorators) == len(RATE_LIMITS)
    for path in RATE_LIMITS:
        assert path in decorators
        assert callable(decorators[path])
