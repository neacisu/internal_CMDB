"""Tests for the debug router (async get_async_session, platform_admin RBAC bypassed in dev mode)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.routers.debug import router as debug_router


async def _empty_session():
    """Async session mock returning empty results for all queries."""
    session = AsyncMock()
    empty_result = MagicMock()
    empty_result.fetchall.return_value = []
    empty_result.fetchone.return_value = None
    session.execute = AsyncMock(return_value=empty_result)
    yield session


def _make_app(session_factory=None) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_async_session] = session_factory or _empty_session
    app.include_router(debug_router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# GET /debug/traces/{correlation_id}
# ---------------------------------------------------------------------------


def test_debug_traces_404() -> None:
    """Returns 404 when no audit events match the correlation ID."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/debug/traces/nonexistent-cid")

    assert r.status_code == 404
    assert "No traces found" in r.json()["detail"]


def test_debug_traces_found() -> None:
    """Returns trace entries when matching audit events exist."""

    async def _session_with_trace():
        row = MagicMock()
        row._mapping = {
            "event_id": "evt-1",
            "event_type": "api_call",
            "actor": "system",
            "action": "test_action",
            "correlation_id": "cid-abc",
            "duration_ms": 42,
            "status": "200",
            "created_at": None,
        }
        result = MagicMock()
        result.fetchall.return_value = [row]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        yield session

    client = TestClient(_make_app(_session_with_trace))
    r = client.get("/api/v1/debug/traces/cid-abc")

    assert r.status_code == 200
    entries = r.json()
    assert isinstance(entries, list)
    assert len(entries) == 1
    assert entries[0]["correlation_id"] == "cid-abc"


# ---------------------------------------------------------------------------
# GET /debug/llm-calls
# ---------------------------------------------------------------------------


def test_debug_llm_calls_empty() -> None:
    """Returns an empty list when no LLM call events exist."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/debug/llm-calls")

    assert r.status_code == 200
    assert r.json() == []


def test_debug_llm_calls_with_filters() -> None:
    """Accepts optional model, status, and since query parameters."""
    client = TestClient(_make_app())
    r = client.get(
        "/api/v1/debug/llm-calls",
        params={"model": "gpt-4", "status": "ok", "limit": "10"},
    )

    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# GET /debug/errors
# ---------------------------------------------------------------------------


def test_debug_errors_empty() -> None:
    """Returns an empty list when no error events exist."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/debug/errors")

    assert r.status_code == 200
    assert r.json() == []


def test_debug_errors_with_severity_filter() -> None:
    """Accepts optional severity and since query parameters."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/debug/errors", params={"severity": "critical", "limit": "5"})

    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# GET /debug/guard-blocks
# ---------------------------------------------------------------------------


def test_debug_guard_blocks_empty() -> None:
    """Returns an empty list when no blocked HITL items exist."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/debug/guard-blocks")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /debug/slow-queries
# ---------------------------------------------------------------------------


def test_debug_slow_queries_empty() -> None:
    """Returns an empty list when no slow queries are recorded."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/debug/slow-queries")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /debug/event-bus/stats
# ---------------------------------------------------------------------------


def test_debug_event_bus_stats_fallback() -> None:
    """Returns a valid EventBusStats structure (Redis may be unavailable in tests)."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/debug/event-bus/stats")

    assert r.status_code == 200
    data = r.json()
    assert "stream_count" in data
    assert "total_events" in data
    assert "consumer_groups" in data
    assert isinstance(data["stream_count"], int)
