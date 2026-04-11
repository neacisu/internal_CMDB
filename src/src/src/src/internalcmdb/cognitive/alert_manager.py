"""Alert Fatigue Manager (Phase 15, F15).

Reduces alert noise through:
    - Flapping suppression: suppress alerts that toggle > 3 times in 15 min
    - Cooldown per entity: don't re-alert same entity for same metric within 5 min
    - Deduplication: group related alerts into incidents
    - Aggregation: bundle alerts about the same root cause

Public surface::

    from internalcmdb.cognitive.alert_manager import AlertFatigueManager

    mgr = AlertFatigueManager()
    should_fire = mgr.should_alert(alert_dict)
    deduped = mgr.deduplicate(alert_list)
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_FLAP_WINDOW_SECONDS = 900  # 15 minutes
_FLAP_THRESHOLD = 3
_COOLDOWN_SECONDS = 300  # 5 minutes
_INCIDENT_WINDOW_SECONDS = 600  # 10 minutes for grouping


# ---------------------------------------------------------------------------
# Internal tracking structures
# ---------------------------------------------------------------------------


@dataclass
class _FlappingRecord:
    """Track state transitions for a single entity+metric pair."""

    transitions: list[tuple[float, str]] = field(default_factory=list)


@dataclass
class _CooldownRecord:
    """Track last alert time for an entity+metric pair."""

    last_alerted: float = 0.0
    last_state: str = ""


@dataclass
class _IncidentGroup:
    """Group of related alerts forming an incident."""

    incident_id: str
    alerts: list[dict[str, Any]]
    created_at: float
    entity_ids: set[str] = field(default_factory=set)
    metrics: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Alert Fatigue Manager
# ---------------------------------------------------------------------------


class AlertFatigueManager:
    """Reduces alert fatigue through suppression, deduplication, and aggregation."""

    def __init__(self) -> None:
        self._flapping: dict[str, _FlappingRecord] = defaultdict(_FlappingRecord)
        self._cooldowns: dict[str, _CooldownRecord] = defaultdict(_CooldownRecord)
        self._incidents: list[_IncidentGroup] = []
        self._suppressed_count: int = 0

    # ------------------------------------------------------------------
    # Primary filter: should this alert fire?
    # ------------------------------------------------------------------

    def should_alert(self, alert: dict[str, Any]) -> bool:
        """Determine whether an alert should be surfaced to operators.

        Applies three filters in order:
          1. Flapping suppression (>3 state changes in 15 min)
          2. Cooldown per entity+metric (5 min between alerts)
          3. Severity check (critical alerts always pass)
        """
        entity_id = alert.get("entity_id", "unknown")
        metric = alert.get("metric", "unknown")
        state = alert.get("state", "firing")
        severity = alert.get("severity", "warning")
        key = f"{entity_id}:{metric}"
        now = time.monotonic()

        # Critical alerts always pass (but still update tracking)
        is_critical = severity == "critical"

        # ── Flapping check ──────────────────────────────────────────────
        flap = self._flapping[key]
        flap.transitions.append((now, state))
        flap.transitions = [
            (ts, s) for ts, s in flap.transitions if now - ts <= _FLAP_WINDOW_SECONDS
        ]

        state_changes = 0
        for i in range(1, len(flap.transitions)):
            if flap.transitions[i][1] != flap.transitions[i - 1][1]:
                state_changes += 1

        if state_changes >= _FLAP_THRESHOLD and not is_critical:
            self._suppressed_count += 1
            logger.info(
                "Alert suppressed (flapping): %s — %d state changes in window",
                key,
                state_changes,
            )
            return False

        # ── Cooldown check ──────────────────────────────────────────────
        cooldown = self._cooldowns[key]

        if (
            not is_critical
            and cooldown.last_alerted > 0
            and now - cooldown.last_alerted < _COOLDOWN_SECONDS
            and cooldown.last_state == state
        ):
            self._suppressed_count += 1
            logger.info(
                "Alert suppressed (cooldown): %s — %.0fs since last alert",
                key,
                now - cooldown.last_alerted,
            )
            return False

        cooldown.last_alerted = now
        cooldown.last_state = state
        return True

    # ------------------------------------------------------------------
    # Deduplication: remove exact duplicates and group into incidents
    # ------------------------------------------------------------------

    def deduplicate(self, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate and group related alerts into incidents.

        Returns a reduced list where related alerts are merged into
        incident records with aggregated details.
        """
        if not alerts:
            return []

        seen_hashes: set[str] = set()
        unique_alerts: list[dict[str, Any]] = []

        for alert in alerts:
            alert_hash = self._hash_alert(alert)
            if alert_hash not in seen_hashes:
                seen_hashes.add(alert_hash)
                unique_alerts.append(alert)

        incidents = self._group_into_incidents(unique_alerts)
        result: list[dict[str, Any]] = []

        for incident in incidents:
            if len(incident.alerts) == 1:
                result.append(incident.alerts[0])
            else:
                result.append(
                    {
                        "type": "incident",
                        "incident_id": incident.incident_id,
                        "alert_count": len(incident.alerts),
                        "entity_ids": list(incident.entity_ids),
                        "metrics": list(incident.metrics),
                        "severity": self._max_severity(incident.alerts),
                        "summary": (
                            f"Incident with {len(incident.alerts)} alerts across "
                            f"{len(incident.entity_ids)} entities"
                        ),
                        "first_alert": incident.alerts[0],
                        "created_at": datetime.now(tz=UTC).isoformat(),
                    }
                )

        logger.info(
            "Deduplicated %d alerts → %d unique → %d output (incidents merged)",
            len(alerts),
            len(unique_alerts),
            len(result),
        )

        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return suppression and deduplication statistics."""
        return {
            "suppressed_total": self._suppressed_count,
            "active_cooldowns": sum(
                1
                for c in self._cooldowns.values()
                if time.monotonic() - c.last_alerted < _COOLDOWN_SECONDS
            ),
            "flapping_entities": sum(
                1 for f in self._flapping.values() if len(f.transitions) >= _FLAP_THRESHOLD
            ),
            "incident_groups": len(self._incidents),
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_alert(alert: dict[str, Any]) -> str:
        """Produce a deduplication hash for an alert."""
        key_parts = [
            str(alert.get("entity_id", "")),
            str(alert.get("metric", "")),
            str(alert.get("state", "")),
            str(alert.get("severity", "")),
        ]
        return hashlib.md5("|".join(key_parts).encode(), usedforsecurity=False).hexdigest()

    def _group_into_incidents(self, alerts: list[dict[str, Any]]) -> list[_IncidentGroup]:
        """Group related alerts into incident clusters.

        Alerts are related if they share entity_id, metric, or fire
        within the incident window.
        """
        if not alerts:
            return []

        groups: list[_IncidentGroup] = []
        now = time.monotonic()

        for alert in alerts:
            entity_id = alert.get("entity_id", "unknown")
            metric = alert.get("metric", "unknown")

            matched_group: _IncidentGroup | None = None
            for group in groups:
                if entity_id in group.entity_ids or metric in group.metrics:
                    matched_group = group
                    break

            if matched_group is not None:
                matched_group.alerts.append(alert)
                matched_group.entity_ids.add(entity_id)
                matched_group.metrics.add(metric)
            else:
                incident_id = hashlib.md5(
                    f"{entity_id}:{metric}:{now}".encode(), usedforsecurity=False
                ).hexdigest()[:12]
                groups.append(
                    _IncidentGroup(
                        incident_id=f"INC-{incident_id}",
                        alerts=[alert],
                        created_at=now,
                        entity_ids={entity_id},
                        metrics={metric},
                    )
                )

        self._incidents.extend(groups)
        return groups

    @staticmethod
    def _max_severity(alerts: list[dict[str, Any]]) -> str:
        """Return the highest severity among a list of alerts."""
        priority = {"critical": 0, "warning": 1, "info": 2}
        best = "info"
        for a in alerts:
            sev = a.get("severity", "info")
            if priority.get(sev, 99) < priority.get(best, 99):
                best = sev
        return best
