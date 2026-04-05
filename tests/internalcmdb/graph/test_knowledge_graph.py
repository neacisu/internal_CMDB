"""Tests for graph.knowledge_graph — InfrastructureKnowledgeGraph."""
from __future__ import annotations
import unittest.mock as mock
from unittest.mock import AsyncMock, MagicMock
import networkx as nx
import pytest
from internalcmdb.graph.knowledge_graph import InfrastructureKnowledgeGraph, _ci_confidence, _service_dependency_target_id


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


def test_service_dependency_target_id_instance():
    row = MagicMock()
    row.target_service_instance_id = "inst-001"
    row.target_shared_service_id = None
    assert _service_dependency_target_id(row) == "inst-001"


def test_service_dependency_target_id_shared_service():
    row = MagicMock()
    row.target_service_instance_id = None
    row.target_shared_service_id = "svc-001"
    assert _service_dependency_target_id(row) == "svc-001"


def test_service_dependency_target_id_none():
    row = MagicMock()
    row.target_service_instance_id = None
    row.target_shared_service_id = None
    assert _service_dependency_target_id(row) is None


def test_ci_confidence_with_value():
    row = MagicMock()
    row.confidence = 0.85
    assert _ci_confidence(row) == 0.85


def test_ci_confidence_none():
    row = MagicMock()
    row.confidence = None
    assert _ci_confidence(row) == 1.0


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------


def _mock_session_empty():
    session = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = []
    result.scalar.return_value = False
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_build_graph_returns_digraph():
    kg = InfrastructureKnowledgeGraph(_mock_session_empty())
    g = await kg.build_graph()
    assert isinstance(g, nx.DiGraph)


@pytest.mark.asyncio
async def test_build_graph_with_hosts():
    session = AsyncMock()

    def make_result(rows):
        r = MagicMock()
        r.fetchall.return_value = rows
        r.scalar.return_value = False
        return r

    import uuid
    host_id = uuid.uuid4()
    host_row = MagicMock()
    host_row.host_id = host_id
    host_row.hostname = "hz-01.local"
    host_row.host_code = "hz-01"

    call_count = [0]
    def side_effect(stmt, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return make_result([host_row])
        return make_result([])

    session.execute.side_effect = side_effect
    kg = InfrastructureKnowledgeGraph(session)
    g = await kg.build_graph()
    assert str(host_id) in g.nodes


# ---------------------------------------------------------------------------
# impact_analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_impact_analysis_entity_not_in_graph():
    kg = InfrastructureKnowledgeGraph(_mock_session_empty())
    result = await kg.impact_analysis("nonexistent", "shutdown")
    assert result["count"] == 0
    assert result["affected"] == []


@pytest.mark.asyncio
async def test_impact_analysis_with_descendants():
    session = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = []
    result.scalar.return_value = False
    session.execute.return_value = result

    kg = InfrastructureKnowledgeGraph(session)
    g = nx.DiGraph()
    g.add_node("h1", kind="host", label="host1")
    g.add_node("s1", kind="service", label="svc1")
    g.add_edge("h1", "s1", relation="runs_on")
    kg._graph = g

    result = await kg.impact_analysis("h1", "shutdown")
    assert result["count"] == 1
    assert result["affected"][0]["entity_id"] == "s1"


# ---------------------------------------------------------------------------
# blast_radius (via build_graph with pre-built graph)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blast_radius_entity_not_in_graph():
    kg = InfrastructureKnowledgeGraph(_mock_session_empty())
    result = await kg.blast_radius("nonexistent")
    assert result == set()


@pytest.mark.asyncio
async def test_blast_radius_with_connected_nodes():
    session = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = []
    res.scalar.return_value = False
    session.execute.return_value = res

    kg = InfrastructureKnowledgeGraph(session)
    g = nx.DiGraph()
    g.add_node("h1", kind="host", label="h1")
    g.add_node("h2", kind="host", label="h2")
    g.add_edge("h1", "h2")
    kg._graph = g

    radius = await kg.blast_radius("h1", depth=3)
    assert "h2" in radius


# ---------------------------------------------------------------------------
# detect_circular_dependencies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_circular_dependencies_no_cycles():
    session = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = []
    res.scalar.return_value = False
    session.execute.return_value = res

    kg = InfrastructureKnowledgeGraph(session)
    g = nx.DiGraph()
    g.add_node("h1")
    g.add_node("h2")
    g.add_edge("h1", "h2")
    kg._graph = g

    cycles = await kg.detect_circular_dependencies()
    assert isinstance(cycles, list) and len(cycles) == 0


@pytest.mark.asyncio
async def test_detect_circular_dependencies_with_cycle():
    session = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = []
    res.scalar.return_value = False
    session.execute.return_value = res

    kg = InfrastructureKnowledgeGraph(session)
    g = nx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    kg._graph = g

    cycles = await kg.detect_circular_dependencies()
    assert len(cycles) > 0


# ---------------------------------------------------------------------------
# to_json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_to_json_structure():
    kg = InfrastructureKnowledgeGraph(_mock_session_empty())
    g = nx.DiGraph()
    g.add_node("h1", kind="host", label="host1")
    g.add_node("h2", kind="host", label="host2")
    g.add_edge("h1", "h2", relation="depends_on")
    kg._graph = g

    data = kg.to_json()
    assert "nodes" in data and "edges" in data
    node_ids = [n["id"] for n in data["nodes"]]
    assert "h1" in node_ids and "h2" in node_ids
