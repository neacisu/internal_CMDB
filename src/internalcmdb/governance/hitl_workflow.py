"""internalCMDB — Human-In-The-Loop Workflow Engine (Phase 4, F4.3 + F4.4).

Manages the lifecycle of HITL review items stored in ``governance.hitl_item``:
submit → (pending) → approve / reject → (decided) with automatic time-based
escalation for items that exceed their SLA.

Escalation thresholds (wall-clock from ``created_at``):

    RC-4  critical  → 15 min
    RC-3  high      → 1 h
    RC-2  medium    → 4 h

After **3 escalations** an item is auto-blocked and marked ``blocked``.

Public surface::

    from internalcmdb.governance.hitl_workflow import HITLWorkflow

    wf = HITLWorkflow(async_session)
    item_id = await wf.submit({...})
    ok = await wf.approve(item_id, decided_by="alice", reason="looks good")
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging security helpers
# ---------------------------------------------------------------------------

_LOG_CTL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_log(value: object, max_len: int = 200) -> str:
    """Sanitize user-controlled values before logging to prevent log injection (S5145).

    Replaces ASCII control characters (including newlines and carriage returns) with '?'
    and truncates to ``max_len`` characters to prevent log flooding.
    """
    sanitized = _LOG_CTL_RE.sub("?", str(value))
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len] + "...[truncated]"
    return sanitized

# ---------------------------------------------------------------------------
# Escalation configuration
# ---------------------------------------------------------------------------

_ESCALATION_THRESHOLDS: dict[str, timedelta] = {
    "RC-4": timedelta(minutes=15),
    "RC-3": timedelta(hours=1),
    "RC-2": timedelta(hours=4),
}

_MAX_ESCALATIONS = 3

_PRIORITY_MAP: dict[str, str] = {
    "RC-4": "critical",
    "RC-3": "high",
    "RC-2": "medium",
    "RC-1": "low",
}


async def _get_escalation_config() -> tuple[dict[str, timedelta], int]:
    """Load escalation thresholds and max escalations from SettingsStore at runtime.

    Falls back to module-level defaults if the store is unavailable.
    Allows operators to tune HITL SLAs via /api/v1/settings/hitl.
    """
    try:
        from internalcmdb.config.settings_store import get_settings_store  # noqa: PLC0415
        store = get_settings_store()
        rc4_m = await store.get("hitl.rc4.escalation_minutes") or 15
        rc3_m = await store.get("hitl.rc3.escalation_minutes") or 60
        rc2_h = await store.get("hitl.rc2.escalation_hours") or 4
        max_esc = await store.get("hitl.max_escalations") or 3
        thresholds = {
            "RC-4": timedelta(minutes=int(rc4_m)),
            "RC-3": timedelta(minutes=int(rc3_m)),
            "RC-2": timedelta(hours=int(rc2_h)),
        }
        return thresholds, int(max_esc)
    except Exception:  # noqa: BLE001
        return _ESCALATION_THRESHOLDS, _MAX_ESCALATIONS


# ---------------------------------------------------------------------------
# Workflow engine
# ---------------------------------------------------------------------------


class HITLWorkflow:
    """Manages the governance.hitl_item lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── submit ──────────────────────────────────────────────────────────

    async def submit(self, item_data: dict[str, Any]) -> str:
        """Insert a new HITL item and return its ``item_id``."""
        item_id = str(uuid.uuid4())
        risk_class = item_data.get("risk_class", "RC-2")
        priority = _PRIORITY_MAP.get(risk_class, "medium")

        threshold = _ESCALATION_THRESHOLDS.get(risk_class)
        expires_at_expr = (
            f"now() + interval '{int(threshold.total_seconds())} seconds'"
            if threshold
            else "NULL"
        )

        await self._session.execute(
            text(f"""
                INSERT INTO governance.hitl_item
                    (item_id, item_type, risk_class, priority, status,
                     source_event_id, correlation_id, context_jsonb,
                     llm_suggestion, llm_confidence, llm_model_used,
                     expires_at)
                VALUES
                    (:item_id, :item_type, :risk_class, :priority, 'pending',
                     :source_event_id, :correlation_id, :context_jsonb::jsonb,
                     :llm_suggestion::jsonb, :llm_confidence, :llm_model_used,
                     {expires_at_expr})
            """),
            {
                "item_id": item_id,
                "item_type": item_data.get("item_type", "action_review"),
                "risk_class": risk_class,
                "priority": priority,
                "source_event_id": item_data.get("source_event_id"),
                "correlation_id": item_data.get("correlation_id"),
                "context_jsonb": _json_or_none(item_data.get("context")),
                "llm_suggestion": _json_or_none(item_data.get("llm_suggestion")),
                "llm_confidence": item_data.get("llm_confidence"),
                "llm_model_used": item_data.get("llm_model_used"),
            },
        )
        await self._session.commit()
        logger.info("HITL item submitted: %s (%s / %s)", item_id, _sanitize_log(risk_class), priority)

        await _notify("submitted", {
            "item_id": item_id,
            "risk_class": risk_class,
            "priority": priority,
            "item_type": item_data.get("item_type", "action_review"),
        })

        return item_id

    # ── approve ─────────────────────────────────────────────────────────

    async def approve(self, item_id: str, decided_by: str, reason: str) -> bool:
        """Approve a pending HITL item."""
        return await self._decide(item_id, "approved", decided_by, reason)

    # ── reject ──────────────────────────────────────────────────────────

    async def reject(self, item_id: str, decided_by: str, reason: str) -> bool:
        """Reject a pending HITL item."""
        return await self._decide(item_id, "rejected", decided_by, reason)

    # ── modify (approve with changes) ──────────────────────────────────

    async def modify(
        self,
        item_id: str,
        decided_by: str,
        reason: str,
        modifications: dict[str, Any] | None = None,
    ) -> bool:
        """Approve with modifications."""
        return await self._decide(
            item_id, "approved_with_modifications", decided_by, reason, modifications
        )

    # ── escalate ────────────────────────────────────────────────────────

    async def escalate(self, item_id: str) -> bool:
        """Manually escalate a pending HITL item."""
        result = await self._session.execute(
            text("""
                UPDATE governance.hitl_item
                   SET escalation_count = escalation_count + 1,
                       status = CASE
                           WHEN escalation_count + 1 >= :max_esc THEN 'blocked'
                           ELSE 'escalated'
                       END
                 WHERE item_id = :item_id
                   AND status IN ('pending', 'escalated')
                RETURNING escalation_count, status, risk_class
            """),
            {"item_id": item_id, "max_esc": _MAX_ESCALATIONS},
        )
        row = result.fetchone()
        if row is None:
            return False
        await self._session.commit()
        esc_count, new_status, risk_class = row
        logger.info(
            "HITL item escalated: %s (count=%d, status=%s, risk=%s)",
            _sanitize_log(item_id), esc_count, _sanitize_log(new_status), _sanitize_log(risk_class),
        )

        await _notify(new_status, {
            "item_id": item_id,
            "risk_class": risk_class,
            "status": new_status,
            "escalation_count": esc_count,
        })

        return True

    # ── check_escalations (background) ─────────────────────────────────

    async def check_escalations(self) -> int:
        """Auto-escalate items that have exceeded their timeout.

        Returns the number of items escalated.
        """
        total_escalated = 0

        escalation_thresholds, max_escalations = await _get_escalation_config()
        for risk_class, threshold in escalation_thresholds.items():
            cutoff = datetime.now(tz=UTC) - threshold
            result = await self._session.execute(
                text("""
                    UPDATE governance.hitl_item
                       SET escalation_count = escalation_count + 1,
                           status = CASE
                               WHEN escalation_count + 1 >= :max_esc THEN 'blocked'
                               ELSE 'escalated'
                           END
                     WHERE risk_class = :rc
                       AND status IN ('pending', 'escalated')
                       AND created_at <= :cutoff
                       AND escalation_count < :max_esc
                """),
                {"rc": risk_class, "cutoff": cutoff, "max_esc": max_escalations},
            )
            total_escalated += result.rowcount  # type: ignore[operator]

        if total_escalated:
            await self._session.commit()
            logger.info("Auto-escalated %d HITL items", total_escalated)
            await _notify("escalated", {
                "item_id": "batch",
                "risk_class": "mixed",
                "status": "escalated",
                "auto_escalated_count": total_escalated,
            })

        return total_escalated

    # ── internal helpers ────────────────────────────────────────────────

    _VALID_DECISIONS = frozenset({
        "approved", "rejected", "approved_with_modifications",
    })

    async def _decide(
        self,
        item_id: str,
        decision: str,
        decided_by: str,
        reason: str,
        decision_jsonb: dict[str, Any] | None = None,
    ) -> bool:
        if decision not in self._VALID_DECISIONS:
            logger.warning("Invalid decision value: %s", _sanitize_log(decision))
            return False

        result = await self._session.execute(
            text("""
                UPDATE governance.hitl_item
                   SET decision      = :decision,
                       decided_by    = :decided_by,
                       decision_reason = :reason,
                       decision_jsonb = :decision_jsonb::jsonb,
                       decided_at    = now(),
                       status        = :decision
                 WHERE item_id = :item_id
                   AND status IN ('pending', 'escalated')
                RETURNING item_id
            """),
            {
                "item_id": item_id,
                "decision": decision,
                "decided_by": decided_by,
                "reason": reason,
                "decision_jsonb": _json_or_none(decision_jsonb),
            },
        )
        row = result.fetchone()
        if row is None:
            return False

        try:
            await self._record_feedback(item_id, decided_by, decision)
        except Exception:
            logger.error("Failed to record feedback for %s — decision still saved", _sanitize_log(item_id), exc_info=True)
        await self._session.commit()
        logger.info("HITL item %s: %s by %s", _sanitize_log(decision), _sanitize_log(item_id), _sanitize_log(decided_by))
        return True

    async def _record_feedback(
        self, item_id: str, decided_by: str, decision: str
    ) -> None:
        """Record an LLM-vs-human feedback row for accuracy tracking."""
        row = await self._session.execute(
            text("""
                SELECT llm_suggestion FROM governance.hitl_item
                 WHERE item_id = :item_id
            """),
            {"item_id": item_id},
        )
        item_row = row.fetchone()
        if item_row is None:
            return

        llm_suggestion = item_row[0]
        llm_decision_val = None
        if isinstance(llm_suggestion, dict):
            llm_decision_val = llm_suggestion.get("decision")

        agreement = llm_decision_val == decision if llm_decision_val else None

        import json as _json  # noqa: PLC0415

        human_decision_safe = _json.dumps(
            {"decision": decision, "decided_by": decided_by},
            default=str,
        )

        await self._session.execute(
            text("""
                INSERT INTO governance.hitl_feedback
                    (hitl_item_id, llm_suggestion, human_decision, agreement)
                VALUES
                    (:item_id, :llm_suggestion::jsonb, :human_decision::jsonb, :agreement)
            """),
            {
                "item_id": item_id,
                "llm_suggestion": _json_or_none(llm_suggestion),
                "human_decision": human_decision_safe,
                "agreement": agreement,
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_or_none(val: Any) -> str | None:
    """Serialise a value to a JSON string or return None."""
    if val is None:
        return None
    if isinstance(val, str):
        return val
    import json  # noqa: PLC0415

    return json.dumps(val, default=str)


async def _notify(event_type: str, payload: dict[str, Any]) -> None:
    """Best-effort notification dispatch — never raises."""
    try:
        from internalcmdb.governance.notifications import notify_hitl_event  # noqa: PLC0415

        await notify_hitl_event(event_type, payload)
    except Exception:
        logger.debug("Notification dispatch failed for %s", event_type, exc_info=True)
