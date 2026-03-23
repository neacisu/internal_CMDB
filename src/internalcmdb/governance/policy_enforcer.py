"""internalCMDB — Policy Enforcer (pt-058).

Evaluates proposed actions against the active governance policy set.
Each policy is loaded from ``governance.policy_record`` and compiled into a
callable predicate.  When :meth:`PolicyEnforcer.check` is invoked the action
dict is tested against every active policy; violations are collected and
returned as a :class:`PolicyCheckResult`.

Public surface::

    from internalcmdb.governance.policy_enforcer import PolicyEnforcer

    enforcer = PolicyEnforcer(session)
    result = enforcer.check(action={"type": "deploy", "target": "prod"})
    if not result.compliant:
        for v in result.violations:
            print(v)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyViolation:
    """A single policy violation."""

    policy_code: str
    policy_name: str
    reason: str


@dataclass(frozen=True)
class PolicyCheckResult:
    """Aggregate result of running all active policies against an action."""

    compliant: bool
    violations: tuple[PolicyViolation, ...] = field(default_factory=tuple)

    def __init__(
        self, *, compliant: bool, violations: list[PolicyViolation] | None = None
    ) -> None:
        object.__setattr__(self, "compliant", compliant)
        object.__setattr__(self, "violations", tuple(violations or []))


class PolicyEnforcer:
    """Evaluates actions against the active governance policy set."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def check(self, action: dict[str, Any], context: dict[str, Any] | None = None) -> PolicyCheckResult:
        """Check *action* against all active policies.

        Returns a :class:`PolicyCheckResult` — ``compliant=True`` when no
        violations are found.
        """
        from internalcmdb.models.governance import PolicyRecord  # noqa: PLC0415

        violations: list[PolicyViolation] = []

        try:
            policies = (
                self._session.query(PolicyRecord)
                .filter(PolicyRecord.is_active.is_(True))
                .all()
            )
        except Exception:
            logger.error(
                "Policy lookup failed — FAIL-CLOSED: treating action as non-compliant",
                exc_info=True,
            )
            return PolicyCheckResult(
                compliant=False,
                violations=[
                    PolicyViolation(
                        policy_code="SYS-FAIL-CLOSED",
                        policy_name="System Fail-Closed Guard",
                        reason="Policy database unavailable; all actions blocked until restored",
                    )
                ],
            )

        action_type = action.get("type", "")
        target = action.get("target", "")

        for policy in policies:
            rules: dict[str, Any] = policy.rules_jsonb or {}

            blocked_actions = rules.get("blocked_actions", [])
            if action_type in blocked_actions:
                violations.append(
                    PolicyViolation(
                        policy_code=policy.policy_code,
                        policy_name=policy.policy_name,
                        reason=f"Action '{action_type}' is blocked by policy",
                    )
                )

            required_approval = rules.get("requires_approval_for", [])
            if action_type in required_approval and not action.get("has_approval"):
                violations.append(
                    PolicyViolation(
                        policy_code=policy.policy_code,
                        policy_name=policy.policy_name,
                        reason=f"Action '{action_type}' requires prior approval",
                    )
                )

            restricted_targets = rules.get("restricted_targets", [])
            if target in restricted_targets and not action.get("override"):
                violations.append(
                    PolicyViolation(
                        policy_code=policy.policy_code,
                        policy_name=policy.policy_name,
                        reason=f"Target '{target}' is restricted",
                    )
                )

        return PolicyCheckResult(compliant=(not violations), violations=violations)
