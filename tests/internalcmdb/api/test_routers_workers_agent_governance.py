"""Tests for workers, agent, and governance routers with mocked sync DB."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_db
from internalcmdb.api.routers.agent import router as agent_router
from internalcmdb.api.routers.governance import router as gov_router
from internalcmdb.api.routers.workers import router as workers_router


def _mock_db_app() -> tuple[FastAPI, MagicMock]:
    app = FastAPI()
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.include_router(workers_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(gov_router, prefix="/api/v1")
    return app, mock_db


def test_workers_list_scripts() -> None:
    app, _ = _mock_db_app()
    client = TestClient(app)
    r = client.get("/api/v1/workers/scripts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 5


def test_workers_list_cognitive_tasks() -> None:
    app, _ = _mock_db_app()
    client = TestClient(app)
    r = client.get("/api/v1/workers/cognitive-tasks")
    assert r.status_code == 200
    names = {x["task_name"] for x in r.json()}
    assert "cognitive_health_score" in names


def test_workers_get_job_404() -> None:
    app, mock_db = _mock_db_app()
    mock_db.get.return_value = None
    client = TestClient(app)
    jid = str(uuid.uuid4())
    r = client.get(f"/api/v1/workers/jobs/{jid}")
    assert r.status_code == 404


def test_agent_templates_mock() -> None:
    app, mock_db = _mock_db_app()
    mock_db.scalars.return_value.all.return_value = []
    client = TestClient(app)
    r = client.get("/api/v1/agent/templates")
    assert r.status_code == 200
    assert r.json() == []


def test_governance_policies_mock() -> None:
    app, mock_db = _mock_db_app()
    mock_db.scalars.return_value.all.return_value = []
    client = TestClient(app)
    r = client.get("/api/v1/governance/policies")
    assert r.status_code == 200
