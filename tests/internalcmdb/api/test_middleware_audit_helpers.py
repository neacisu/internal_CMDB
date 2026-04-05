"""Tests for audit middleware helpers (no live DB)."""

from __future__ import annotations

import base64
import json

from starlette.requests import Request

from internalcmdb.api.middleware.audit import _extract_actor, _extract_ip


def test_extract_ip_forwarded() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/x",
        "headers": [(b"x-forwarded-for", b"203.0.113.1, 10.0.0.1")],
        "client": ("127.0.0.1", 80),
    }
    assert _extract_ip(Request(scope)) == "203.0.113.1"


def test_extract_ip_client() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/x",
        "headers": [],
        "client": ("192.168.1.5", 80),
    }
    assert _extract_ip(Request(scope)) == "192.168.1.5"


def test_extract_actor_api_key_user() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/x",
        "headers": [(b"x-api-key-user", b"svc-collector")],
        "client": ("127.0.0.1", 80),
    }
    assert _extract_actor(Request(scope)) == "svc-collector"


def test_extract_actor_bearer_sub() -> None:
    payload = {"sub": "user-abc"}
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    token = f"h.{b64}.s"
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/x",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "client": ("127.0.0.1", 80),
    }
    assert _extract_actor(Request(scope)) == "user-abc"
