"""F3.1 — Action Workflow Bridge.

Orchestrates the full lifecycle of a remediation action: policy check →
risk-class routing → HITL submission (if needed) → execution via playbook.

This module wires together:
    - :class:`~internalcmdb.governance.policy_enforcer.PolicyEnforcer`
    - :class:`~internalcmdb.governance.hitl_workflow.HITLWorkflow`
    - :class:`~internalcmdb.motor.playbooks.PlaybookExecutor`
    - :class:`~internalcmdb.motor.execution_lock.ExecutionLock`
    - :class:`~internalcmdb.motor.remediation.RemediationPlan`

Public surface::

    from internalcmdb.governance.action_workflow import ActionWorkflow

    wf = ActionWorkflow(db_session, async_session, redis_url)
    result = await wf.execute_plan(plan)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from internalcmdb.governance.hitl_workflow import HITLWorkflow
from internalcmdb.governance.policy_enforcer import PolicyEnforcer
from internalcmdb.motor.execution_lock import ExecutionLock
from internalcmdb.motor.playbooks import PlaybookExecutor
from internalcmdb.motor.remediation import RC_1, RC_2, RC_3, RemediationPlan

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    """Outcome of the action workflow."""

    plan_id: str
    executed: bool
    hitl_item_id: str | None = None
    playbook_result: dict[str, Any] | None = None
    blocked_reason: str | None = None
    policy_violations: list[str] | None = None
    lock_denied: bool = False


class ActionWorkflow:
    """End-to-end action workflow: policy → approval → lock → execute."""

    def __init__(
        self,
        db_session: Session,
        async_session: AsyncSession,
        redis_url: str,
    ) -> None:
        self._policy = PolicyEnforcer(db_session)
        self._hitl = HITLWorkflow(async_session)
        self._executor = PlaybookExecutor()
        self._lock = ExecutionLock(redis_url)

    async def execute_plan(self, plan: RemediationPlan) -> WorkflowResult:
        """Drive a remediation plan through the full approval and execution pipeline."""
        if plan.status == "blocked":
            return WorkflowResult(
                plan_id=plan.plan_id,
                executed=False,
                blocked_reason=plan.blocked_reason or plan.explanation,
            )

        result = self._check_policy(plan)
        if result:
            return result

        if plan.risk_class in {RC_2, RC_3}:
            return await self._submit_to_hitl(plan)

        if plan.risk_class != RC_1 or plan.status != "auto_approved":
            return WorkflowResult(
                plan_id=plan.plan_id,
                executed=False,
                blocked_reason=f"Not auto-executable: risk={plan.risk_class} status={plan.status}",
            )

        return await self._auto_execute(plan)

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _check_policy(self, plan: RemediationPlan) -> WorkflowResult | None:
        """Return a blocked WorkflowResult if policy fails, else None."""
        policy_result = self._policy.check(
            action={
                "type": plan.actions[0].action_type if plan.actions else "unknown",
                "target": plan.actions[0].target_entity if plan.actions else "unknown",
                "risk_class": plan.risk_class,
            }
        )
        if not policy_result.compliant:
            reasons = [v.reason for v in policy_result.violations]
            logger.warning("Plan %s blocked by policy: %s", plan.plan_id, reasons)
            plan.status = "blocked"
            return WorkflowResult(
                plan_id=plan.plan_id,
                executed=False,
                blocked_reason="Policy violation",
                policy_violations=reasons,
            )
        return None

    async def _submit_to_hitl(self, plan: RemediationPlan) -> WorkflowResult:
        """Submit an RC-2/RC-3 plan for HITL review."""
        item_id = await self._hitl.submit(
            {
                "item_type": "remediation_review",
                "risk_class": plan.risk_class,
                "source_event_id": plan.insight_id,
                "correlation_id": plan.plan_id,
                "context": {
                    "plan_id": plan.plan_id,
                    "actions": [
                        {"type": a.action_type, "target": a.target_entity} for a in plan.actions
                    ],
                    "confidence": plan.confidence,
                    "explanation": plan.explanation,
                },
            }
        )
        logger.info("Plan %s submitted for HITL review as item %s", plan.plan_id, item_id)
        return WorkflowResult(plan_id=plan.plan_id, executed=False, hitl_item_id=item_id)

    async def _auto_execute(self, plan: RemediationPlan) -> WorkflowResult:
        """Acquire locks and execute playbooks for an RC-1 auto-approved plan."""
        lock_tokens: list[tuple[str, str, str]] = []
        for action in plan.actions:
            token = await self._lock.acquire(
                action.target_entity,
                action.action_type,
                window_seconds=max(action.estimated_duration_s * 2, 300),
            )
            if not token:
                logger.warning(
                    "Lock denied for %s on %s.", action.action_type, action.target_entity
                )
                for ent, act, tok in lock_tokens:
                    await self._lock.release(ent, act, tok)
                return WorkflowResult(
                    plan_id=plan.plan_id,
                    executed=False,
                    lock_denied=True,
                    blocked_reason="Execution already in progress for target",
                )
            lock_tokens.append((action.target_entity, action.action_type, token))

        try:
            return await self._run_playbooks(plan)
        finally:
            for ent, act, tok in lock_tokens:
                await self._lock.release(ent, act, tok)

    async def _run_playbooks(self, plan: RemediationPlan) -> WorkflowResult:
        """Execute playbooks for each action in the plan."""
        combined: dict[str, Any] = {}
        for action in plan.actions:
            if action.action_type not in self._executor.available_playbooks:
                logger.info("No playbook for action %s — logging only.", action.action_type)
                continue

            pb_result = await self._executor.execute(action.action_type, action.params)
            combined[action.action_type] = {
                "success": pb_result.success,
                "output": pb_result.output,
                "error": pb_result.error,
            }
            if not pb_result.success:
                logger.error("Playbook %s failed: %s", action.action_type, pb_result.error)
                return WorkflowResult(
                    plan_id=plan.plan_id,
                    executed=False,
                    playbook_result=combined,
                    blocked_reason=f"Playbook {action.action_type} failed: {pb_result.error}",
                )
        return WorkflowResult(plan_id=plan.plan_id, executed=True, playbook_result=combined)

    async def close(self) -> None:
        """Release resources."""
        await self._lock.close()
