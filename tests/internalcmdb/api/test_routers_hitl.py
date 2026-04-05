"""Tests for the HITL router (async get_async_session)."""

from __future__ import annotations

import pytest

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.routers.hitl import router as hitl_router


async def _empty_session():
    """Async session mock where all queries return empty results."""
    session = AsyncMock()
    empty_result = MagicMock()
    empty_result.fetchall.return_value = []
    empty_result.fetchone.return_value = None
    session.execute = AsyncMock(return_value=empty_result)
    yield session


def _make_app(session_factory=None) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_async_session] = session_factory or _empty_session
    app.include_router(hitl_router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# GET /hitl/queue
# ---------------------------------------------------------------------------


def test_hitl_queue_empty() -> None:
    """Returns an empty list when no pending items exist."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/hitl/queue")

    assert r.status_code == 200
    assert r.json() == []


def test_hitl_queue_with_status_filter() -> None:
    """Accepts an optional status query parameter."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/hitl/queue", params={"status": "approved"})

    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# GET /hitl/queue/{item_id}
# ---------------------------------------------------------------------------


def test_hitl_item_404() -> None:
    """Returns 404 when a specific item does not exist."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/hitl/queue/nonexistent-item-id")

    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_hitl_item_found() -> None:
    """Returns the item dict when fetchone returns a matching row."""

    async def _session_with_row():
        row = MagicMock()
        row._mapping = {
            "item_id": "abc-123",
            "item_type": "config_change",
            "risk_class": "RC-2",
            "priority": "high",
            "status": "pending",
            "source_event_id": None,
            "correlation_id": None,
            "context_jsonb": None,
            "llm_suggestion": None,
            "llm_confidence": None,
            "llm_model_used": None,
            "decided_by": None,
            "decision": None,
            "decision_reason": None,
            "decision_jsonb": None,
            "created_at": None,
            "expires_at": None,
            "decided_at": None,
            "escalated_to": None,
            "escalation_count": 0,
        }
        result = MagicMock()
        result.fetchone.return_value = row
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        yield session

    client = TestClient(_make_app(_session_with_row))
    r = client.get("/api/v1/hitl/queue/abc-123")

    assert r.status_code == 200
    data = r.json()
    assert data["item_id"] == "abc-123"
    assert data["status"] == "pending"


# ---------------------------------------------------------------------------
# GET /hitl/stats
# ---------------------------------------------------------------------------


def test_hitl_stats_empty() -> None:
    """Returns the correct stats structure when no items exist."""

    async def _stats_session():
        stats_row = MagicMock()
        stats_row._mapping = {
            "pending_count": 0,
            "escalated_count": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "blocked_count": 0,
            "avg_decision_time_seconds": None,
        }
        first_result = MagicMock()
        first_result.fetchone.return_value = stats_row

        acc_result = MagicMock()
        acc_result.fetchone.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[first_result, acc_result])
        yield session

    client = TestClient(_make_app(_stats_session))
    r = client.get("/api/v1/hitl/stats")

    assert r.status_code == 200
    data = r.json()
    assert data["pending_count"] == 0
    assert data["approved_count"] == 0
    assert data["rejected_count"] == 0
    assert data["accuracy"] is None


def test_hitl_stats_with_counts() -> None:
    """Reflects non-zero counts from the DB in the response."""

    async def _stats_session_counts():
        stats_row = MagicMock()
        stats_row._mapping = {
            "pending_count": 3,
            "escalated_count": 1,
            "approved_count": 10,
            "rejected_count": 2,
            "blocked_count": 0,
            "avg_decision_time_seconds": 120.5,
        }
        first_result = MagicMock()
        first_result.fetchone.return_value = stats_row

        acc_result = MagicMock()
        acc_result.fetchone.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[first_result, acc_result])
        yield session

    client = TestClient(_make_app(_stats_session_counts))
    r = client.get("/api/v1/hitl/stats")

    assert r.status_code == 200
    data = r.json()
    assert data["pending_count"] == 3
    assert data["approved_count"] == 10
    assert data["avg_decision_time_seconds"] == pytest.approx(120.5)


# ---------------------------------------------------------------------------
# GET /hitl/history
# ---------------------------------------------------------------------------


def test_hitl_history_empty() -> None:
    """Returns empty list for decision history when no decided items exist."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/hitl/history")

    assert r.status_code == 200
    assert r.json() == []
