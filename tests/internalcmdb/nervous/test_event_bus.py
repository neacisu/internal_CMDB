"""Tests for the nervous-system EventBus (Redis Streams backbone)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.nervous.event_bus import Event, EventBus


# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------


class TestEvent:
    def test_auto_generates_fields(self) -> None:
        evt = Event(event_type="test.created", source="unit-test")
        assert evt.event_id
        assert evt.timestamp
        assert evt.correlation_id
        assert evt.event_type == "test.created"

    def test_to_dict_serialises_payload(self) -> None:
        evt = Event(
            event_type="metric",
            source="agent",
            payload={"cpu": 42.0},
        )
        d = evt.to_dict()
        assert json.loads(d["payload"]) == {"cpu": 42.0}
        assert d["event_type"] == "metric"

    def test_from_dict_round_trip(self) -> None:
        original = Event(
            event_type="sensor:ingest",
            source="hz.113",
            payload={"disk_pct": 88},
            risk_class="RC-2",
        )
        d = original.to_dict()
        restored = Event.from_dict(d)
        assert restored.event_type == original.event_type
        assert restored.source == original.source
        assert restored.payload == original.payload
        assert restored.risk_class == "RC-2"

    def test_from_dict_handles_raw_payload_dict(self) -> None:
        data = {
            "event_type": "test",
            "payload": {"key": "value"},
        }
        evt = Event.from_dict(data)
        assert evt.payload == {"key": "value"}

    def test_from_dict_handles_invalid_json_payload(self) -> None:
        data = {"event_type": "test", "payload": "not-json{{{"}
        evt = Event.from_dict(data)
        assert evt.payload == {}


# ---------------------------------------------------------------------------
# EventBus — publish / subscribe / ack with mock Redis
# ---------------------------------------------------------------------------


class TestEventBus:
    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        redis = MagicMock()
        redis.xadd = AsyncMock(return_value="1234567890-0")
        redis.xreadgroup = AsyncMock(return_value=[])
        redis.xack = AsyncMock()
        redis.xgroup_create = AsyncMock()
        redis.aclose = AsyncMock()
        return redis

    @pytest.fixture
    def bus(self, mock_redis: MagicMock) -> EventBus:
        b = EventBus.__new__(EventBus)
        b._redis = mock_redis
        return b

    @pytest.mark.asyncio
    async def test_publish(self, bus: EventBus, mock_redis: MagicMock) -> None:
        evt = Event(event_type="sensor:ingest", source="test")
        msg_id = await bus.publish("sensor:ingest", evt)
        assert msg_id == "1234567890-0"
        mock_redis.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_returns_events(
        self, bus: EventBus, mock_redis: MagicMock
    ) -> None:
        mock_redis.xreadgroup.return_value = [
            (
                "sensor:ingest",
                [
                    (
                        "111-0",
                        {
                            "event_id": "e1",
                            "event_type": "test",
                            "correlation_id": "c1",
                            "timestamp": "2025-01-01T00:00:00",
                            "source": "unit",
                            "payload": "{}",
                            "risk_class": "RC-1",
                        },
                    ),
                ],
            ),
        ]
        events = await bus.subscribe("sensor:ingest", "grp", "consumer-1")
        assert len(events) == 1
        assert events[0].event_type == "test"
        assert events[0].redis_message_id == "111-0"

    @pytest.mark.asyncio
    async def test_subscribe_empty(self, bus: EventBus, mock_redis: MagicMock) -> None:
        mock_redis.xreadgroup.return_value = []
        events = await bus.subscribe("sensor:ingest", "grp", "c1")
        assert events == []

    @pytest.mark.asyncio
    async def test_ack(self, bus: EventBus, mock_redis: MagicMock) -> None:
        await bus.ack("sensor:ingest", "grp", "111-0")
        mock_redis.xack.assert_called_once_with("sensor:ingest", "grp", "111-0")

    @pytest.mark.asyncio
    async def test_ensure_groups_creates_all_streams(
        self, bus: EventBus, mock_redis: MagicMock
    ) -> None:
        await bus.ensure_groups()
        assert mock_redis.xgroup_create.call_count == len(EventBus.STREAMS)

    @pytest.mark.asyncio
    async def test_ensure_group_ignores_busygroup(
        self, bus: EventBus, mock_redis: MagicMock
    ) -> None:
        from redis.exceptions import RedisError  # noqa: PLC0415

        mock_redis.xgroup_create.side_effect = RedisError("BUSYGROUP")
        await bus._ensure_group("sensor:ingest", "test-group")

    @pytest.mark.asyncio
    async def test_close(self, bus: EventBus, mock_redis: MagicMock) -> None:
        await bus.close()
        mock_redis.aclose.assert_called_once()
