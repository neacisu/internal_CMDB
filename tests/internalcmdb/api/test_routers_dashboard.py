"""Tests for the dashboard router (sync get_db)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_db
from internalcmdb.api.routers.dashboard import router as dashboard_router


def _make_app() -> tuple[FastAPI, MagicMock]:
    app = FastAPI()
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.include_router(dashboard_router, prefix="/api/v1")
    return app, mock_db


def _summary_db_mock(scalar_values: list[object]) -> MagicMock:
    """Return a mock DB configured for the /summary endpoint.

    scalar_values: [host_count, cluster_count, service_count,
                    service_instance_count, gpu_count, docker_host_count,
                    runs_24h, ram_bytes, vram_mb]
    execute calls: [last_run_row, env_rows, lc_rows]
    """
    mock_db = MagicMock()
    mock_db.scalar.side_effect = list(scalar_values)

    last_run_exec = MagicMock()
    last_run_exec.first.return_value = None

    env_exec = MagicMock()
    env_exec.all.return_value = []

    lc_exec = MagicMock()
    lc_exec.all.return_value = []

    mock_db.execute.side_effect = [last_run_exec, env_exec, lc_exec]
    return mock_db


# ---------------------------------------------------------------------------
# /dashboard/summary
# ---------------------------------------------------------------------------


def test_dashboard_summary_empty() -> None:
    """All counts are zero when DB returns 0 / None."""
    app, _ = _make_app()
    zeros: list[object] = [0, 0, 0, 0, 0, 0, 0, 0, 0]
    app.dependency_overrides[get_db] = lambda: _summary_db_mock(zeros)

    client = TestClient(app)
    r = client.get("/api/v1/dashboard/summary")

    assert r.status_code == 200
    data = r.json()
    assert data["host_count"] == 0
    assert data["cluster_count"] == 0
    assert data["service_count"] == 0
    assert data["total_ram_gb"] == 0.0
    assert data["total_gpu_vram_gb"] == 0.0
    assert data["hosts_by_environment"] == []
    assert data["hosts_by_lifecycle"] == []


def test_dashboard_summary_counts() -> None:
    """Scalar values are reflected correctly in the response."""
    app, _ = _make_app()
    # host=5, cluster=2, service=3, service_instance=10,
    # gpu_capable=1, docker=1, runs_24h=7,
    # ram_bytes=8 GiB, vram_mb=4096
    ram_bytes = 8 * (1024**3)
    vram_mb = 4096
    values: list[object] = [5, 2, 3, 10, 1, 1, 7, ram_bytes, vram_mb]
    app.dependency_overrides[get_db] = lambda: _summary_db_mock(values)

    client = TestClient(app)
    r = client.get("/api/v1/dashboard/summary")

    assert r.status_code == 200
    data = r.json()
    assert data["host_count"] == 5
    assert data["cluster_count"] == 2
    assert data["service_count"] == 3
    assert data["service_instance_count"] == 10
    assert data["gpu_count"] == 1
    assert data["docker_host_count"] == 1
    assert data["collection_runs_24h"] == 7
    assert data["total_ram_gb"] == 8.0
    assert data["total_gpu_vram_gb"] == 4.0


# ---------------------------------------------------------------------------
# /dashboard/gpu-summary
# ---------------------------------------------------------------------------


def test_dashboard_gpu_summary_empty() -> None:
    """Returns an empty list when no GPU devices are present."""
    app, mock_db = _make_app()
    mock_db.execute.return_value.all.return_value = []

    client = TestClient(app)
    r = client.get("/api/v1/dashboard/gpu-summary")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# /dashboard/disk-summary
# ---------------------------------------------------------------------------


def test_dashboard_disk_summary_empty() -> None:
    """Returns an empty list when no storage assets exist."""
    app, mock_db = _make_app()
    mock_db.execute.return_value.all.return_value = []

    client = TestClient(app)
    r = client.get("/api/v1/dashboard/disk-summary")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# /dashboard/trends
# ---------------------------------------------------------------------------


def test_dashboard_trends_empty() -> None:
    """Returns two series (host_count, fact_count) with no points."""
    app, mock_db = _make_app()
    mock_db.execute.return_value.all.return_value = []

    client = TestClient(app)
    r = client.get("/api/v1/dashboard/trends")

    assert r.status_code == 200
    series = r.json()
    assert isinstance(series, list)
    assert len(series) == 2
    names = {s["series"] for s in series}
    assert names == {"host_count", "fact_count"}
    for s in series:
        assert s["points"] == []
