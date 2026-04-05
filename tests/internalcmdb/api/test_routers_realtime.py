"""Tests for internalcmdb.api.routers.realtime — pure function coverage."""

from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _safe_json
# ---------------------------------------------------------------------------


def test_safe_json_basic():
    from internalcmdb.api.routers.realtime import _safe_json

    row = MagicMock()
    row._mapping.items.return_value = [("key", "value"), ("num", 42)]
    result = _safe_json(row)
    assert result["key"] == "value"
    assert result["num"] == 42


def test_safe_json_datetime_converted_to_isoformat():
    from internalcmdb.api.routers.realtime import _safe_json

    dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    row = MagicMock()
    row._mapping.items.return_value = [("created_at", dt)]
    result = _safe_json(row)
    assert result["created_at"] == dt.isoformat()


def test_safe_json_uuid_converted_to_str():
    from internalcmdb.api.routers.realtime import _safe_json

    uid = uuid.uuid4()
    row = MagicMock()
    row._mapping.items.return_value = [("id", uid)]
    result = _safe_json(row)
    assert result["id"] == str(uid)


def test_safe_json_none_value_preserved():
    from internalcmdb.api.routers.realtime import _safe_json

    row = MagicMock()
    row._mapping.items.return_value = [("field", None)]
    result = _safe_json(row)
    assert result["field"] is None


def test_safe_json_bool_preserved():
    from internalcmdb.api.routers.realtime import _safe_json

    row = MagicMock()
    row._mapping.items.return_value = [("active", True), ("deleted", False)]
    result = _safe_json(row)
    assert result["active"] is True
    assert result["deleted"] is False


def test_safe_json_float_preserved():
    from internalcmdb.api.routers.realtime import _safe_json

    row = MagicMock()
    row._mapping.items.return_value = [("score", 3.14)]
    result = _safe_json(row)
    assert result["score"] == pytest.approx(3.14)


def test_safe_json_mixed_types():
    from internalcmdb.api.routers.realtime import _safe_json

    dt = datetime(2025, 1, 1)
    uid = uuid.uuid4()
    row = MagicMock()
    row._mapping.items.return_value = [
        ("ts", dt),
        ("id", uid),
        ("label", "hello"),
        ("count", 7),
        ("ratio", 0.5),
        ("flag", False),
        ("nothing", None),
    ]
    result = _safe_json(row)
    assert result["ts"] == dt.isoformat()
    assert result["id"] == str(uid)
    assert result["label"] == "hello"
    assert result["count"] == 7
    assert result["ratio"] == pytest.approx(0.5)
    assert result["flag"] is False
    assert result["nothing"] is None


# ---------------------------------------------------------------------------
# _authenticate_ws
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_ws_dev_mode_returns_true():
    from internalcmdb.api.routers.realtime import _authenticate_ws

    ws = MagicMock()
    with patch("internalcmdb.api.middleware.rbac._DEV_MODE", True):
        result = await _authenticate_ws(ws)
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_ws_no_token_closes_and_returns_false():
    from internalcmdb.api.routers.realtime import _authenticate_ws

    ws = MagicMock()
    ws.query_params = {}
    ws.close = AsyncMock()

    with patch("internalcmdb.api.middleware.rbac._DEV_MODE", False):
        result = await _authenticate_ws(ws)

    assert result is False
    ws.close.assert_awaited_once_with(code=4001, reason="Missing auth token")


@pytest.mark.asyncio
async def test_authenticate_ws_invalid_token_closes_and_returns_false():
    from internalcmdb.api.routers.realtime import _authenticate_ws

    ws = MagicMock()
    ws.query_params = {"token": "bad-token"}
    ws.close = AsyncMock()

    with (
        patch("internalcmdb.api.middleware.rbac._DEV_MODE", False),
        patch("internalcmdb.api.middleware.rbac._decode_jwt_claims", return_value=None),
    ):
        result = await _authenticate_ws(ws)

    assert result is False
    ws.close.assert_awaited_once_with(code=4003, reason="Invalid auth token")


@pytest.mark.asyncio
async def test_authenticate_ws_valid_token_returns_true():
    from internalcmdb.api.routers.realtime import _authenticate_ws

    ws = MagicMock()
    ws.query_params = {"token": "valid-token"}

    with (
        patch("internalcmdb.api.middleware.rbac._DEV_MODE", False),
        patch("internalcmdb.api.middleware.rbac._decode_jwt_claims", return_value={"sub": "user1"}),
    ):
        result = await _authenticate_ws(ws)

    assert result is True


# ---------------------------------------------------------------------------
# _filter_new_insights
# ---------------------------------------------------------------------------


def test_filter_new_insights_returns_only_new():
    from internalcmdb.api.routers.realtime import _filter_new_insights

    seen: deque[str] = deque(maxlen=500)
    seen.append("existing-id")

    def make_row(iid: str):
        row = MagicMock()
        row._mapping.items.return_value = [("insight_id", iid), ("title", f"Insight {iid}")]
        return row

    rows = [make_row("existing-id"), make_row("new-id-1"), make_row("new-id-2")]
    result = _filter_new_insights(rows, seen)

    assert len(result) == 2
    ids = [r["insight_id"] for r in result]
    assert "new-id-1" in ids
    assert "new-id-2" in ids
    assert "existing-id" not in ids


def test_filter_new_insights_updates_seen_ids():
    from internalcmdb.api.routers.realtime import _filter_new_insights

    seen: deque[str] = deque(maxlen=500)

    row = MagicMock()
    row._mapping.items.return_value = [("insight_id", "abc-123")]
    _filter_new_insights([row], seen)

    assert "abc-123" in seen


def test_filter_new_insights_empty_rows():
    from internalcmdb.api.routers.realtime import _filter_new_insights

    seen: deque[str] = deque(maxlen=500)
    result = _filter_new_insights([], seen)
    assert result == []


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------


def test_router_is_api_router():
    from fastapi import APIRouter

    from internalcmdb.api.routers.realtime import router

    assert isinstance(router, APIRouter)


def test_router_has_realtime_tag():
    from internalcmdb.api.routers.realtime import router

    assert "realtime" in router.tags


def test_router_has_websocket_routes():
    from internalcmdb.api.routers.realtime import router

    paths = {r.path for r in router.routes}
    assert "/ws/metrics" in paths
    assert "/ws/events" in paths
    assert "/ws/insights" in paths
    assert "/ws/hitl" in paths


def test_constants_have_expected_values():
    from internalcmdb.api.routers.realtime import (
        _HEARTBEAT_INTERVAL,
        _HITL_PUSH_INTERVAL,
        _INSIGHTS_PUSH_INTERVAL,
        _MAX_SEEN_IDS,
        _METRICS_PUSH_INTERVAL,
    )

    assert _HEARTBEAT_INTERVAL > 0
    assert _METRICS_PUSH_INTERVAL > 0
    assert _INSIGHTS_PUSH_INTERVAL > 0
    assert _HITL_PUSH_INTERVAL > 0
    assert _MAX_SEEN_IDS > 0
