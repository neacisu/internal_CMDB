"""Teste pentru AlertFatigueManager (F15) — cooldown, flapping, deduplicare, incidente."""

from __future__ import annotations

from typing import Any

from internalcmdb.cognitive.alert_manager import (
    _FLAP_THRESHOLD,
    AlertFatigueManager,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _alert(
    entity_id: str = "host-1",
    metric: str = "cpu_usage",
    state: str = "firing",
    severity: str = "warning",
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "metric": metric,
        "state": state,
        "severity": severity,
    }


# ---------------------------------------------------------------------------
# should_alert — test normal firing
# ---------------------------------------------------------------------------


class TestShouldAlertNormal:
    def test_first_alert_always_passes(self) -> None:
        mgr = AlertFatigueManager()
        assert mgr.should_alert(_alert()) is True

    def test_second_different_metric_passes(self) -> None:
        mgr = AlertFatigueManager()
        mgr.should_alert(_alert(metric="cpu_usage"))
        assert mgr.should_alert(_alert(metric="disk_usage")) is True

    def test_second_different_entity_passes(self) -> None:
        mgr = AlertFatigueManager()
        mgr.should_alert(_alert(entity_id="host-1"))
        assert mgr.should_alert(_alert(entity_id="host-2")) is True

    def test_same_alert_suppressed_by_cooldown(self) -> None:
        mgr = AlertFatigueManager()
        mgr.should_alert(_alert())
        result = mgr.should_alert(_alert())
        assert result is False

    def test_suppressed_count_increments(self) -> None:
        mgr = AlertFatigueManager()
        mgr.should_alert(_alert())
        mgr.should_alert(_alert())
        mgr.should_alert(_alert())
        stats = mgr.get_stats()
        assert stats["suppressed_total"] >= 2

    def test_critical_alert_bypasses_cooldown(self) -> None:
        mgr = AlertFatigueManager()
        mgr.should_alert(_alert(severity="critical"))
        result = mgr.should_alert(_alert(severity="critical"))
        assert result is True

    def test_state_change_breaks_cooldown_suppression(self) -> None:
        """Cooldown suppression only applies when state is unchanged."""
        mgr = AlertFatigueManager()
        mgr.should_alert(_alert(state="firing"))
        result = mgr.should_alert(_alert(state="resolved"))
        assert result is True


# ---------------------------------------------------------------------------
# Flapping suppression
# ---------------------------------------------------------------------------


class TestFlappingSuppression:
    def _trigger_flap(self, mgr: AlertFatigueManager, n: int = 4) -> None:
        """Alternate states to cause flapping."""
        states = ["firing", "resolved"] * (n // 2 + 1)
        for i in range(n):
            mgr.should_alert(_alert(state=states[i]))

    def test_flapping_suppresses_after_threshold(self) -> None:
        mgr = AlertFatigueManager()
        self._trigger_flap(mgr, n=_FLAP_THRESHOLD + 2)
        result = mgr.should_alert(_alert(state="firing"))
        assert result is False

    def test_flapping_stats_report_flapping_entity(self) -> None:
        mgr = AlertFatigueManager()
        self._trigger_flap(mgr, n=_FLAP_THRESHOLD + 1)
        stats = mgr.get_stats()
        assert stats["flapping_entities"] >= 1

    def test_critical_alert_bypasses_flapping(self) -> None:
        mgr = AlertFatigueManager()
        self._trigger_flap(mgr, n=_FLAP_THRESHOLD + 2)
        result = mgr.should_alert(_alert(severity="critical", state="firing"))
        assert result is True


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def test_empty_list_returns_empty(self) -> None:
        mgr = AlertFatigueManager()
        assert mgr.deduplicate([]) == []

    def test_exact_duplicates_removed(self) -> None:
        mgr = AlertFatigueManager()
        alerts = [_alert(), _alert(), _alert()]
        result = mgr.deduplicate(alerts)
        assert len(result) == 1

    def test_different_entities_and_metrics_kept(self) -> None:
        mgr = AlertFatigueManager()
        alerts = [
            _alert(entity_id="h1", metric="cpu"),
            _alert(entity_id="h2", metric="disk"),
        ]
        result = mgr.deduplicate(alerts)
        assert len(result) == 2

    def test_related_alerts_grouped_into_incident(self) -> None:
        mgr = AlertFatigueManager()
        alerts = [
            _alert(entity_id="h1", metric="cpu"),
            _alert(entity_id="h1", metric="disk"),
        ]
        result = mgr.deduplicate(alerts)
        assert len(result) == 1
        assert result[0].get("type") == "incident"

    def test_incident_contains_alert_count(self) -> None:
        mgr = AlertFatigueManager()
        alerts = [
            _alert(entity_id="h1", metric="cpu"),
            _alert(entity_id="h1", metric="mem"),
        ]
        result = mgr.deduplicate(alerts)
        assert result[0]["alert_count"] == 2

    def test_max_severity_in_incident(self) -> None:
        mgr = AlertFatigueManager()
        alerts = [
            _alert(entity_id="h1", metric="cpu", severity="warning"),
            _alert(entity_id="h1", metric="mem", severity="critical"),
        ]
        result = mgr.deduplicate(alerts)
        assert result[0]["severity"] == "critical"


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_structure(self) -> None:
        mgr = AlertFatigueManager()
        stats = mgr.get_stats()
        assert "suppressed_total" in stats
        assert "active_cooldowns" in stats
        assert "flapping_entities" in stats
        assert "incident_groups" in stats

    def test_initial_suppressed_is_zero(self) -> None:
        mgr = AlertFatigueManager()
        assert mgr.get_stats()["suppressed_total"] == 0
