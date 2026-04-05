"""Tests for the collectors router (sync get_db)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_db
from internalcmdb.api.routers.collectors import router as collectors_router


def _make_app() -> tuple[FastAPI, MagicMock]:
    app = FastAPI()
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.include_router(collectors_router, prefix="/api/v1")
    return app, mock_db


# ---------------------------------------------------------------------------
# POST /collectors/enroll
# ---------------------------------------------------------------------------


def test_enroll_creates_agent() -> None:
    """A new agent is created when no matching existing agents exist."""
    app, mock_db = _make_app()
    mock_db.scalars.return_value.all.return_value = []
    mock_db.commit.return_value = None

    with (
        patch(
            "internalcmdb.api.routers.collectors.resolve_host",
            return_value=None,
        ),
        patch(
            "internalcmdb.api.routers.collectors.get_settings",
        ) as mock_settings,
    ):
        mock_settings.return_value.secret_key = "test-secret-key-12345"

        client = TestClient(app)
        r = client.post(
            "/api/v1/collectors/enroll",
            json={
                "host_code": "test-host-01",
                "agent_version": "1.0.0",
                "capabilities": ["system_vitals", "disk_state"],
            },
        )

    assert r.status_code == 201
    data = r.json()
    assert "agent_id" in data
    assert "api_token" in data
    assert "schedule_tiers" in data
    assert "enabled_collectors" in data
    assert isinstance(data["enabled_collectors"], list)


def test_enroll_reuses_existing_agent() -> None:
    """When a matching active agent exists it is reused, not duplicated."""
    app, mock_db = _make_app()

    existing = MagicMock()
    existing.agent_id = uuid.uuid4()
    existing.host_id = None
    existing.host_code = "test-host-02"
    existing.agent_config_jsonb = {}
    mock_db.scalars.return_value.all.return_value = [existing]
    mock_db.commit.return_value = None

    with (
        patch(
            "internalcmdb.api.routers.collectors.resolve_host",
            return_value=None,
        ),
        patch(
            "internalcmdb.api.routers.collectors.get_settings",
        ) as mock_settings,
    ):
        mock_settings.return_value.secret_key = "test-secret-key-12345"

        client = TestClient(app)
        r = client.post(
            "/api/v1/collectors/enroll",
            json={
                "host_code": "test-host-02",
                "agent_version": "1.1.0",
                "capabilities": [],
            },
        )

    assert r.status_code == 201
    data = r.json()
    assert str(data["agent_id"]) == str(existing.agent_id)


# ---------------------------------------------------------------------------
# GET /collectors/agents
# ---------------------------------------------------------------------------


def test_agents_list_empty() -> None:
    """Returns an empty list when no active agents are registered."""
    app, mock_db = _make_app()
    mock_db.scalars.return_value.all.return_value = []

    client = TestClient(app)
    r = client.get("/api/v1/collectors/agents")

    assert r.status_code == 200
    assert r.json() == []


def test_agents_list_with_status_filter() -> None:
    """Accepts an optional status query parameter."""
    app, mock_db = _make_app()
    mock_db.scalars.return_value.all.return_value = []

    client = TestClient(app)
    r = client.get("/api/v1/collectors/agents", params={"status": "online"})

    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# GET /collectors/health  (fleet health summary)
# ---------------------------------------------------------------------------


def test_fleet_health_empty() -> None:
    """Returns a FleetHealthSummary with all-zero counts when no agents are active."""
    app, _ = _make_app()

    mock_fleet_state = MagicMock()
    mock_fleet_state.hosts = []
    mock_fleet_state.agents_by_host_id = {}
    mock_fleet_state.unassigned_agents = []

    with patch(
        "internalcmdb.api.routers.collectors.build_fleet_state",
        return_value=mock_fleet_state,
    ):
        client = TestClient(app)
        r = client.get("/api/v1/collectors/health")

    assert r.status_code == 200
    data = r.json()
    assert data["online"] == 0
    assert data["offline"] == 0
    assert data["total"] == 0
    assert "registered_agents" in data


def test_fleet_health_with_online_agent() -> None:
    """Counts an online agent correctly."""
    app, _ = _make_app()

    agent = MagicMock()
    agent.agent_id = uuid.uuid4()
    agent.last_heartbeat_at = "2026-01-01T00:00:00+00:00"

    host = MagicMock()
    host.host_id = uuid.uuid4()
    host.host_code = "h-01"
    host.hostname = "host-01"

    mock_fleet_state = MagicMock()
    mock_fleet_state.hosts = [host]
    mock_fleet_state.agents_by_host_id = {host.host_id: agent}
    mock_fleet_state.unassigned_agents = []

    with (
        patch(
            "internalcmdb.api.routers.collectors.build_fleet_state",
            return_value=mock_fleet_state,
        ),
        patch(
            "internalcmdb.api.routers.collectors.derive_agent_status",
            return_value="online",
        ),
    ):
        client = TestClient(app)
        r = client.get("/api/v1/collectors/health")

    assert r.status_code == 200
    data = r.json()
    assert data["online"] == 1
    assert data["total"] == 1


# ---------------------------------------------------------------------------
# GET /collectors/snapshots
# ---------------------------------------------------------------------------


def test_snapshots_list_empty() -> None:
    """Returns an empty list when no snapshots exist."""
    app, mock_db = _make_app()
    mock_db.scalars.return_value.all.return_value = []

    client = TestClient(app)
    r = client.get("/api/v1/collectors/snapshots")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /collectors/agents/{agent_id} — 404
# ---------------------------------------------------------------------------


def test_get_agent_404() -> None:
    """Returns 404 when the requested agent does not exist."""
    app, mock_db = _make_app()
    mock_db.get.return_value = None

    client = TestClient(app)
    r = client.get(f"/api/v1/collectors/agents/{uuid.uuid4()}")

    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()
