"""Tests for the cognitive router (async get_async_session, RBAC bypassed in dev mode)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.routers.cognitive import router as cognitive_router


async def _empty_session():
    """Async session mock returning empty results for all queries."""
    session = AsyncMock()
    empty_result = MagicMock()
    empty_result.fetchall.return_value = []
    empty_result.fetchone.return_value = None
    empty_result.rowcount = 0
    session.execute = AsyncMock(return_value=empty_result)
    session.commit = AsyncMock()
    yield session


def _make_app(session_factory=None) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_async_session] = session_factory or _empty_session
    app.include_router(cognitive_router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# POST /cognitive/query
# ---------------------------------------------------------------------------


def test_cognitive_query_returns_answer() -> None:
    """POST /query returns a response with an 'answer' field (engine may be unavailable)."""
    client = TestClient(_make_app())
    r = client.post(
        "/api/v1/cognitive/query",
        json={"question": "How many hosts are online?", "top_k": 5},
    )

    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0


def test_cognitive_query_calls_engine() -> None:
    """POST /query returns an NLQueryResponse structure regardless of engine state."""
    client = TestClient(_make_app())
    r = client.post(
        "/api/v1/cognitive/query",
        json={"question": "What is the fleet status?"},
    )

    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "sources" in data
    assert "confidence" in data
    assert isinstance(data["sources"], list)


def test_cognitive_query_invalid_empty_question() -> None:
    """Returns 422 for an empty question (min_length=1 validation)."""
    client = TestClient(_make_app())
    r = client.post("/api/v1/cognitive/query", json={"question": ""})

    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /cognitive/insights
# ---------------------------------------------------------------------------


def test_cognitive_insights_empty() -> None:
    """Returns an empty list when no active insights exist."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/insights")

    assert r.status_code == 200
    assert r.json() == []


def test_cognitive_insights_invalid_status() -> None:
    """Returns 422 for an invalid status filter value."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/insights", params={"status": "invalid_status"})

    assert r.status_code == 422


def test_cognitive_insights_valid_statuses() -> None:
    """Accepts acknowledged and dismissed as valid status values."""
    client = TestClient(_make_app())
    for status in ("active", "acknowledged", "dismissed"):
        r = client.get("/api/v1/cognitive/insights", params={"status": status})
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# GET /cognitive/reports
# ---------------------------------------------------------------------------


def test_cognitive_reports_empty() -> None:
    """Returns an empty list when no reports have been generated."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/reports")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /cognitive/drift/results
# ---------------------------------------------------------------------------


def test_cognitive_drift_empty() -> None:
    """Returns an empty list when no drift results are stored."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/drift/results")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /cognitive/self-heal/playbooks
# ---------------------------------------------------------------------------


def test_cognitive_playbooks_returns_list() -> None:
    """Returns a list of playbooks (empty when DB has no active playbooks)."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/self-heal/playbooks")

    assert r.status_code == 200
    playbooks = r.json()
    assert isinstance(playbooks, list)


def test_cognitive_playbooks_fallback_on_error() -> None:
    """Falls back to hard-coded defaults when the DB raises an exception."""

    async def _session_with_error():
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("table does not exist"))
        yield session

    client = TestClient(_make_app(_session_with_error))
    r = client.get("/api/v1/cognitive/self-heal/playbooks")

    assert r.status_code == 200
    playbooks = r.json()
    assert isinstance(playbooks, list)
    assert len(playbooks) >= 1
    for pb in playbooks:
        assert "playbook_id" in pb
        assert "name" in pb


# ---------------------------------------------------------------------------
# GET /cognitive/self-heal/history
# ---------------------------------------------------------------------------


def test_cognitive_self_heal_history_empty() -> None:
    """Returns an empty list when no self-healing actions have been executed."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/self-heal/history")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /cognitive/health-scores
# ---------------------------------------------------------------------------


def test_cognitive_health_scores_empty() -> None:
    """Returns an empty list when no hosts have snapshot data."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/health-scores")

    assert r.status_code == 200
    assert isinstance(r.json(), list)
