"""Tests for the metrics_live router (async get_async_session)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.routers.metrics_live import router as metrics_router


async def _empty_session():
    """Async session mock returning empty/None results for all queries."""
    session = AsyncMock()
    empty_result = MagicMock()
    empty_result.fetchall.return_value = []
    empty_result.fetchone.return_value = None
    session.execute = AsyncMock(return_value=empty_result)
    yield session


def _make_app(session_factory=None) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_async_session] = session_factory or _empty_session
    app.include_router(metrics_router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# GET /metrics/hosts/{code}/live
# ---------------------------------------------------------------------------


def test_host_live_404() -> None:
    """Returns 404 when the host code does not exist."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/metrics/hosts/nonexistent-host/live")

    assert r.status_code == 404
    assert "Host not found" in r.json()["detail"]


def test_host_live_found() -> None:
    """Returns host info and metrics list when host exists."""

    async def _session_with_host():
        host_row = MagicMock()
        host_row._mapping = {
            "host_id": "11111111-1111-1111-1111-111111111111",
            "host_code": "test-01",
            "hostname": "test-host-01",
        }

        host_result = MagicMock()
        host_result.fetchone.return_value = host_row

        metrics_result = MagicMock()
        metrics_result.fetchall.return_value = []

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[host_result, metrics_result])
        yield session

    client = TestClient(_make_app(_session_with_host))
    r = client.get("/api/v1/metrics/hosts/test-01/live")

    assert r.status_code == 200
    data = r.json()
    assert "host" in data
    assert "metrics" in data
    assert data["host"]["host_code"] == "test-01"
    assert data["metrics"] == []


# ---------------------------------------------------------------------------
# GET /metrics/hosts/{code}/series
# ---------------------------------------------------------------------------


def test_host_series_404() -> None:
    """Returns 404 when the host code does not exist for series query."""
    client = TestClient(_make_app())
    r = client.get(
        "/api/v1/metrics/hosts/nonexistent-host/series",
        params={"metric_name": "cpu_usage_pct"},
    )

    assert r.status_code == 404
    assert "Host not found" in r.json()["detail"]


def test_host_series_found_empty() -> None:
    """Returns an empty points list for a host with no metric data."""

    async def _session_with_host():
        host_row = MagicMock()
        host_row.__getitem__ = lambda self, _: "22222222-2222-2222-2222-222222222222"

        host_result = MagicMock()
        host_result.fetchone.return_value = host_row

        series_result = MagicMock()
        series_result.fetchall.return_value = []

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[host_result, series_result])
        yield session

    client = TestClient(_make_app(_session_with_host))
    r = client.get(
        "/api/v1/metrics/hosts/test-02/series",
        params={"metric_name": "memory_usage_pct"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["host_code"] == "test-02"
    assert data["metric_name"] == "memory_usage_pct"
    assert data["points"] == []
    assert data["next_before"] is None


# ---------------------------------------------------------------------------
# GET /metrics/gpu/live
# ---------------------------------------------------------------------------


def test_gpu_live_empty() -> None:
    """Returns an empty list when no GPU devices are tracked."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/metrics/gpu/live")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /metrics/llm/live
# ---------------------------------------------------------------------------


def test_llm_live_empty() -> None:
    """Returns the expected structure with an empty models list."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/metrics/llm/live")

    assert r.status_code == 200
    data = r.json()
    assert data["window"] == "1h"
    assert data["models"] == []


# ---------------------------------------------------------------------------
# GET /metrics/fleet/matrix
# ---------------------------------------------------------------------------


def test_fleet_matrix_empty() -> None:
    """Returns hosts=[], total=0, limit=200 when no recent metric data exists."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/metrics/fleet/matrix")

    assert r.status_code == 200
    data = r.json()
    assert data["hosts"] == []
    assert data["total"] == 0
    assert data["limit"] == 200


def test_fleet_matrix_custom_limit() -> None:
    """Respects the limit query parameter."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/metrics/fleet/matrix", params={"limit": "50"})

    assert r.status_code == 200
    data = r.json()
    assert data["limit"] == 50
