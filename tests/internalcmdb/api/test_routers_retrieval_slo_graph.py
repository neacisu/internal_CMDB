"""Tests for /retrieval, /slo, and /graph routers."""
from __future__ import annotations
import uuid
import unittest.mock as mock
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from internalcmdb.api.deps import get_async_session, get_db
from internalcmdb.api.routers.graph import router as graph_router
from internalcmdb.api.routers.retrieval import router as retrieval_router
from internalcmdb.api.routers.slo import router as slo_router


def _retrieval_app():
    app = FastAPI()
    mock_db = MagicMock()
    mock_q = MagicMock()
    mock_db.query.return_value = mock_q
    mock_q.filter.return_value = mock_q
    mock_q.order_by.return_value = mock_q
    mock_q.count.return_value = 0
    mock_q.offset.return_value = mock_q
    mock_q.limit.return_value = mock_q
    mock_q.all.return_value = []
    app.dependency_overrides[get_db] = lambda: mock_db
    app.include_router(retrieval_router, prefix="/api/v1")
    return app, mock_db


def _async_app(router):
    app = FastAPI()
    mock_session = AsyncMock()
    app.dependency_overrides[get_async_session] = lambda: mock_session
    app.include_router(router, prefix="/api/v1")
    return app, mock_session


def test_list_task_types():
    app, _ = _retrieval_app()
    r = TestClient(app).get("/api/v1/retrieval/task-types")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 1
    assert "task_code" in data[0]


def test_list_packs_empty():
    app, _ = _retrieval_app()
    r = TestClient(app).get("/api/v1/retrieval/packs")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_list_chunks_empty():
    app, _ = _retrieval_app()
    r = TestClient(app).get("/api/v1/retrieval/chunks")
    assert r.status_code == 200


def test_list_chunks_version_filter():
    app, _ = _retrieval_app()
    vid = str(uuid.uuid4())
    r = TestClient(app).get(f"/api/v1/retrieval/chunks?document_version_id={vid}")
    assert r.status_code == 200


def test_slo_list_definitions_empty():
    app, mock_session = _async_app(slo_router)
    result = MagicMock()
    result.fetchall.return_value = []
    mock_session.execute.return_value = result
    r = TestClient(app).get("/api/v1/slo/definitions")
    assert r.status_code == 200 and r.json() == []


def test_slo_history():
    app, mock_session = _async_app(slo_router)
    result = MagicMock()
    result.fetchall.return_value = []
    mock_session.execute.return_value = result
    r = TestClient(app).get("/api/v1/slo/slo-123/history")
    assert r.status_code == 200
    assert r.json()["slo_id"] == "slo-123"


def test_slo_dashboard_empty():
    app, mock_session = _async_app(slo_router)
    result = MagicMock()
    result.fetchall.return_value = []
    mock_session.execute.return_value = result
    r = TestClient(app).get("/api/v1/slo/dashboard")
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_slo_define():
    from internalcmdb.slo.framework import SLOFramework
    app, mock_session = _async_app(slo_router)
    mock_fw = AsyncMock(spec=SLOFramework)
    mock_fw.define_slo.return_value = {"slo_id": "new-slo", "status": "created"}
    with mock.patch("internalcmdb.api.routers.slo.SLOFramework", return_value=mock_fw):
        r = TestClient(app).post(
            "/api/v1/slo/define",
            json={"service_id": "svc-001", "sli_type": "availability", "target": 0.99, "window_days": 30},
        )
    assert r.status_code == 200


def test_slo_budget_not_found():
    from internalcmdb.slo.framework import SLOFramework
    app, mock_session = _async_app(slo_router)
    mock_fw = AsyncMock(spec=SLOFramework)
    mock_fw.current_budget.return_value = {"error": "SLO not found"}
    with mock.patch("internalcmdb.api.routers.slo.SLOFramework", return_value=mock_fw):
        r = TestClient(app).get("/api/v1/slo/slo-999/budget")
    assert r.status_code == 404


def test_graph_topology_empty():
    import networkx as nx
    app, mock_session = _async_app(graph_router)
    g = nx.DiGraph()
    mock_kg = mock.AsyncMock()
    mock_kg.build_graph.return_value = g
    mock_kg._graph = g
    mock_kg.to_json = MagicMock(return_value={"nodes": [], "edges": []})
    with mock.patch("internalcmdb.api.routers.graph.InfrastructureKnowledgeGraph", return_value=mock_kg):
        r = TestClient(app).get("/api/v1/graph/topology")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data and "edges" in data


def test_graph_entity_dependencies_missing():
    import networkx as nx
    app, mock_session = _async_app(graph_router)
    g = nx.DiGraph()
    mock_kg = mock.AsyncMock()
    mock_kg.build_graph.return_value = g
    with mock.patch("internalcmdb.api.routers.graph.InfrastructureKnowledgeGraph", return_value=mock_kg):
        r = TestClient(app).get("/api/v1/graph/entity/nonexistent-id/dependencies")
    assert r.status_code == 200
    assert r.json()["upstream"] == [] and r.json()["downstream"] == []


def test_graph_impact_analysis():
    app, mock_session = _async_app(graph_router)
    mock_kg = mock.AsyncMock()
    mock_kg.impact_analysis.return_value = {"entity_id": "e1", "action": "shutdown", "affected": [], "count": 0}
    with mock.patch("internalcmdb.api.routers.graph.InfrastructureKnowledgeGraph", return_value=mock_kg):
        r = TestClient(app).post("/api/v1/graph/impact-analysis", json={"entity_id": "host-001", "action_type": "shutdown"})
    assert r.status_code == 200 and "entity_id" in r.json()


def test_graph_critical_paths():
    import networkx as nx
    app, mock_session = _async_app(graph_router)
    g = nx.DiGraph()
    g.add_node("h1", kind="host", label="host1")
    g.add_node("h2", kind="host", label="host2")
    g.add_edge("h1", "h2")
    mock_kg = mock.AsyncMock()
    mock_kg.build_graph.return_value = g
    with mock.patch("internalcmdb.api.routers.graph.InfrastructureKnowledgeGraph", return_value=mock_kg):
        r = TestClient(app).get("/api/v1/graph/critical-paths")
    assert r.status_code == 200 and "critical_nodes" in r.json()


def test_graph_circular_deps_empty():
    app, mock_session = _async_app(graph_router)
    mock_kg = mock.AsyncMock()
    mock_kg.detect_circular_dependencies.return_value = []
    with mock.patch("internalcmdb.api.routers.graph.InfrastructureKnowledgeGraph", return_value=mock_kg):
        r = TestClient(app).get("/api/v1/graph/circular-deps")
    assert r.status_code == 200
    assert r.json()["cycles"] == [] and r.json()["count"] == 0
