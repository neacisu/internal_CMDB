"""Incident Correlator — group related events, deduplicate alerts, trace causal chains.

Provides event correlation within configurable time windows, alert deduplication
with cooldown periods, and causal chain tracing through correlated audit events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# fromisoformat() does not accept "Z" before Python 3.11; use explicit UTC offset.
_ISO8601_UTC_OFFSET = "+00:00"


class IncidentCorrelator:
    """Correlates, deduplicates, and traces infrastructure incidents."""

    DEFAULT_COOLDOWN_SECONDS = 300  # 5 minutes

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def correlate(self, window_minutes: int = 15) -> list[dict[str, Any]]:
        """Group related audit events within a time window into incident clusters.

        Events are grouped by entity (target_id) and then merged if they share
        a correlation_id.  The result is a list of incident groups, each containing
        the related events.
        """
        result = await self._session.execute(
            text("""
                SELECT event_id, event_type, actor, action,
                       target_entity, target_id, correlation_id,
                       risk_class, status, created_at
                FROM governance.audit_event
                WHERE created_at >= now() - make_interval(mins => :window)
                ORDER BY created_at DESC
            """),
            {"window": window_minutes},
        )
        events = [dict(r._mapping) for r in result.fetchall()]

        groups: dict[str, list[dict[str, Any]]] = {}
        correlation_map: dict[str, str] = {}

        for event in events:
            event = {
                k: (str(v) if hasattr(v, "isoformat") else v) for k, v in event.items()
            }

            corr_id = event.get("correlation_id")
            target_id = event.get("target_id")

            group_key = None
            if corr_id and str(corr_id) in correlation_map:
                group_key = correlation_map[str(corr_id)]
            elif target_id:
                group_key = str(target_id)

            if group_key is None:
                group_key = str(corr_id) if corr_id else str(event["event_id"])

            if corr_id:
                correlation_map[str(corr_id)] = group_key

            groups.setdefault(group_key, []).append(event)

        incidents: list[dict[str, Any]] = []
        for group_key, group_events in groups.items():
            incidents.append({
                "group_key": group_key,
                "event_count": len(group_events),
                "events": group_events,
                "severity": _highest_severity(group_events),
                "time_span_seconds": _time_span(group_events),
            })

        incidents.sort(key=lambda x: x["event_count"], reverse=True)
        return incidents

    def deduplicate_alerts(
        self,
        alerts: list[dict[str, Any]],
        cooldown_seconds: int | None = None,
    ) -> list[dict[str, Any]]:
        """Remove duplicate alerts: same alert_name + host within cooldown period."""
        cooldown = cooldown_seconds or self.DEFAULT_COOLDOWN_SECONDS
        seen: dict[str, str] = {}
        deduped: list[dict[str, Any]] = []

        for alert in alerts:
            alert_name = alert.get("alert_name") or ""
            host = alert.get("host") or ""

            if not alert_name and not host:
                deduped.append(alert)
                continue

            key = f"{alert_name}:{host}"
            ts = alert.get("timestamp", "")

            if key in seen:
                prev_ts = seen[key]
                if _within_cooldown(prev_ts, ts, cooldown):
                    continue

            seen[key] = ts
            deduped.append(alert)

        return deduped

    async def causal_chain(self, incident_id: str) -> dict[str, Any]:
        """Trace the causal chain backwards from an audit event using correlation_id."""
        result = await self._session.execute(
            text("""
                SELECT correlation_id FROM governance.audit_event
                WHERE event_id = :event_id
            """),
            {"event_id": incident_id},
        )
        row = result.fetchone()
        if row is None:
            return {"incident_id": incident_id, "chain": [], "error": "Event not found"}

        corr_id = row[0]
        if corr_id is None:
            return {"incident_id": incident_id, "chain": [], "note": "No correlation_id"}

        chain_result = await self._session.execute(
            text("""
                SELECT event_id, event_type, actor, action,
                       target_entity, target_id, risk_class,
                       status, created_at
                FROM governance.audit_event
                WHERE correlation_id = :corr_id
                ORDER BY created_at ASC
            """),
            {"corr_id": str(corr_id)},
        )

        chain = []
        for r in chain_result.fetchall():
            chain.append({
                k: (str(v) if hasattr(v, "isoformat") else v)
                for k, v in r._mapping.items()
            })

        return {
            "incident_id": incident_id,
            "correlation_id": str(corr_id),
            "chain_length": len(chain),
            "chain": chain,
        }


def _parse_iso_datetime(ts: str) -> datetime:
    """Parse ISO timestamps; normalize trailing Z to UTC offset for fromisoformat."""
    return datetime.fromisoformat(ts.replace("Z", _ISO8601_UTC_OFFSET))


def _highest_severity(events: list[dict[str, Any]]) -> str:
    severity_order = {"RC-4": 4, "RC-3": 3, "RC-2": 2, "RC-1": 1}
    best = "RC-1"
    best_rank = 0
    for e in events:
        rc = e.get("risk_class", "RC-1")
        rank = severity_order.get(rc, 0)
        if rank > best_rank:
            best_rank = rank
            best = rc
    return best


def _time_span(events: list[dict[str, Any]]) -> float:
    """Rough time span in seconds based on string timestamps."""
    timestamps = [e.get("created_at", "") for e in events if e.get("created_at")]
    if len(timestamps) < 2:
        return 0.0
    timestamps.sort()
    try:
        first = _parse_iso_datetime(timestamps[0])
        last = _parse_iso_datetime(timestamps[-1])
        return (last - first).total_seconds()
    except (ValueError, TypeError):
        return 0.0


def _within_cooldown(ts_a: str, ts_b: str, cooldown_seconds: int) -> bool:
    """Check if two ISO timestamps are within cooldown_seconds of each other."""
    try:
        a = _parse_iso_datetime(ts_a)
        b = _parse_iso_datetime(ts_b)
        return abs((b - a).total_seconds()) < cooldown_seconds
    except (ValueError, TypeError):
        return False
