"""Tests for reactor RC-1 PolicyEnforcer gate."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from internalcmdb.nervous.event_bus import Event
from internalcmdb.nervous.reactor import STREAM_CONSCIOUSNESS_ALERT, STREAM_MOTOR_ACTION, ReactiveLoop
from internalcmdb.retrieval.task_types import RiskClass


def _make_event(**kwargs) -> Event:
    defaults = {
        "event_id": "evt-001",
        "event_type": "anomaly",
        "correlation_id": "corr-001",
        "payload": {"action_type": "read", "target": "host-01"},
        "risk_class": RiskClass.RC1_READ_ONLY.value,
        "timestamp": "2024-01-01T00:00:00+00:00",
        "source": "test",
    }
    defaults.update(kwargs)
    return Event(**defaults)


@pytest.mark.asyncio
async def test_rc1_policy_block_routes_to_alert() -> None:
    bus = AsyncMock()
    bus.publish = AsyncMock(return_value="msg-001")
    rl = ReactiveLoop(bus, AsyncMock())

    with patch.object(
        ReactiveLoop,
        "_check_policy",
        new=AsyncMock(return_value="Policy violation"),
    ):
        await rl.process_event(_make_event())

    stream = bus.publish.call_args[0][0]
    assert stream == STREAM_CONSCIOUSNESS_ALERT


@pytest.mark.asyncio
async def test_rc1_policy_pass_routes_to_motor() -> None:
    bus = AsyncMock()
    bus.publish = AsyncMock(return_value="msg-001")
    rl = ReactiveLoop(bus, AsyncMock())

    with patch.object(ReactiveLoop, "_check_policy", new=AsyncMock(return_value=None)):
        await rl.process_event(_make_event())

    stream = bus.publish.call_args[0][0]
    assert stream == STREAM_MOTOR_ACTION
