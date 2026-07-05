"""Tests for heartbeat snapshot throttling in collectors router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_db
from internalcmdb.api.middleware.rate_limit import limiter
from internalcmdb.api.routers.collectors import (
    _get_heartbeat_snapshot_interval_seconds,
    _should_store_heartbeat_snapshot,
    verify_agent_token,
)
from internalcmdb.api.routers.collectors import router as collectors_router


class TestHeartbeatThrottle:
    def test_should_store_when_interval_zero(self):
        db = MagicMock()
        assert _should_store_heartbeat_snapshot(db, uuid.uuid4(), 0) is True
        db.scalar.assert_not_called()

    def test_should_not_store_when_recent_exists(self):
        db = MagicMock()
        db.scalar.return_value = True
        assert _should_store_heartbeat_snapshot(db, uuid.uuid4(), 60) is False

    def test_should_store_when_no_recent(self):
        db = MagicMock()
        db.scalar.return_value = False
        assert _should_store_heartbeat_snapshot(db, uuid.uuid4(), 60) is True

    def test_interval_cache_reads_setting_once(self):
        db = MagicMock()
        db.scalar.return_value = 120
        with patch("internalcmdb.api.routers.collectors._HEARTBEAT_INTERVAL_CACHE", {"value": 60, "expires_at": 0.0}):
            assert _get_heartbeat_snapshot_interval_seconds(db) == 120
            assert _get_heartbeat_snapshot_interval_seconds(db) == 120
            assert db.scalar.call_count == 1

    def test_interval_invalid_falls_back_to_sixty(self):
        db = MagicMock()
        db.scalar.return_value = "not-a-number"
        with patch("internalcmdb.api.routers.collectors._HEARTBEAT_INTERVAL_CACHE", {"value": 60, "expires_at": 0.0}):
            assert _get_heartbeat_snapshot_interval_seconds(db) == 60


# ---------------------------------------------------------------------------
# POST /collectors/ingest — heartbeat throttle
# ---------------------------------------------------------------------------

_AGENT_ID = uuid.uuid4()


def _make_ingest_app() -> tuple[FastAPI, MagicMock]:
    app = FastAPI()
    app.state.limiter = limiter
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[verify_agent_token] = lambda: _AGENT_ID
    app.include_router(collectors_router, prefix="/api/v1")
    return app, mock_db


def _heartbeat_item(payload_hash: str = "hash-1") -> dict:
    return {
        "snapshot_kind": "heartbeat",
        "tier_code": "5s",
        "payload": {"uptime_seconds": 123.4, "load_avg": [0.1], "memory_pct": 40.0},
        "collected_at": datetime.now(UTC).isoformat(),
        "payload_hash": payload_hash,
    }


class TestIngestHeartbeatThrottle:
    def _post_ingest(self, mock_db: MagicMock, app: FastAPI, snapshots: list[dict]):
        client = TestClient(app)
        return client.post(
            "/api/v1/collectors/ingest",
            json={"agent_id": str(_AGENT_ID), "snapshots": snapshots},
            headers={"X-Agent-ID": str(_AGENT_ID), "Authorization": "Bearer x"},
        )

    def test_heartbeat_item_throttled_when_recent_snapshot_exists(self):
        app, mock_db = _make_ingest_app()
        agent = MagicMock()
        agent.agent_config_jsonb = {}
        mock_db.execute.return_value.scalar_one_or_none.return_value = agent
        # interval setting = 60, EXISTS(recent heartbeat) = True
        mock_db.scalar.side_effect = [60, True]

        with patch("internalcmdb.api.routers.collectors._HEARTBEAT_INTERVAL_CACHE", {"value": 60, "expires_at": 0.0}):
            r = self._post_ingest(mock_db, app, [_heartbeat_item()])

        assert r.status_code == 200
        data = r.json()
        assert data["deduplicated"] == 1
        assert data["accepted"] == 0

    def test_heartbeat_item_stored_when_no_recent_snapshot(self):
        app, mock_db = _make_ingest_app()
        agent = MagicMock()
        agent.agent_config_jsonb = {}
        agent.host_code = "host-01"
        # _lock_agent -> agent; hash-dedup select -> no existing; diff select -> no prev
        mock_db.execute.return_value.scalar_one_or_none.return_value = agent
        mock_db.execute.return_value.first.return_value = None
        # interval setting = 60, EXISTS(recent) = False, then _next_snapshot_version
        mock_db.scalar.side_effect = [60, False, 0]

        with patch("internalcmdb.api.routers.collectors._HEARTBEAT_INTERVAL_CACHE", {"value": 60, "expires_at": 0.0}):
            r = self._post_ingest(mock_db, app, [_heartbeat_item()])

        assert r.status_code == 200
        data = r.json()
        assert data["accepted"] == 1
        assert data["deduplicated"] == 0

    def test_non_heartbeat_kind_not_throttled(self):
        app, mock_db = _make_ingest_app()
        agent = MagicMock()
        agent.agent_config_jsonb = {}
        agent.host_code = "host-01"
        mock_db.execute.return_value.scalar_one_or_none.return_value = agent
        mock_db.execute.return_value.first.return_value = None
        # interval setting read once; no EXISTS call for non-heartbeat kinds
        mock_db.scalar.side_effect = [60, 0]

        item = _heartbeat_item()
        item["snapshot_kind"] = "system_vitals"

        with patch("internalcmdb.api.routers.collectors._HEARTBEAT_INTERVAL_CACHE", {"value": 60, "expires_at": 0.0}):
            r = self._post_ingest(mock_db, app, [item])

        assert r.status_code == 200
        assert r.json()["accepted"] == 1
