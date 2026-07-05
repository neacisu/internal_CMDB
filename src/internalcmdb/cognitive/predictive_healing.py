"""Predictive self-healing — anomaly detection and HITL-gated remediation (F5.6).

Analyses fleet vitals for statistical anomalies and proposes remediations
through :class:`~internalcmdb.governance.policy_enforcer.PolicyEnforcer`
with human-in-the-loop approval for high-risk actions.
"""

from __future__ import annotations

import logging
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLDS: dict[str, float] = {
    "cpu_pct": 90.0,
    "memory_pct": 85.0,
    "disk_root_pct": 90.0,
    "gpu_pct": 95.0,
}
_ZSCORE_THRESHOLD = 2.5


@dataclass
class VitalsAnomaly:
    """Detected anomaly in fleet vitals."""

    agent_id: str
    host_code: str
    metric: str
    value: float
    threshold: float
    severity: str  # warning | critical
    reason: str


@dataclass
class RemediationProposal:
    """Proposed remediation routed through governance."""

    proposal_id: str
    anomaly: VitalsAnomaly
    action: dict[str, Any]
    policy_compliant: bool
    hitl_required: bool
    hitl_item_id: str | None = None
    violations: list[str] = field(default_factory=list)


class PredictiveHealingEngine:
    """Detect vitals anomalies and propose policy-gated remediations."""

    def __init__(
        self,
        session: Session,
        *,
        thresholds: dict[str, float] | None = None,
    ) -> None:
        self._session = session
        self._thresholds = thresholds or _DEFAULT_THRESHOLDS

    def detect_anomalies(self, vitals: list[dict[str, Any]]) -> list[VitalsAnomaly]:
        """Detect threshold and z-score anomalies across fleet vitals."""
        anomalies: list[VitalsAnomaly] = []
        for metric, threshold in self._thresholds.items():
            values = [
                (v, float(v[metric]))
                for v in vitals
                if v.get(metric) is not None and v.get("agent_id")
            ]
            if len(values) < 2:
                self._check_absolute_thresholds(values, metric, threshold, anomalies)
                continue

            nums = [val for _, val in values]
            try:
                mean = statistics.mean(nums)
                stdev = statistics.stdev(nums)
            except statistics.StatisticsError:
                mean, stdev = 0.0, 0.0

            for vital, val in values:
                self._evaluate_vital(vital, metric, val, threshold, mean, stdev, anomalies)

        return anomalies

    def _check_absolute_thresholds(
        self,
        values: list[tuple[dict[str, Any], float]],
        metric: str,
        threshold: float,
        anomalies: list[VitalsAnomaly],
    ) -> None:
        for vital, val in values:
            if val >= threshold:
                anomalies.append(self._make_anomaly(vital, metric, val, threshold, "absolute"))

    def _evaluate_vital(
        self,
        vital: dict[str, Any],
        metric: str,
        val: float,
        threshold: float,
        mean: float,
        stdev: float,
        anomalies: list[VitalsAnomaly],
    ) -> None:
        if val >= threshold:
            anomalies.append(self._make_anomaly(vital, metric, val, threshold, "absolute"))
            return
        if stdev > 0:
            zscore = (val - mean) / stdev
            if zscore >= _ZSCORE_THRESHOLD:
                anomalies.append(
                    self._make_anomaly(
                        vital,
                        metric,
                        val,
                        mean + _ZSCORE_THRESHOLD * stdev,
                        "zscore",
                    )
                )

    def _make_anomaly(
        self,
        vital: dict[str, Any],
        metric: str,
        val: float,
        threshold: float,
        reason: str,
    ) -> VitalsAnomaly:
        severity = "critical" if val >= threshold * 1.05 else "warning"
        return VitalsAnomaly(
            agent_id=str(vital.get("agent_id", "")),
            host_code=str(vital.get("host_code", "")),
            metric=metric,
            value=val,
            threshold=threshold,
            severity=severity,
            reason=reason,
        )

    def propose_remediation(self, anomaly: VitalsAnomaly) -> RemediationProposal:
        """Build a remediation action and evaluate via PolicyEnforcer."""
        from internalcmdb.governance.policy_enforcer import PolicyEnforcer  # noqa: PLC0415

        action = self._build_action(anomaly)
        result = PolicyEnforcer(self._session).check(action, context={"environment": "production"})
        violations = [v.reason for v in result.violations]
        hitl_required = not result.compliant or action.get("requires_hitl", False)

        proposal = RemediationProposal(
            proposal_id=str(uuid.uuid4()),
            anomaly=anomaly,
            action=action,
            policy_compliant=result.compliant,
            hitl_required=hitl_required,
            violations=violations,
        )

        if hitl_required:
            proposal.hitl_item_id = self._submit_hitl(proposal)

        return proposal

    @staticmethod
    def _build_action(anomaly: VitalsAnomaly) -> dict[str, Any]:
        action_type = (
            "restart_service" if anomaly.metric == "containers_unhealthy" else "investigate"
        )
        if anomaly.severity == "critical" and anomaly.metric in ("cpu_pct", "memory_pct"):
            action_type = "scale_or_restart"
        return {
            "type": action_type,
            "target": anomaly.host_code,
            "entity_id": anomaly.agent_id,
            "metric": anomaly.metric,
            "value": anomaly.value,
            "requires_hitl": anomaly.severity == "critical",
            "has_approval": False,
        }

    def _submit_hitl(self, proposal: RemediationProposal) -> str | None:
        """Insert a HITL item for human approval of the proposed remediation."""
        try:
            from sqlalchemy import text  # noqa: PLC0415

            item_id = str(uuid.uuid4())
            title = (
                f"Predictive healing: {proposal.anomaly.metric} anomaly on "
                f"{proposal.anomaly.host_code}"
            )
            self._session.execute(
                text("""
                    INSERT INTO governance.hitl_item
                        (item_id, title, description, action_class, priority,
                         status, payload_jsonb, created_at)
                    VALUES
                        (:item_id, :title, :description, :action_class, :priority,
                         'pending', CAST(:payload AS jsonb), :created_at)
                """),
                {
                    "item_id": item_id,
                    "title": title,
                    "description": (
                        f"Auto-detected {proposal.anomaly.reason} anomaly: "
                        f"{proposal.anomaly.metric}={proposal.anomaly.value:.1f}"
                    ),
                    "action_class": "RC-3",
                    "priority": "high" if proposal.anomaly.severity == "critical" else "medium",
                    "payload": __import__("json").dumps(
                        {
                            "proposal_id": proposal.proposal_id,
                            "action": proposal.action,
                            "violations": proposal.violations,
                            "source": "predictive_healing",
                        }
                    ),
                    "created_at": datetime.now(tz=UTC),
                },
            )
            self._session.flush()
            return item_id
        except Exception:
            logger.warning("HITL submission for predictive healing failed", exc_info=True)
            return None
