"""Tests for nervous.reactor — ReactiveLoop."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from internalcmdb.nervous.event_bus import Event
from internalcmdb.nervous.reactor import (
    STREAM_CONSCIOUSNESS_ALERT,
    STREAM_CORTEX_ANOMALY,
    STREAM_IMMUNE_HITL,
    STREAM_MOTOR_ACTION,
    ReactiveLoop,
)
from internalcmdb.retrieval.task_types import RiskClass


def _make_event(event_type="ingest", risk_class=None):
    return Event(
        event_id="evt-001",
        event_type=event_type,
        correlation_id="corr-001",
        payload={"data": "test"},
        risk_class=risk_class,
        timestamp="2024-01-01T00:00:00+00:00",
        source="test",
    )


def _loop(published=None):
    bus = AsyncMock()
    bus.publish = AsyncMock(return_value="msg-001")
    bus.ack = AsyncMock()
    bus.subscribe = AsyncMock(return_value=[])
    guard = AsyncMock()
    rl = ReactiveLoop(bus, guard)
    return rl, bus


# ---------------------------------------------------------------------------
# Properties and shutdown
# ---------------------------------------------------------------------------


def test_is_running_initially_true():
    rl, _ = _loop()
    assert rl.is_running is True


def test_request_shutdown():
    rl, _ = _loop()
    rl.request_shutdown()
    assert rl.is_running is False


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_is_duplicate_false_initially():
    rl, _ = _loop()
    assert rl._is_duplicate("evt-001") is False


def test_mark_and_check_duplicate():
    rl, _ = _loop()
    rl._mark_processed("evt-001")
    assert rl._is_duplicate("evt-001") is True


def test_mark_processed_evicts_at_max_size():
    rl, _ = _loop()
    for i in range(10_001):
        rl._mark_processed(f"e-{i}")
    assert len(rl._processed_ids) <= 10_000


# ---------------------------------------------------------------------------
# process_event: ingest routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_event_ingest_publishes_to_cortex():
    rl, bus = _loop()
    evt = _make_event("ingest")
    await rl.process_event(evt)
    bus.publish.assert_called_once()
    stream_arg = bus.publish.call_args[0][0]
    assert stream_arg == STREAM_CORTEX_ANOMALY


# ---------------------------------------------------------------------------
# process_event: anomaly routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_event_anomaly_rc1_routes_to_motor():
    rl, bus = _loop()
    evt = _make_event("anomaly", risk_class=RiskClass.RC1_READ_ONLY.value)
    await rl.process_event(evt)
    stream_arg = bus.publish.call_args[0][0]
    assert stream_arg == STREAM_MOTOR_ACTION


@pytest.mark.asyncio
async def test_process_event_anomaly_rc2_routes_to_hitl():
    rl, bus = _loop()
    evt = _make_event("anomaly", risk_class=RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE.value)
    await rl.process_event(evt)
    stream_arg = bus.publish.call_args[0][0]
    assert stream_arg == STREAM_IMMUNE_HITL


@pytest.mark.asyncio
async def test_process_event_anomaly_rc3_routes_to_hitl_2_approvals():
    rl, bus = _loop()
    evt = _make_event("anomaly", risk_class=RiskClass.RC3_SUPERVISED_WRITE.value)
    await rl.process_event(evt)
    stream_arg = bus.publish.call_args[0][0]
    assert stream_arg == STREAM_IMMUNE_HITL
    published_evt = bus.publish.call_args[0][1]
    assert published_evt.payload.get("approval_required") == 2


@pytest.mark.asyncio
async def test_process_event_anomaly_rc4_routes_to_alert():
    rl, bus = _loop()
    evt = _make_event("anomaly", risk_class=RiskClass.RC4_BULK_STRUCTURAL.value)
    await rl.process_event(evt)
    stream_arg = bus.publish.call_args[0][0]
    assert stream_arg == STREAM_CONSCIOUSNESS_ALERT


@pytest.mark.asyncio
async def test_process_event_anomaly_unknown_risk_routes_to_alert():
    rl, bus = _loop()
    evt = _make_event("anomaly", risk_class="UNKNOWN-RISK")
    await rl.process_event(evt)
    stream_arg = bus.publish.call_args[0][0]
    assert stream_arg == STREAM_CONSCIOUSNESS_ALERT


@pytest.mark.asyncio
async def test_process_event_anomaly_none_risk_routes_to_alert():
    rl, bus = _loop()
    evt = _make_event("anomaly", risk_class=None)
    await rl.process_event(evt)
    stream_arg = bus.publish.call_args[0][0]
    assert stream_arg == STREAM_CONSCIOUSNESS_ALERT


@pytest.mark.asyncio
async def test_process_event_unknown_type_does_not_publish():
    rl, bus = _loop()
    evt = _make_event("unknown_type")
    await rl.process_event(evt)
    bus.publish.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_event_safely
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_event_safely_dedup_skip():
    rl, bus = _loop()
    evt = _make_event("ingest")
    evt.redis_message_id = "msg-001"
    rl._mark_processed("evt-001")
    await rl._handle_event_safely(evt)
    bus.publish.assert_not_called()
    assert rl.stats_duplicates == 1


@pytest.mark.asyncio
async def test_handle_event_safely_error_increments_counter():
    rl, bus = _loop()
    bus.publish.side_effect = RuntimeError("publish failed")
    evt = _make_event("ingest")
    await rl._handle_event_safely(evt)
    assert rl.stats_errors == 1


@pytest.mark.asyncio
async def test_handle_event_safely_success_increments_processed():
    rl, _bus = _loop()
    evt = _make_event("ingest")
    evt.redis_message_id = "msg-001"
    await rl._handle_event_safely(evt)
    assert rl.stats_processed == 1


# ---------------------------------------------------------------------------
# _resolve_risk_class
# ---------------------------------------------------------------------------


def test_resolve_risk_class_rc1():
    rl, _ = _loop()
    evt = _make_event(risk_class=RiskClass.RC1_READ_ONLY.value)
    assert rl._resolve_risk_class(evt) == RiskClass.RC1_READ_ONLY


def test_resolve_risk_class_none():
    rl, _ = _loop()
    evt = _make_event(risk_class=None)
    assert rl._resolve_risk_class(evt) is None


def test_resolve_risk_class_unknown():
    rl, _ = _loop()
    evt = _make_event(risk_class="TOTALLY_UNKNOWN")
    assert rl._resolve_risk_class(evt) is None


def test_resolve_risk_class_enum_instance():
    rl, _ = _loop()
    evt = _make_event(risk_class=RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE)
    assert rl._resolve_risk_class(evt) == RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE


# ---------------------------------------------------------------------------
# run() exits immediately on shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_exits_when_shutdown_set():
    rl, _bus = _loop()
    rl.request_shutdown()
    await asyncio.wait_for(rl.run(), timeout=2.0)
