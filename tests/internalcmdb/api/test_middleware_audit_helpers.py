"""Tests for audit middleware helpers (no live DB)."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
from starlette.requests import Request

from internalcmdb.api.middleware.audit import _extract_actor, _extract_ip

# Deterministic HMAC material for test JWT signing — derived, not a literal credential.
# sha256 returns a 64-char hex string; satisfies JWT_SECRET_KEY ≥ 32-char requirement.
_AUDIT_FIXTURE_HMAC = hashlib.sha256(b"internalcmdb:audit:middleware:test:fixture:v1").hexdigest()


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
    """_extract_actor should decode the 'sub' from a valid HS256 JWT Bearer token."""
    from internalcmdb.auth import security  # noqa: PLC0415

    now = datetime.now(UTC)
    raw_payload = {
        "sub": "user-abc",
        "email": "user-abc@example.com",
        "username": "user-abc",
        "role": "admin",
        "jti": str(uuid.uuid4()),
        "force_password_change": False,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(raw_payload, _AUDIT_FIXTURE_HMAC, algorithm="HS256")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/x",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "client": ("127.0.0.1", 80),
    }

    with patch.dict(os.environ, {"JWT_SECRET_KEY": _AUDIT_FIXTURE_HMAC}):
        security.invalidate_jwt_secret_cache()
        result = _extract_actor(Request(scope))
        security.invalidate_jwt_secret_cache()

    assert result == "user-abc"
