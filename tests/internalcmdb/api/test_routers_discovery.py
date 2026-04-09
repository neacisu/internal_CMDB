"""Tests for /discovery router — sync DB endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_db
from internalcmdb.api.routers.discovery import router


def _app():
    app = FastAPI()
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.include_router(router, prefix="/api/v1")
    return app, mock_db


def _page_setup(mock_db, items, total=0):
    mock_q = MagicMock()
    mock_db.query.return_value = mock_q
    mock_q.filter.return_value = mock_q
    mock_q.order_by.return_value = mock_q
    mock_q.count.return_value = total
    mock_q.offset.return_value = mock_q
    mock_q.limit.return_value = mock_q
    mock_q.all.return_value = items


def test_list_sources_empty():
    app, mock_db = _app()
    mock_db.scalars.return_value.all.return_value = []
    r = TestClient(app).get("/api/v1/discovery/sources")
    assert r.status_code == 200
    assert r.json() == []


def test_list_runs_empty():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    r = TestClient(app).get("/api/v1/discovery/runs")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_list_runs_source_filter():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    sid = str(uuid.uuid4())
    r = TestClient(app).get(f"/api/v1/discovery/runs?source_id={sid}")
    assert r.status_code == 200


def test_get_run_not_found():
    app, mock_db = _app()
    mock_db.get.return_value = None
    r = TestClient(app).get(f"/api/v1/discovery/runs/{uuid.uuid4()}")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_get_run_found():
    app, mock_db = _app()
    run = MagicMock()
    run.collection_run_id = uuid.uuid4()
    run.discovery_source_id = uuid.uuid4()
    run.run_code = "RUN-001"
    run.target_scope_jsonb = None
    run.started_at = "2024-01-01T00:00:00+00:00"
    run.finished_at = None
    run.executor_identity = "agent-001"
    run.raw_output_path = None
    run.summary_jsonb = None
    mock_db.get.return_value = run
    r = TestClient(app).get(f"/api/v1/discovery/runs/{run.collection_run_id}")
    assert r.status_code == 200


def test_list_facts_empty():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    r = TestClient(app).get("/api/v1/discovery/facts")
    assert r.status_code == 200


def test_list_facts_with_filters():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    rid = str(uuid.uuid4())
    r = TestClient(app).get(f"/api/v1/discovery/facts?run_id={rid}&fact_namespace=cpu")
    assert r.status_code == 200


def test_list_evidence_empty():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    r = TestClient(app).get("/api/v1/discovery/evidence")
    assert r.status_code == 200


def test_list_evidence_run_filter():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    rid = str(uuid.uuid4())
    r = TestClient(app).get(f"/api/v1/discovery/evidence?run_id={rid}")
    assert r.status_code == 200


def test_discovery_stats():
    app, mock_db = _app()
    mock_db.scalar.return_value = 5
    mock_db.execute.return_value.all.return_value = []
    r = TestClient(app).get("/api/v1/discovery/stats")
    assert r.status_code == 200
    data = r.json()
    assert "sources" in data
    assert "active_agents" in data
