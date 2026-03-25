"""internalCMDB — Guard Gate: 5-Level Action Evaluation Pipeline (Phase 4).

Chains five defence-in-depth levels before any action is permitted to execute:

    L1  Input Sanitisation — RedactionScanner rejects PII / credential leaks.
    L2  LLM Guard Scan    — external LLM-Guard API pre-scan (prompt injection,
                             jailbreak, toxic content).
    L3  Policy Enforcer    — PolicyEnforcer.check() verifies governance policy
                             compliance.
    L4  Risk Classification — classifies the action as RC-1 … RC-4.
    L5  HITL Gate          — routes RC-3/RC-4 actions to Human-In-The-Loop
                             review queue; RC-1/RC-2 pass automatically.

Public surface::

    from internalcmdb.governance.guard_gate import GuardGate, GateDecision

    gate = GuardGate(session)
    decision = await gate.evaluate(action, context)
    if not decision.allowed:
        ...
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from internalcmdb.governance.policy_enforcer import PolicyEnforcer
from internalcmdb.governance.redaction_scanner import RedactionScanner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk classification constants
# ---------------------------------------------------------------------------

RC_1 = "RC-1"  # informational / read-only — auto-approve
RC_2 = "RC-2"  # low-risk mutation — auto-approve with logging
RC_3 = "RC-3"  # high-risk mutation — requires HITL approval
RC_4 = "RC-4"  # critical / destructive — requires HITL + escalation

_READ_ACTIONS = frozenset({"read", "query", "list", "get", "search", "retrieve", "inspect"})
_LOW_RISK_MUTATIONS = frozenset({"create", "add", "tag", "annotate", "update_metadata"})
_HIGH_RISK_MUTATIONS = frozenset({"update", "patch", "modify", "restart", "scale"})
_CRITICAL_ACTIONS = frozenset(
    {"delete", "destroy", "purge", "drop", "terminate", "decommission", "wipe", "revoke"}
)

_CRITICAL_TARGETS = frozenset({"production", "prod", "database", "cluster", "secrets"})

_LLM_GUARD_FAIL_CLOSED = os.getenv("LLM_GUARD_FAIL_CLOSED", "true").lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Gate decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LevelTrace:
    """Outcome of a single guard level evaluation."""

    level: int
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class GateDecision:
    """Outcome produced by :meth:`GuardGate.evaluate`."""

    allowed: bool
    risk_class: str
    blocked_at_level: int | None
    reason: str
    requires_hitl: bool
    gate_trace: tuple[LevelTrace, ...] = ()


# ---------------------------------------------------------------------------
# LLM Guard scanner (L2)
# ---------------------------------------------------------------------------

_LLM_GUARD_URL = os.getenv("LLM_GUARD_URL", "http://10.0.1.115:8000")
_LLM_GUARD_TIMEOUT = float(os.getenv("LLM_GUARD_TIMEOUT", "5"))


async def _llm_guard_scan(payload: dict[str, Any]) -> tuple[bool, str]:
    """Call the external LLM Guard API for prompt-injection / toxicity scan.

    Behaviour on failure is controlled by ``LLM_GUARD_FAIL_CLOSED`` (default
    ``true``).  When fail-closed, an unreachable guard blocks the action.
    """
    if not _LLM_GUARD_URL:
        if _LLM_GUARD_FAIL_CLOSED:
            logger.warning("LLM Guard URL not configured — FAIL-CLOSED: blocking action")
            return False, "llm-guard-not-configured-fail-closed"
        logger.warning("LLM Guard URL not configured — fail-open (set LLM_GUARD_FAIL_CLOSED=true)")
        return True, "llm-guard-not-configured"

    try:
        async with httpx.AsyncClient(timeout=_LLM_GUARD_TIMEOUT) as client:
            resp = await client.post(
                f"{_LLM_GUARD_URL}/scan",
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            safe: bool = body.get("safe", True)
            detail: str = body.get("detail", "")
            return safe, detail
    except Exception:
        if _LLM_GUARD_FAIL_CLOSED:
            logger.error("LLM Guard scan failed — FAIL-CLOSED: blocking action", exc_info=True)
            return False, "llm-guard-unavailable-fail-closed"
        logger.warning("LLM Guard scan failed — fail-open", exc_info=True)
        return True, "llm-guard-unavailable"


# ---------------------------------------------------------------------------
# Risk classifier (L4)
# ---------------------------------------------------------------------------


def classify_risk(action: dict[str, Any], context: dict[str, Any]) -> str:
    """Classify an action into one of four risk classes (RC-1 … RC-4).

    Read-only actions on critical targets are escalated to RC-2 (logged),
    not RC-4.  Only destructive/mutation actions on critical targets are RC-4.
    """
    action_type = (action.get("type") or "").lower()
    target = (action.get("target") or "").lower()
    is_critical_target = target in _CRITICAL_TARGETS

    if action_type in _CRITICAL_ACTIONS:
        return RC_4

    if action_type in _HIGH_RISK_MUTATIONS:
        return RC_4 if is_critical_target else RC_3

    if action_type in _LOW_RISK_MUTATIONS:
        return RC_3 if is_critical_target else RC_2

    if action_type in _READ_ACTIONS:
        return RC_2 if is_critical_target else RC_1

    env = (context.get("environment") or "").lower()
    if env in ("production", "prod"):
        return RC_3

    return RC_2


# ---------------------------------------------------------------------------
# Guard Gate
# ---------------------------------------------------------------------------


def _record_guard_metric(level: str, result: str) -> None:
    """Increment the Prometheus guard_decisions counter."""
    try:
        from internalcmdb.observability.metrics import GUARD_DECISIONS_TOTAL

        GUARD_DECISIONS_TOTAL.labels(level=level, result=result).inc()
    except Exception:
        pass


class GuardGate:
    """Five-level guardrail gate for action evaluation."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._scanner = RedactionScanner()
        self._enforcer = PolicyEnforcer(session)

    async def evaluate(self, action: dict[str, Any], context: dict[str, Any]) -> GateDecision:
        """Run *action* through all five guard levels and return a decision.

        Each level's outcome is captured in ``gate_trace`` for audit purposes.
        """
        trace: list[LevelTrace] = []

        # ── L1: Input Sanitisation ──────────────────────────────────────
        payload = {"action": action, "context": context}
        scan = self._scanner.scan_fact_payload(payload)
        l1_passed = scan.safe
        trace.append(LevelTrace(
            level=1, name="input_sanitisation", passed=l1_passed,
            detail=f"matched={scan.matched_patterns}" if not l1_passed else "clean",
        ))
        if not l1_passed:
            _record_guard_metric("L1", "blocked")
            return GateDecision(
                allowed=False,
                risk_class=RC_4,
                blocked_at_level=1,
                reason=f"L1 redaction: PII/credentials detected — {scan.matched_patterns}",
                requires_hitl=False,
                gate_trace=tuple(trace),
            )

        # ── L2: LLM Guard Scan ─────────────────────────────────────────
        llm_safe, llm_detail = await _llm_guard_scan(payload)
        trace.append(LevelTrace(
            level=2, name="llm_guard_scan", passed=llm_safe,
            detail=llm_detail,
        ))
        if not llm_safe:
            _record_guard_metric("L2", "blocked")
            return GateDecision(
                allowed=False,
                risk_class=RC_4,
                blocked_at_level=2,
                reason=f"L2 llm-guard: content flagged — {llm_detail}",
                requires_hitl=False,
                gate_trace=tuple(trace),
            )

        # ── L3: Policy Enforcer ─────────────────────────────────────────
        policy_result = self._enforcer.check(action, context)
        l3_passed = policy_result.compliant
        trace.append(LevelTrace(
            level=3, name="policy_enforcer", passed=l3_passed,
            detail="; ".join(v.reason for v in policy_result.violations) if not l3_passed else "compliant",
        ))
        if not l3_passed:
            _record_guard_metric("L3", "blocked")
            reasons = "; ".join(v.reason for v in policy_result.violations)
            return GateDecision(
                allowed=False,
                risk_class=RC_3,
                blocked_at_level=3,
                reason=f"L3 policy: {reasons}",
                requires_hitl=False,
                gate_trace=tuple(trace),
            )

        # ── L4: Risk Classification ────────────────────────────────────
        risk_class = classify_risk(action, context)
        trace.append(LevelTrace(
            level=4, name="risk_classification", passed=True,
            detail=f"classified={risk_class}",
        ))

        # ── L5: HITL Gate ───────────────────────────────────────────────
        if risk_class in (RC_3, RC_4):
            trace.append(LevelTrace(
                level=5, name="hitl_gate", passed=False,
                detail=f"{risk_class} requires human approval",
            ))
            _record_guard_metric("L5", "hitl_required")
            logger.info(
                "Guard Gate BLOCKED: action=%s target=%s risk=%s (HITL required)",
                action.get("type"), action.get("target"), risk_class,
            )
            return GateDecision(
                allowed=False,
                risk_class=risk_class,
                blocked_at_level=5,
                reason=f"L5 hitl-gate: {risk_class} action requires human approval",
                requires_hitl=True,
                gate_trace=tuple(trace),
            )

        trace.append(LevelTrace(
            level=5, name="hitl_gate", passed=True,
            detail=f"{risk_class} auto-approved",
        ))
        _record_guard_metric("L5", "allowed")
        logger.info(
            "Guard Gate PASSED: action=%s target=%s risk=%s",
            action.get("type"), action.get("target"), risk_class,
        )
        return GateDecision(
            allowed=True,
            risk_class=risk_class,
            blocked_at_level=None,
            reason="all-clear",
            requires_hitl=False,
            gate_trace=tuple(trace),
        )
