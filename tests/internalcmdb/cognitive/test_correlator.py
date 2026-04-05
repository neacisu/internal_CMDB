"""Teste pentru IncidentCorrelator — corelare, deduplicare alerte, lanț cauzal."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from internalcmdb.cognitive.correlator import (
    IncidentCorrelator,
    _highest_severity,
    _time_span,
    _within_cooldown,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(rows: list[Any] | None = None) -> MagicMock:
    """Construiește un session mock care returnează *rows* la fetchall."""
    session = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = rows or []
    result.fetchone.return_value = rows[0] if rows else None
    session.execute = AsyncMock(return_value=result)
    return session


def _event_row(
    event_id: str = "evt-1",
    target_id: str = "host-1",
    correlation_id: str | None = None,
    risk_class: str = "RC-2",
    created_at: str = "2024-06-01T10:00:00+00:00",
) -> MagicMock:
    row = MagicMock()
    row._mapping = {
        "event_id": event_id,
        "event_type": "anomaly",
        "actor": "system",
        "action": "detect",
        "target_entity": "Host",
        "target_id": target_id,
        "correlation_id": correlation_id,
        "risk_class": risk_class,
        "status": "open",
        "created_at": created_at,
    }
    return row


# ---------------------------------------------------------------------------
# IncidentCorrelator.correlate
# ---------------------------------------------------------------------------


class TestCorrelate:
    @pytest.mark.asyncio
    async def test_empty_events_returns_empty(self) -> None:
        session = _make_session(rows=[])
        correlator = IncidentCorrelator(session)
        result = await correlator.correlate()
        assert result == []

    @pytest.mark.asyncio
    async def test_single_event_creates_one_group(self) -> None:
        session = _make_session(rows=[_event_row()])
        correlator = IncidentCorrelator(session)
        result = await correlator.correlate()
        assert len(result) == 1
        assert result[0]["event_count"] == 1

    @pytest.mark.asyncio
    async def test_two_events_same_target_grouped(self) -> None:
        rows = [
            _event_row(event_id="e1", target_id="host-1"),
            _event_row(event_id="e2", target_id="host-1"),
        ]
        session = _make_session(rows=rows)
        correlator = IncidentCorrelator(session)
        result = await correlator.correlate()
        assert len(result) == 1
        assert result[0]["event_count"] == 2

    @pytest.mark.asyncio
    async def test_two_events_different_target_separate_groups(self) -> None:
        rows = [
            _event_row(event_id="e1", target_id="host-1"),
            _event_row(event_id="e2", target_id="host-2"),
        ]
        session = _make_session(rows=rows)
        correlator = IncidentCorrelator(session)
        result = await correlator.correlate()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_severity_set_correctly(self) -> None:
        rows = [_event_row(risk_class="RC-4")]
        session = _make_session(rows=rows)
        correlator = IncidentCorrelator(session)
        result = await correlator.correlate()
        assert result[0]["severity"] == "RC-4"

    @pytest.mark.asyncio
    async def test_incidents_sorted_by_event_count_desc(self) -> None:
        rows = [
            _event_row(event_id="e1", target_id="host-1"),
            _event_row(event_id="e2", target_id="host-1"),
            _event_row(event_id="e3", target_id="host-2"),
        ]
        session = _make_session(rows=rows)
        correlator = IncidentCorrelator(session)
        result = await correlator.correlate()
        assert result[0]["event_count"] >= result[-1]["event_count"]


# ---------------------------------------------------------------------------
# IncidentCorrelator.deduplicate_alerts
# ---------------------------------------------------------------------------


class TestDeduplicateAlerts:
    def _correlator(self) -> IncidentCorrelator:
        return IncidentCorrelator(MagicMock())

    def test_empty_list_returns_empty(self) -> None:
        c = self._correlator()
        assert c.deduplicate_alerts([]) == []

    def test_duplicate_within_cooldown_removed(self) -> None:
        c = self._correlator()
        alerts = [
            {"alert_name": "HighCPU", "host": "host-1", "timestamp": "2024-06-01T10:00:00+00:00"},
            {"alert_name": "HighCPU", "host": "host-1", "timestamp": "2024-06-01T10:01:00+00:00"},
        ]
        result = c.deduplicate_alerts(alerts, cooldown_seconds=600)
        assert len(result) == 1

    def test_duplicate_outside_cooldown_kept(self) -> None:
        c = self._correlator()
        alerts = [
            {"alert_name": "HighCPU", "host": "host-1", "timestamp": "2024-06-01T10:00:00+00:00"},
            {"alert_name": "HighCPU", "host": "host-1", "timestamp": "2024-06-01T11:00:00+00:00"},
        ]
        result = c.deduplicate_alerts(alerts, cooldown_seconds=60)
        assert len(result) == 2

    def test_different_hosts_both_kept(self) -> None:
        c = self._correlator()
        alerts = [
            {"alert_name": "HighCPU", "host": "host-1", "timestamp": "2024-06-01T10:00:00+00:00"},
            {"alert_name": "HighCPU", "host": "host-2", "timestamp": "2024-06-01T10:00:00+00:00"},
        ]
        result = c.deduplicate_alerts(alerts)
        assert len(result) == 2

    def test_alert_without_name_or_host_always_kept(self) -> None:
        c = self._correlator()
        alerts = [{}, {}]
        result = c.deduplicate_alerts(alerts)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# IncidentCorrelator.causal_chain
# ---------------------------------------------------------------------------


class TestCausalChain:
    @pytest.mark.asyncio
    async def test_event_not_found_returns_error(self) -> None:
        session = MagicMock()
        result = MagicMock()
        result.fetchone.return_value = None
        session.execute = AsyncMock(return_value=result)
        c = IncidentCorrelator(session)
        out = await c.causal_chain("non-existent")
        assert out["error"] == "Event not found"

    @pytest.mark.asyncio
    async def test_no_correlation_id_returns_note(self) -> None:
        session = MagicMock()
        result_1 = MagicMock()
        result_1.fetchone.return_value = (None,)
        session.execute = AsyncMock(return_value=result_1)
        c = IncidentCorrelator(session)
        out = await c.causal_chain("evt-1")
        assert "note" in out


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_highest_severity_empty(self) -> None:
        assert _highest_severity([]) == "RC-1"

    def test_highest_severity_picks_rc4(self) -> None:
        events = [{"risk_class": "RC-2"}, {"risk_class": "RC-4"}]
        assert _highest_severity(events) == "RC-4"

    def test_time_span_single_event_zero(self) -> None:
        events = [{"created_at": "2024-06-01T10:00:00+00:00"}]
        assert _time_span(events) == 0.0

    def test_time_span_two_events(self) -> None:
        events = [
            {"created_at": "2024-06-01T10:00:00+00:00"},
            {"created_at": "2024-06-01T10:05:00+00:00"},
        ]
        assert _time_span(events) == pytest.approx(300.0)

    def test_within_cooldown_true(self) -> None:
        assert _within_cooldown(
            "2024-06-01T10:00:00+00:00",
            "2024-06-01T10:01:00+00:00",
            cooldown_seconds=300,
        ) is True

    def test_within_cooldown_false(self) -> None:
        assert _within_cooldown(
            "2024-06-01T10:00:00+00:00",
            "2024-06-01T11:00:00+00:00",
            cooldown_seconds=60,
        ) is False
