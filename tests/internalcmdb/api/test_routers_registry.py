"""Tests for /registry router — sync DB endpoints."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_db
from internalcmdb.api.routers.registry import router


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


def test_list_clusters_empty():
    app, mock_db = _app()
    mock_db.scalars.return_value.all.return_value = []
    r = TestClient(app).get("/api/v1/registry/clusters")
    assert r.status_code == 200
    assert r.json() == []


def test_list_hosts_empty():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    r = TestClient(app).get("/api/v1/registry/hosts")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_list_hosts_page_validation():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    r = TestClient(app).get("/api/v1/registry/hosts?page=0")
    assert r.status_code == 422


def test_list_hosts_with_filters():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    cid = str(uuid.uuid4())
    r = TestClient(app).get(f"/api/v1/registry/hosts?cluster_id={cid}&gpu_capable=true&docker_host=false")
    assert r.status_code == 200


def test_get_host_not_found():
    app, mock_db = _app()
    mock_db.get.return_value = None
    r = TestClient(app).get(f"/api/v1/registry/hosts/{uuid.uuid4()}")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_get_host_found():
    app, mock_db = _app()
    host = MagicMock()
    host.host_id = uuid.uuid4()
    host.cluster_id = None
    host.host_code = "hz-01"
    host.hostname = "hz-01.local"
    host.ssh_alias = None
    host.fqdn = None
    host.os_version_text = None
    host.kernel_version_text = None
    host.architecture_text = None
    host.is_gpu_capable = False
    host.is_docker_host = False
    host.is_hypervisor = False
    host.primary_public_ipv4 = None
    host.primary_private_ipv4 = None
    host.observed_hostname = None
    host.confidence_score = None
    host.metadata_jsonb = None
    host.created_at = "2024-01-01T00:00:00+00:00"
    host.updated_at = "2024-01-01T00:00:00+00:00"
    mock_db.get.return_value = host
    mock_db.scalars.return_value.first.return_value = None
    mock_db.scalars.return_value.all.return_value = []
    r = TestClient(app).get(f"/api/v1/registry/hosts/{host.host_id}")
    assert r.status_code == 200
    assert r.json()["host_code"] == "hz-01"


def test_list_gpu_devices_empty():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    r = TestClient(app).get("/api/v1/registry/gpu-devices")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_list_gpu_devices_host_filter():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    hid = str(uuid.uuid4())
    r = TestClient(app).get(f"/api/v1/registry/gpu-devices?host_id={hid}")
    assert r.status_code == 200


def test_list_network_interfaces_empty():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    r = TestClient(app).get("/api/v1/registry/network/interfaces")
    assert r.status_code == 200


def test_list_services_empty():
    app, mock_db = _app()
    mock_db.scalars.return_value.all.return_value = []
    r = TestClient(app).get("/api/v1/registry/services")
    assert r.status_code == 200
    assert r.json() == []


def test_list_service_instances_empty():
    app, mock_db = _app()
    mock_db.scalars.return_value.all.return_value = []
    sid = str(uuid.uuid4())
    r = TestClient(app).get(f"/api/v1/registry/services/{sid}/instances")
    assert r.status_code == 200


def test_list_storage_empty():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    r = TestClient(app).get("/api/v1/registry/storage")
    assert r.status_code == 200


def test_list_storage_host_filter():
    app, mock_db = _app()
    _page_setup(mock_db, [], 0)
    hid = str(uuid.uuid4())
    r = TestClient(app).get(f"/api/v1/registry/storage?host_id={hid}")
    assert r.status_code == 200
