"""F3.1 — Remediation Engine.

Classifies insights into risk classes (RC-1 … RC-4) and produces
structured remediation plans that route through the appropriate
approval workflow:

  RC-1  read-only / log-only          → auto-execute
  RC-2  single-operator approval      → HITL single
  RC-3  dual-operator approval        → HITL dual
  RC-4  blocked (manual-only)         → reject with explanation
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk-class constants
# ---------------------------------------------------------------------------

RC_1 = "RC-1"
RC_2 = "RC-2"
RC_3 = "RC-3"
RC_4 = "RC-4"

_RISK_LABELS: dict[str, str] = {
    RC_1: "read-only / log",
    RC_2: "single approval",
    RC_3: "dual approval",
    RC_4: "blocked",
}

# Action types classified by risk.  Anything not listed defaults to RC-4.
_ACTION_RISK_MAP: dict[str, str] = {
    "log_observation": RC_1,
    "emit_metric": RC_1,
    "send_notification": RC_1,
    "alert_escalate": RC_2,
    "restart_container": RC_2,
    "clear_disk_space": RC_2,
    "rotate_certificate": RC_3,
    "restart_llm_engine": RC_3,
    "rebalance_gpu_load": RC_3,
    "modify_firewall": RC_4,
    "delete_volume": RC_4,
    "destroy_cluster_node": RC_4,
}

_DESTRUCTIVE_ACTIONS: frozenset[str] = frozenset({
    "modify_firewall",
    "delete_volume",
    "destroy_cluster_node",
})

_MIN_AUTO_EXECUTE_CONFIDENCE = 0.7

_REQUIRED_INSIGHT_FIELDS: tuple[str, ...] = ("type", "target_entity")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RemediationAction:
    """Single atomic step within a remediation plan."""

    action_type: str
    target_entity: str
    params: dict[str, Any] = field(default_factory=dict)
    estimated_duration_s: int = 60


@dataclass
class RemediationPlan:
    """Full remediation proposal for an insight."""

    plan_id: str
    insight_id: str
    risk_class: str
    actions: list[RemediationAction]
    confidence: float
    explanation: str
    created_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    status: str = "proposed"
    blocked_reason: str | None = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RemediationEngine:
    """Proposes and routes remediation plans based on risk classification.

    Usage::

        engine = RemediationEngine()
        plan = await engine.propose(insight)
    """

    def __init__(self) -> None:
        self._action_risk_map: dict[str, str] = dict(_ACTION_RISK_MAP)
        self._seen_insight_hashes: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def propose(self, insight: dict[str, Any]) -> RemediationPlan:
        """Analyse *insight* and return a :class:`RemediationPlan`.

        The plan's risk class is the *highest* risk among all proposed
        actions.  Routing logic:

        * RC-1 → auto-execute (only if confidence >= threshold)
        * RC-2 / RC-3 → submit for human-in-the-loop approval
        * RC-4 → block immediately
        """
        validation_error = self._validate_insight(insight)
        if validation_error:
            return self._rejected_plan(insight, validation_error)

        dedup_hash = self._insight_hash(insight)
        if dedup_hash in self._seen_insight_hashes:
            logger.warning(
                "Duplicate insight detected (hash=%s), skipping.",
                dedup_hash,
            )
            return self._rejected_plan(insight, "Duplicate insight — already processed")

        insight_id: str = insight.get("insight_id", str(uuid.uuid4()))
        actions = self._derive_actions(insight)

        if not actions:
            return self._rejected_plan(
                insight, "No actionable remediation could be derived"
            )

        risk_class = self._classify_risk(actions)
        confidence = self._calculate_confidence(insight, actions)
        explanation = self._build_explanation(insight, actions, risk_class)

        safety_violation = self._safety_check(actions, risk_class)
        if safety_violation:
            return self._rejected_plan(insight, safety_violation)

        plan = RemediationPlan(
            plan_id=str(uuid.uuid4()),
            insight_id=insight_id,
            risk_class=risk_class,
            actions=actions,
            confidence=confidence,
            explanation=explanation,
        )

        logger.info(
            "Remediation plan %s created for insight %s — risk=%s confidence=%.2f actions=%d",
            plan.plan_id,
            plan.insight_id,
            plan.risk_class,
            plan.confidence,
            len(plan.actions),
        )

        await self._route(plan)
        self._seen_insight_hashes.add(dedup_hash)
        return plan

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_insight(insight: dict[str, Any]) -> str | None:
        """Return an error message if the insight is missing required fields."""
        missing = [f for f in _REQUIRED_INSIGHT_FIELDS if not insight.get(f)]
        if missing:
            return f"Insight missing required fields: {', '.join(missing)}"
        return None

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    @staticmethod
    def _insight_hash(insight: dict[str, Any]) -> str:
        """Deterministic hash of the core insight fields for deduplication."""
        key_fields = {
            "type": insight.get("type"),
            "target_entity": insight.get("target_entity"),
            "severity": insight.get("severity"),
        }
        raw = json.dumps(key_fields, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Safety checks
    # ------------------------------------------------------------------

    def _safety_check(
        self, actions: list[RemediationAction], risk_class: str
    ) -> str | None:
        """Block destructive actions and enforce safety invariants."""
        for action in actions:
            if action.action_type in _DESTRUCTIVE_ACTIONS:
                return (
                    f"Action '{action.action_type}' is destructive and blocked by safety guard. "
                    f"Manual intervention required."
                )

        if risk_class == RC_4:
            action_names = ", ".join(a.action_type for a in actions)
            return (
                f"RC-4 actions [{action_names}] are blocked — "
                f"manual intervention required."
            )

        return None

    # ------------------------------------------------------------------
    # Risk classification
    # ------------------------------------------------------------------

    def _classify_risk(self, actions: list[RemediationAction]) -> str:
        """Return the highest risk class across all *actions*."""
        if not actions:
            return RC_4

        risk_order = [RC_1, RC_2, RC_3, RC_4]
        max_idx = 0
        for action in actions:
            rc = self._action_risk_map.get(action.action_type, RC_4)
            idx = risk_order.index(rc)
            max_idx = max(max_idx, idx)
        return risk_order[max_idx]

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def _route(self, plan: RemediationPlan) -> None:
        """Route plan to the correct execution path based on risk class."""
        await asyncio.sleep(0)

        if plan.risk_class == RC_1:
            if plan.confidence < _MIN_AUTO_EXECUTE_CONFIDENCE:
                plan.status = "pending_approval"
                logger.info(
                    "Plan %s confidence=%.2f < threshold=%.2f — escalating RC-1 to manual review.",
                    plan.plan_id,
                    plan.confidence,
                    _MIN_AUTO_EXECUTE_CONFIDENCE,
                )
                return

            plan.status = "auto_approved"
            logger.info("Plan %s auto-approved (RC-1, confidence=%.2f).", plan.plan_id, plan.confidence)

        elif plan.risk_class in {RC_2, RC_3}:
            plan.status = "pending_approval"
            approvals_needed = 1 if plan.risk_class == RC_2 else 2
            logger.info(
                "Plan %s submitted for HITL approval (%s, %d approval(s) required).",
                plan.plan_id,
                plan.risk_class,
                approvals_needed,
            )

        else:
            plan.status = "blocked"
            plan.blocked_reason = plan.explanation
            logger.warning(
                "Plan %s blocked (RC-4) — manual intervention required. Reason: %s",
                plan.plan_id,
                plan.explanation,
            )

    # ------------------------------------------------------------------
    # Action derivation
    # ------------------------------------------------------------------

    def _derive_actions(self, insight: dict[str, Any]) -> list[RemediationAction]:
        """Derive concrete remediation actions from an insight payload.

        Supports the following insight types:

        * ``high_disk_usage``   → clear_disk_space
        * ``container_crash``   → restart_container
        * ``cert_expiry``       → rotate_certificate
        * ``gpu_imbalance``     → rebalance_gpu_load
        * ``llm_latency_spike`` → restart_llm_engine
        * ``security_alert``    → alert_escalate
        * fallback              → log_observation
        """
        insight_type: str = insight.get("type", "unknown")
        target: str = insight.get("target_entity", "unknown")
        params: dict[str, Any] = insight.get("params", {})

        mapping: dict[str, tuple[str, int]] = {
            "high_disk_usage": ("clear_disk_space", 120),
            "container_crash": ("restart_container", 30),
            "cert_expiry": ("rotate_certificate", 300),
            "gpu_imbalance": ("rebalance_gpu_load", 180),
            "llm_latency_spike": ("restart_llm_engine", 90),
            "security_alert": ("alert_escalate", 10),
        }

        if insight_type in mapping:
            action_type, duration = mapping[insight_type]
            return [
                RemediationAction(
                    action_type=action_type,
                    target_entity=target,
                    params=params,
                    estimated_duration_s=duration,
                )
            ]

        return [
            RemediationAction(
                action_type="log_observation",
                target_entity=target,
                params={"raw_insight_type": insight_type, **params},
                estimated_duration_s=5,
            )
        ]

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_confidence(
        insight: dict[str, Any],
        actions: list[RemediationAction],
    ) -> float:
        """Heuristic confidence score (0.0–1.0).

        Higher when the insight carries rich context and maps to known actions.
        """
        base = 0.5
        if insight.get("source"):
            base += 0.1
        if insight.get("evidence"):
            base += 0.15
        if insight.get("severity"):
            base += 0.1
        if all(a.action_type in _ACTION_RISK_MAP for a in actions):
            base += 0.15
        return min(base, 1.0)

    # ------------------------------------------------------------------
    # Explanation builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_explanation(
        insight: dict[str, Any],
        actions: list[RemediationAction],
        risk_class: str,
    ) -> str:
        action_names = ", ".join(a.action_type for a in actions)
        severity = insight.get("severity", "unknown")
        risk_label = _RISK_LABELS.get(risk_class, risk_class)
        return (
            f"Insight type='{insight.get('type', 'unknown')}' severity={severity} "
            f"produced action(s) [{action_names}] classified as {risk_class} ({risk_label})."
        )

    # ------------------------------------------------------------------
    # Rejected plan helper
    # ------------------------------------------------------------------

    @staticmethod
    def _rejected_plan(insight: dict[str, Any], reason: str) -> RemediationPlan:
        """Create a blocked/rejected plan with an explanation."""
        return RemediationPlan(
            plan_id=str(uuid.uuid4()),
            insight_id=insight.get("insight_id", str(uuid.uuid4())),
            risk_class=RC_4,
            actions=[],
            confidence=0.0,
            explanation=reason,
            status="blocked",
            blocked_reason=reason,
        )
