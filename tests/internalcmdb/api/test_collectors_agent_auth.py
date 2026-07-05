"""Tests for zero-trust agent enrollment and token verification."""

from __future__ import annotations

import hashlib
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_db
from internalcmdb.api.middleware.rate_limit import rate_limit as _rate_limit
from internalcmdb.api.routers.collectors import (
    _ALLOWED_SNAPSHOT_KINDS,
    _compute_payload_hash,
    _validate_bootstrap_token,
    router as collectors_router,
    verify_agent_token,
)
from internalcmdb.collectors.agent_auth import generate_agent_token, hash_bootstrap_token
from internalcmdb.models.collectors import CollectorAgent

_BOOTSTRAP = "bootstrap-dev-token-change-me"
_AGENT_ID = uuid.uuid4()


def _make_agent(token: str | None = "secret-token") -> CollectorAgent:
    agent = CollectorAgent(
        agent_id=_AGENT_ID,
        host_code="test-host",
        agent_version="1.0.0",
        status="online",
        is_active=True,
    )
    if token is not None:
        agent.token_hash = hashlib.sha256(token.encode()).hexdigest()
    return agent


def test_compute_payload_hash_matches_agent_daemon() -> None:
    payload = {"cpu": 42, "mem": 1024}
    expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    assert _compute_payload_hash(payload) == expected


def test_validate_bootstrap_token_rejects_missing() -> None:
    db = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        _validate_bootstrap_token(db, None)
    assert exc_info.value.status_code == 401


def test_validate_bootstrap_token_accepts_active_hash() -> None:
    db = MagicMock()
    db.execute.return_value.first.return_value = ("token-id",)
    _validate_bootstrap_token(db, _BOOTSTRAP)
    call_args = db.execute.call_args[0][1]
    assert call_args["token_hash"] == hash_bootstrap_token(_BOOTSTRAP)


def test_verify_agent_token_rejects_bad_hash() -> None:
    agent = _make_agent("correct-token")
    db = MagicMock()
    db.get.return_value = agent
    with pytest.raises(HTTPException) as exc_info:
        verify_agent_token(
            authorization="Bearer wrong-token",
            x_agent_id=str(_AGENT_ID),
            db=db,
        )
    assert exc_info.value.status_code == 401


def test_verify_agent_token_accepts_valid_token() -> None:
    token = "my-agent-token"
    agent = _make_agent(token)
    db = MagicMock()
    db.get.return_value = agent
    result = verify_agent_token(
        authorization=f"Bearer {token}",
        x_agent_id=str(_AGENT_ID),
        db=db,
    )
    assert result == _AGENT_ID


def test_allowed_snapshot_kinds_include_heartbeat() -> None:
    assert "heartbeat" in _ALLOWED_SNAPSHOT_KINDS
    assert "system_vitals" in _ALLOWED_SNAPSHOT_KINDS


def _make_collectors_app(db: MagicMock) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[_rate_limit] = lambda: None
    app.include_router(collectors_router, prefix="/api/v1")
    return app


def test_enroll_requires_bootstrap_token() -> None:
    db = MagicMock()
    db.execute.return_value.first.return_value = None
    client = TestClient(_make_collectors_app(db))
    resp = client.post(
        "/api/v1/collectors/enroll",
        json={"host_code": "host1", "agent_version": "1.0.0", "capabilities": []},
    )
    assert resp.status_code == 401


def test_enroll_returns_random_token_and_caches() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    db.execute.return_value.first.return_value = ("bootstrap-id",)

    with patch("internalcmdb.api.routers.collectors.cache_agent_token") as cache_mock:
        client = TestClient(_make_collectors_app(db))
        resp = client.post(
            "/api/v1/collectors/enroll",
            json={"host_code": "host1", "agent_version": "1.0.0", "capabilities": []},
            headers={"X-Bootstrap-Token": _BOOTSTRAP},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert "api_token" in data
    assert len(data["api_token"]) >= 32
    cache_mock.assert_called_once()
