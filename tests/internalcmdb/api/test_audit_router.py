"""Tests for internalcmdb.api.routers.audit — HTTP audit trail endpoints.

Covers:
  - list_events endpoint: pagination, filtering by actor/status/event_type
  - audit_stats endpoint: aggregation across governance tables
  - Serialisation of AuditEvent fields to dict
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.routers.audit import router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _make_audit_event(
    *,
    event_type: str = "http_request",
    actor: str | None = "admin",
    action: str = "GET /api/v1/hosts",
    target_entity: str | None = "/api/v1/hosts",
    status: str | None = "200",
    duration_ms: int | None = 15,
    ip_address: str | None = "10.0.0.1",
    risk_level: str | None = "low",
    created_at: str | None = None,
) -> MagicMock:
    e = MagicMock()
    e.audit_event_id = uuid.uuid4()
    e.event_type = event_type
    e.actor = actor
    e.action = action
    e.target_entity = target_entity
    e.correlation_id = str(uuid.uuid4())
    e.duration_ms = duration_ms
    e.status = status
    e.ip_address = ip_address
    e.risk_level = risk_level
    e.created_at = created_at or datetime.now(UTC).isoformat()
    return e


class TestListEvents:
    """Tests for GET /audit/events."""

    def test_returns_paginated_items(self) -> None:
        events = [_make_audit_event() for _ in range(3)]
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 3
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = (
            events
        )
        mock_db.query.return_value = mock_query

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/events?page=1&page_size=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["meta"]["page"] == 1
        assert data["meta"]["page_size"] == 50
        assert data["meta"]["total"] == 3

    def test_items_contain_all_required_fields(self) -> None:
        event = _make_audit_event(actor="tester", status="201", duration_ms=42)
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 1
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            event
        ]
        mock_db.query.return_value = mock_query

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/events")
        item = resp.json()["items"][0]
        required_fields = [
            "event_id",
            "event_type",
            "actor",
            "action",
            "target_entity",
            "correlation_id",
            "duration_ms",
            "status",
            "ip_address",
            "risk_level",
            "created_at",
        ]
        for field in required_fields:
            assert field in item, f"Missing field: {field}"

    def test_actor_filter_applied(self) -> None:
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []  # noqa: E501
        mock_db.query.return_value = mock_query

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/events?actor=admin")
        assert resp.status_code == 200
        mock_query.filter.assert_called_once()

    def test_status_filter_applied(self) -> None:
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []  # noqa: E501
        mock_db.query.return_value = mock_query

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/events?status=200")
        assert resp.status_code == 200
        mock_query.filter.assert_called_once()

    def test_event_type_filter_applied(self) -> None:
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []  # noqa: E501
        mock_db.query.return_value = mock_query

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/events?event_type=http_request")
        assert resp.status_code == 200
        mock_query.filter.assert_called_once()

    def test_multiple_filters_chain(self) -> None:
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []  # noqa: E501
        mock_db.query.return_value = mock_query

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/events?actor=admin&status=200&event_type=http_request")
        assert resp.status_code == 200
        assert mock_query.filter.call_count == 3

    def test_page_size_validation(self) -> None:
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/audit/events?page_size=999")
        assert resp.status_code == 422

    def test_page_validation(self) -> None:
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/audit/events?page=0")
        assert resp.status_code == 422

    def test_empty_results(self) -> None:
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 0
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []  # noqa: E501
        mock_db.query.return_value = mock_query

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["meta"]["total"] == 0

    def test_event_id_serialized_as_string(self) -> None:
        event = _make_audit_event()
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 1
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            event
        ]
        mock_db.query.return_value = mock_query

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/events")
        item = resp.json()["items"][0]
        assert isinstance(item["event_id"], str)
        uuid.UUID(item["event_id"])


class TestAuditStats:
    """Tests for GET /audit/stats."""

    def test_returns_all_aggregate_fields(self) -> None:
        mock_db = MagicMock()
        mock_db.scalar.side_effect = [
            100,  # total_events
            20,  # total_changelogs
            5,  # total_policies
            3,  # total_approvals
            15.5,  # avg_duration
            12,  # error_count
            datetime(2026, 3, 23, 12, 0, 0, tzinfo=UTC),
        ]
        mock_db.execute.side_effect = [
            MagicMock(all=lambda: [("200", 80), ("404", 15), ("500", 5)]),
            MagicMock(all=lambda: [("admin", 70), ("system", 30)]),
            MagicMock(all=lambda: [("/api/v1/hosts", 50), ("/api/v1/health", 30)]),
        ]

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/stats")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_events"] == 100
        assert data["total_changelogs"] == 20
        assert data["total_policies"] == 5
        assert data["total_approvals"] == 3
        assert data["error_count"] == 12
        assert data["avg_duration_ms"] == pytest.approx(15.5)

    def test_status_breakdown_structure(self) -> None:
        mock_db = MagicMock()
        mock_db.scalar.side_effect = [10, 0, 0, 0, None, 0, None]
        mock_db.execute.side_effect = [
            MagicMock(all=lambda: [("200", 8), ("500", 2)]),
            MagicMock(all=lambda: []),
            MagicMock(all=lambda: []),
        ]

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/stats")
        data = resp.json()
        assert len(data["status_breakdown"]) == 2
        assert data["status_breakdown"][0] == {"status": "200", "count": 8}

    def test_avg_duration_null_when_no_data(self) -> None:
        mock_db = MagicMock()
        mock_db.scalar.side_effect = [0, 0, 0, 0, None, 0, None]
        mock_db.execute.side_effect = [
            MagicMock(all=lambda: []),
            MagicMock(all=lambda: []),
            MagicMock(all=lambda: []),
        ]

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/stats")
        data = resp.json()
        assert data["avg_duration_ms"] is None

    def test_latest_event_at_null_when_no_events(self) -> None:
        mock_db = MagicMock()
        mock_db.scalar.side_effect = [0, 0, 0, 0, None, 0, None]
        mock_db.execute.side_effect = [
            MagicMock(all=lambda: []),
            MagicMock(all=lambda: []),
            MagicMock(all=lambda: []),
        ]

        app = _build_app()
        app.dependency_overrides[_get_db_dep()] = lambda: mock_db
        client = TestClient(app)

        resp = client.get("/audit/stats")
        data = resp.json()
        assert data["latest_event_at"] is None


def _get_db_dep():
    from internalcmdb.api.deps import get_db  # noqa: PLC0415

    return get_db
