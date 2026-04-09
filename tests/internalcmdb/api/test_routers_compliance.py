"""Tests for /compliance router."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.routers.compliance import router


def _app():
    app = FastAPI()
    mock_session = AsyncMock()
    app.dependency_overrides[get_async_session] = lambda: mock_session
    app.include_router(router, prefix="/api/v1")
    return app, mock_session


def _mgr():
    mgr = AsyncMock()
    mgr.get_ai_inventory.return_value = [
        {
            "system_name": "CMDB-Cognitive",
            "risk_level": "low",
            "purpose": "infra analysis",
            "data_types": ["metrics"],
            "model_ids": ["llama3"],
            "deployed_since": "2024-01-01",
            "owner_team": "platform",
            "human_oversight_level": "full",
            "last_audit": None,
        }
    ]
    mgr.generate_compliance_report.return_value = "EU AI Act report"
    mgr.audit_data_lineage.return_value = {
        "entity_id": "host-001",
        "lineage_stages": [],
        "checked_at": "2024-01-01T00:00:00+00:00",
    }
    mgr.check_article_12.return_value = {
        "audit_trail": True,
        "audit_trail_detail": "Ledger",
        "decision_logging": True,
        "decision_logging_detail": "Logged",
        "model_versioning": True,
        "model_versioning_detail": "MLflow",
        "data_lineage": True,
        "data_lineage_detail": "Tracked",
        "hitl_feedback": True,
        "hitl_feedback_detail": "Active",
        "overall_compliant": True,
        "checked_at": "2024-01-01T00:00:00+00:00",
    }
    return mgr


def test_ai_inventory():
    app, _ = _app()
    with patch("internalcmdb.governance.ai_compliance.AIComplianceManager", return_value=_mgr()):
        r = TestClient(app).get("/api/v1/compliance/inventory")
    assert r.status_code == 200
    assert r.json()[0]["system_name"] == "CMDB-Cognitive"


def test_compliance_report():
    app, _ = _app()
    with patch("internalcmdb.governance.ai_compliance.AIComplianceManager", return_value=_mgr()):
        r = TestClient(app).get("/api/v1/compliance/report")
    assert r.status_code == 200
    assert "report" in r.json()
    assert "generated_at" in r.json()


def test_data_lineage():
    app, _ = _app()
    with patch("internalcmdb.governance.ai_compliance.AIComplianceManager", return_value=_mgr()):
        r = TestClient(app).get("/api/v1/compliance/data-lineage/host-001")
    assert r.status_code == 200
    assert r.json()["entity_id"] == "host-001"


def test_article_12_check():
    app, _ = _app()
    with patch("internalcmdb.governance.ai_compliance.AIComplianceManager", return_value=_mgr()):
        r = TestClient(app).get("/api/v1/compliance/article-12")
    assert r.status_code == 200
    assert r.json()["overall_compliant"] is True
