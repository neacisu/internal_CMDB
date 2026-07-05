"""Tests for Alertmanager webhook receiver."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from internalcmdb.api.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_alert_webhook_rejects_non_localhost(client: TestClient) -> None:
    with patch(
        "internalcmdb.api.routers.events._ALLOWED_CLIENTS",
        frozenset({"127.0.0.1"}),
    ):
        response = client.post(
            "/api/v1/events/alert",
            json={"alerts": []},
        )
    assert response.status_code == 403


def test_alert_webhook_publishes_to_event_bus(client: TestClient) -> None:
    payload = {
        "receiver": "internalcmdb-eventbus",
        "status": "firing",
        "groupKey": "{}:{alertname=\"TestAlert\"}",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "TestAlert", "severity": "critical"},
                "annotations": {"summary": "test"},
                "startsAt": "2026-07-05T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "fingerprint": "abc123",
            }
        ],
    }

    with patch(
        "internalcmdb.api.routers.events._ALLOWED_CLIENTS",
        frozenset({"127.0.0.1", "testclient"}),
    ), patch("internalcmdb.api.routers.events.EventBus") as mock_bus_cls:
        mock_bus = AsyncMock()
        mock_bus.publish = AsyncMock(return_value="1-0")
        mock_bus.close = AsyncMock()
        mock_bus_cls.return_value = mock_bus

        response = client.post("/api/v1/events/alert", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "published": "1"}
    mock_bus.publish.assert_awaited_once()
    mock_bus.close.assert_awaited_once()
