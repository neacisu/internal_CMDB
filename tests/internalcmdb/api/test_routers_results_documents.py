"""Tests for results and documents routers (filesystem-backed, no DB)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.routers.documents import _to_title
from internalcmdb.api.routers.documents import router as documents_router
from internalcmdb.api.routers.results import RESULT_TYPES
from internalcmdb.api.routers.results import router as results_router


def _app_results() -> FastAPI:
    app = FastAPI()
    app.include_router(results_router, prefix="/api/v1")
    return app


def _app_docs() -> FastAPI:
    app = FastAPI()
    app.include_router(documents_router, prefix="/api/v1")
    return app


def test_list_result_types() -> None:
    client = TestClient(_app_results())
    r = client.get("/api/v1/results/types")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    keys = {x["result_type"] for x in data}
    assert "ssh_connectivity" in keys
    assert len(keys) == len(RESULT_TYPES)


def test_get_current_unknown_type() -> None:
    client = TestClient(_app_results())
    r = client.get("/api/v1/results/not_a_real_type/current")
    assert r.status_code == 404


def test_documents_index_or_empty() -> None:
    client = TestClient(_app_docs())
    r = client.get("/api/v1/documents/index")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_documents_to_title_helper() -> None:
    assert "architecture" in _to_title("ADR-001-architecture").lower()
