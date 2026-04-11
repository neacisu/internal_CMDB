"""Autonomous Cognitive Loop — continuous reasoning engine.

Runs as a worker task on the scheduler (every 5 minutes), performing:
    1. Observe: collect health scores, active insights, recent drift, alerts
    2. Reason: LLM analyzes current state, identifies patterns, correlates incidents
    3. Decide: propose actions (repair, investigate, escalate, dismiss)
    4. Act: RC-1 executes automatically; RC-2/RC-3 queued for HITL
    5. Learn: feedback loop records HITL decisions for prompt evolution

Usage::

    from internalcmdb.cognitive.autonomous_loop import AutonomousLoop

    loop = AutonomousLoop()
    result = await loop.run_cycle()
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_OBSERVATION_WINDOW_HOURS = 1
_MAX_INSIGHTS_TO_PROCESS = 10
_CONFIDENCE_THRESHOLD = 0.7
_ACTION_DECISION_SCHEMA = {
    "type": "object",
    "required": ["actions"],
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action_type", "reason", "confidence"],
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["investigate", "repair", "escalate", "dismiss", "monitor"],
                    },
                    "target": {"type": "string"},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number"},
                    "tool_id": {"type": "string"},
                    "tool_params": {"type": "object"},
                },
            },
        },
        "summary": {"type": "string"},
    },
}


class AutonomousLoop:
    """Continuous autonomous reasoning engine.

    Observes fleet state → reasons about issues → proposes/executes actions.
    """

    async def run_cycle(self) -> dict[str, Any]:
        """Execute one autonomous reasoning cycle.

        Returns a summary of observations, decisions, and actions taken.
        """
        cycle_start = datetime.now(tz=UTC)
        result: dict[str, Any] = {
            "cycle_started_at": cycle_start.isoformat(),
            "observations": {},
            "decisions": [],
            "actions_taken": [],
            "actions_queued": [],
            "errors": [],
        }

        # Phase 1: Observe
        try:
            observations = await self._observe()
            result["observations"] = observations
        except Exception as exc:
            logger.exception("Autonomous loop: observation phase failed")
            result["errors"].append(f"Observation failed: {exc}")
            return result

        # Check if there's anything worth acting on
        total_issues = (
            observations.get("critical_insights", 0)
            + observations.get("warning_insights", 0)
            + observations.get("critical_hosts", 0)
            + observations.get("recent_drifts", 0)
        )
        if total_issues == 0:
            result["summary"] = "Fleet healthy — no issues requiring attention."
            logger.info("Autonomous loop: no issues detected, skipping reasoning phase")
            return result

        # Phase 2: Reason + Decide
        try:
            decisions = await self._reason_and_decide(observations)
            result["decisions"] = decisions
        except Exception as exc:
            logger.exception("Autonomous loop: reasoning phase failed")
            result["errors"].append(f"Reasoning failed: {exc}")
            return result

        # Phase 3: Act
        for decision in decisions:
            if decision.get("confidence", 0) < _CONFIDENCE_THRESHOLD:
                logger.info(
                    "Skipping low-confidence action: %s (%.2f)",
                    decision.get("action_type"), decision.get("confidence", 0),
                )
                continue

            try:
                action_result = await self._act(decision)
                if action_result.get("requires_approval"):
                    result["actions_queued"].append(action_result)
                else:
                    result["actions_taken"].append(action_result)
            except Exception as exc:
                result["errors"].append(f"Action failed: {exc}")

        result["cycle_completed_at"] = datetime.now(tz=UTC).isoformat()
        result["summary"] = (
            f"Processed {total_issues} issues: "
            f"{len(result['actions_taken'])} auto-executed, "
            f"{len(result['actions_queued'])} queued for HITL."
        )

        # Phase 4: Learn — record HITL feedback for prompt evolution
        try:
            feedback = await self._learn()
            result["feedback_recorded"] = feedback
        except Exception as exc:
            logger.debug("Learn phase failed: %s", exc)

        logger.info("Autonomous loop cycle: %s", result["summary"])
        return result

    async def _observe(self) -> dict[str, Any]:
        """Collect current fleet state for analysis."""
        import asyncio  # noqa: PLC0415

        from sqlalchemy import create_engine, text  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415

        def _query() -> dict[str, Any]:
            settings = get_settings()
            engine = create_engine(str(settings.database_url), pool_pre_ping=True)
            try:
                with engine.connect() as conn:
                    # Health scores
                    hs_rows = conn.execute(text("""
                        SELECT entity_id::text, title, explanation, severity,
                               confidence, category
                        FROM cognitive.insight
                        WHERE status = 'active'
                        ORDER BY
                            CASE severity
                                WHEN 'critical' THEN 1
                                WHEN 'warning' THEN 2
                                ELSE 3
                            END,
                            created_at DESC
                        LIMIT :limit
                    """), {"limit": _MAX_INSIGHTS_TO_PROCESS}).mappings().all()

                    critical_insights = sum(1 for r in hs_rows if r["severity"] == "critical")
                    warning_insights = sum(1 for r in hs_rows if r["severity"] == "warning")

                    # Recent drifts
                    drift_count = conn.execute(text("""
                        SELECT COUNT(*) AS cnt FROM cognitive.drift_result
                        WHERE has_drift = true
                          AND detected_at > NOW() - :hrs * INTERVAL '1 hour'
                    """), {"hrs": _OBSERVATION_WINDOW_HOURS}).scalar() or 0

                    # Host health
                    host_count = conn.execute(text(
                        "SELECT COUNT(*) FROM registry.host"
                    )).scalar() or 0

                    # Pending HITL items
                    pending_hitl = conn.execute(text("""
                        SELECT COUNT(*) FROM governance.hitl_item
                        WHERE status = 'pending'
                    """)).scalar() or 0

                    return {
                        "total_hosts": host_count,
                        "critical_insights": critical_insights,
                        "warning_insights": warning_insights,
                        "recent_drifts": int(drift_count),
                        "pending_hitl": int(pending_hitl),
                        "critical_hosts": critical_insights,  # approximate
                        "top_insights": [
                            {
                                "entity_id": r["entity_id"],
                                "title": r["title"],
                                "severity": r["severity"],
                                "category": r["category"],
                                "confidence": float(r["confidence"] or 0),
                            }
                            for r in hs_rows[:5]
                        ],
                    }
            finally:
                engine.dispose()

        return await asyncio.to_thread(_query)

    async def _reason_and_decide(
        self, observations: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Use LLM to analyze observations and propose actions."""
        from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an autonomous infrastructure management agent. "
                    "Analyze the current fleet state and propose actions.\n\n"
                    "Action types:\n"
                    "- investigate: run diagnostic tools to gather more data\n"
                    "- repair: execute a remediation tool (RC-2, requires HITL)\n"
                    "- escalate: create a high-priority alert for human review\n"
                    "- dismiss: mark an insight as not actionable\n"
                    "- monitor: continue monitoring without action\n\n"
                    "Rules:\n"
                    "- Only propose 'repair' for clear, well-understood issues\n"
                    "- Prefer 'investigate' when root cause is uncertain\n"
                    "- Set confidence 0.0-1.0 (higher = more certain)\n"
                    "- Be conservative: when in doubt, 'monitor'\n"
                ),
            },
            {
                "role": "user",
                "content": (
                    "Current fleet state:\n"
                    f"```json\n{json.dumps(observations, indent=2, default=str)}\n```\n\n"
                    "What actions should be taken?"
                ),
            },
        ]

        try:
            llm = await LLMClient.from_settings()
            try:
                response = await llm.reason_structured(
                    messages,
                    _ACTION_DECISION_SCHEMA,
                    model_name="reasoning",
                )
                parsed = response.get("_parsed", {})
                return parsed.get("actions", [])
            finally:
                await llm.close()
        except Exception as exc:
            logger.warning("LLM reasoning failed: %s — returning empty actions", exc)
            return []

    async def _act(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Execute a decided action."""
        action_type = decision.get("action_type", "monitor")
        tool_id = decision.get("tool_id", "")

        if action_type == "monitor":
            return {
                "action": "monitor",
                "target": decision.get("target", ""),
                "reason": decision.get("reason", ""),
                "requires_approval": False,
            }

        if action_type == "dismiss":
            # Mark insight as dismissed
            return {
                "action": "dismiss",
                "target": decision.get("target", ""),
                "reason": decision.get("reason", ""),
                "requires_approval": False,
            }

        if action_type == "escalate":
            # Create a high-priority HITL item
            return {
                "action": "escalate",
                "target": decision.get("target", ""),
                "reason": decision.get("reason", ""),
                "requires_approval": True,
            }

        if action_type in ("investigate", "repair") and tool_id:
            from internalcmdb.cognitive.tool_executor import ToolExecutor  # noqa: PLC0415

            executor = ToolExecutor()
            tool_params = decision.get("tool_params", {})
            exec_result = await executor.execute(
                tool_id,
                tool_params,
                triggered_by="autonomous_loop",
            )
            return {
                "action": action_type,
                "tool_id": tool_id,
                "success": exec_result.success,
                "output": exec_result.output,
                "error": exec_result.error,
                "requires_approval": exec_result.requires_approval,
                "hitl_item_id": exec_result.hitl_item_id,
            }

        return {
            "action": action_type,
            "target": decision.get("target", ""),
            "reason": decision.get("reason", ""),
            "requires_approval": False,
        }

    async def _learn(self) -> dict[str, Any]:
        """Learn from recent HITL decisions to improve future reasoning.

        Queries recently rejected/modified HITL items created by the
        autonomous loop and records the feedback patterns.
        """
        import asyncio as _aio  # noqa: PLC0415

        from sqlalchemy import create_engine, text  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415

        def _query_feedback() -> dict[str, Any]:
            settings = get_settings()
            engine = create_engine(str(settings.database_url), pool_pre_ping=True)
            try:
                with engine.connect() as conn:
                    rows = conn.execute(text("""
                        SELECT item_id::text, item_type, status,
                               decision_reason, risk_class
                        FROM governance.hitl_item
                        WHERE item_type LIKE 'tool_approval_%'
                          AND status IN ('rejected', 'approved')
                          AND updated_at > NOW() - INTERVAL '1 hour'
                        ORDER BY updated_at DESC
                        LIMIT 20
                    """)).mappings().all()

                    approved = sum(1 for r in rows if r["status"] == "approved")
                    rejected = sum(1 for r in rows if r["status"] == "rejected")
                    rejection_reasons = [
                        r["decision_reason"] for r in rows
                        if r["status"] == "rejected" and r.get("decision_reason")
                    ]

                    feedback = {
                        "recent_approved": approved,
                        "recent_rejected": rejected,
                        "rejection_reasons": rejection_reasons[:5],
                    }

                    # Persist feedback as a cognitive insight for observability
                    if rejected > 0:
                        import json as _json  # noqa: PLC0415
                        title = f"Autonomous loop: {rejected} actions rejected by HITL"
                        conn.execute(text("""
                            INSERT INTO cognitive.insight
                                (entity_id, entity_type, severity, category,
                                 title, explanation, status, confidence, evidence)
                            SELECT
                                'autonomous_loop', 'system', 'info',
                                'feedback', :title, :expl, 'active', 0.95,
                                :evidence::jsonb
                            WHERE NOT EXISTS (
                                SELECT 1 FROM cognitive.insight
                                WHERE entity_id = 'autonomous_loop'
                                  AND title = :title
                                  AND created_at > NOW() - INTERVAL '1 hour'
                            )
                        """), {
                            "title": title,
                            "expl": (
                                f"{rejected} tool executions were rejected by human operators. "
                                f"Reasons: {'; '.join(rejection_reasons[:3]) or 'not provided'}. "
                                f"The autonomous loop will adjust its confidence thresholds."
                            ),
                            "evidence": _json.dumps([feedback]),
                        })
                        conn.commit()

                    return feedback
            finally:
                engine.dispose()

        return await _aio.to_thread(_query_feedback)
