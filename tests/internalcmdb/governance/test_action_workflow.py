"""Tests for internalcmdb.governance.action_workflow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.governance.action_workflow import ActionWorkflow, WorkflowResult
from internalcmdb.motor.remediation import RC_1, RC_2, RC_3

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(action_type: str = "read", target: str = "host-01") -> MagicMock:
    a = MagicMock()
    a.action_type = action_type
    a.target_entity = target
    a.estimated_duration_s = 60
    a.params = {}
    return a


def _make_plan(
    plan_id: str = "plan-001",
    risk_class: str = RC_1,
    status: str = "auto_approved",
    actions: list | None = None,
    blocked_reason: str | None = None,
) -> MagicMock:
    plan = MagicMock()
    plan.plan_id = plan_id
    plan.risk_class = risk_class
    plan.status = status
    plan.actions = actions if actions is not None else [_make_action()]
    plan.insight_id = "insight-123"
    plan.confidence = 0.9
    plan.explanation = "test explanation"
    plan.blocked_reason = blocked_reason
    return plan


def _make_workflow() -> tuple[ActionWorkflow, MagicMock, MagicMock, MagicMock, MagicMock]:
    db_session = MagicMock()
    async_session = AsyncMock()
    redis_url = "redis://localhost:6379"

    with (
        patch("internalcmdb.governance.action_workflow.PolicyEnforcer") as MockPolicy,  # noqa: N806
        patch("internalcmdb.governance.action_workflow.HITLWorkflow") as MockHITL,  # noqa: N806
        patch("internalcmdb.governance.action_workflow.PlaybookExecutor") as MockExecutor,  # noqa: N806
        patch("internalcmdb.governance.action_workflow.ExecutionLock") as MockLock,  # noqa: N806
    ):
        wf = ActionWorkflow(db_session, async_session, redis_url)
        return (
            wf,
            MockPolicy.return_value,
            MockHITL.return_value,
            MockExecutor.return_value,
            MockLock.return_value,
        )


# ---------------------------------------------------------------------------
# Tests: WorkflowResult dataclass
# ---------------------------------------------------------------------------


class TestWorkflowResult:
    def test_workflow_result_defaults(self) -> None:
        r = WorkflowResult(plan_id="p1", executed=True)
        assert r.plan_id == "p1"
        assert r.executed is True
        assert r.hitl_item_id is None
        assert r.playbook_result is None
        assert r.blocked_reason is None
        assert r.policy_violations is None
        assert r.lock_denied is False

    def test_workflow_result_full(self) -> None:
        r = WorkflowResult(
            plan_id="p2",
            executed=False,
            hitl_item_id="hitl-99",
            playbook_result={"restart": {"success": True}},
            blocked_reason="policy violation",
            policy_violations=["no_delete"],
            lock_denied=True,
        )
        assert r.hitl_item_id == "hitl-99"
        assert r.lock_denied is True
        assert r.policy_violations == ["no_delete"]


# ---------------------------------------------------------------------------
# Tests: execute_plan — blocked status
# ---------------------------------------------------------------------------


class TestExecutePlanBlocked:
    @pytest.mark.asyncio
    async def test_plan_with_blocked_status_returns_immediately(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()
        plan = _make_plan(status="blocked", blocked_reason="pre-blocked")

        result = await wf.execute_plan(plan)

        assert result.executed is False
        assert result.blocked_reason == "pre-blocked"
        mock_policy.check.assert_not_called()
        mock_hitl.submit.assert_not_called()
        mock_executor.execute.assert_not_called()
        mock_lock.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocked_plan_uses_explanation_when_no_reason(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()
        plan = _make_plan(status="blocked", blocked_reason=None)
        plan.explanation = "LLM said no"

        result = await wf.execute_plan(plan)

        assert result.executed is False
        assert result.blocked_reason == "LLM said no"
        mock_policy.check.assert_not_called()
        mock_hitl.submit.assert_not_called()
        mock_executor.execute.assert_not_called()
        mock_lock.acquire.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: execute_plan — policy violation
# ---------------------------------------------------------------------------


class TestExecutePlanPolicyViolation:
    @pytest.mark.asyncio
    async def test_policy_violation_blocks_plan(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()

        violation = MagicMock()
        violation.reason = "no delete on production"
        policy_result = MagicMock()
        policy_result.compliant = False
        policy_result.violations = [violation]
        mock_policy.check.return_value = policy_result

        plan = _make_plan(risk_class=RC_1, status="auto_approved")

        result = await wf.execute_plan(plan)

        assert result.executed is False
        assert result.blocked_reason == "Policy violation"
        assert result.policy_violations == ["no delete on production"]
        assert plan.status == "blocked"
        mock_hitl.submit.assert_not_called()
        mock_executor.execute.assert_not_called()
        mock_lock.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_policy_violations_captured(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()

        v1 = MagicMock()
        v1.reason = "reason A"
        v2 = MagicMock()
        v2.reason = "reason B"
        policy_result = MagicMock()
        policy_result.compliant = False
        policy_result.violations = [v1, v2]
        mock_policy.check.return_value = policy_result

        plan = _make_plan(risk_class=RC_1, status="auto_approved")

        result = await wf.execute_plan(plan)

        assert result.policy_violations == ["reason A", "reason B"]
        mock_hitl.submit.assert_not_called()
        mock_executor.execute.assert_not_called()
        mock_lock.acquire.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: execute_plan — HITL submission (RC-2, RC-3)
# ---------------------------------------------------------------------------


class TestExecutePlanHITL:
    @pytest.mark.asyncio
    async def test_rc2_plan_submitted_to_hitl(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_policy.check.return_value = policy_result
        mock_hitl.submit = AsyncMock(return_value="hitl-item-42")

        plan = _make_plan(risk_class=RC_2, status="pending_review")

        result = await wf.execute_plan(plan)

        assert result.executed is False
        assert result.hitl_item_id == "hitl-item-42"
        mock_hitl.submit.assert_awaited_once()
        # RC-2 goes to HITL review — executor must NOT run and lock must NOT be acquired.
        mock_executor.execute.assert_not_called()
        mock_lock.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_rc3_plan_submitted_to_hitl(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_policy.check.return_value = policy_result
        mock_hitl.submit = AsyncMock(return_value="hitl-item-99")

        plan = _make_plan(risk_class=RC_3, status="pending_review")

        result = await wf.execute_plan(plan)

        assert result.executed is False
        assert result.hitl_item_id == "hitl-item-99"
        # RC-3 goes to HITL review — executor must NOT run and lock must NOT be acquired.
        mock_executor.execute.assert_not_called()
        mock_lock.acquire.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: execute_plan — auto execute (RC-1)
# ---------------------------------------------------------------------------


class TestExecutePlanAutoExecute:
    @pytest.mark.asyncio
    async def test_rc1_auto_approved_executes_playbook(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_policy.check.return_value = policy_result

        mock_lock.acquire = AsyncMock(return_value="token-xyz")
        mock_lock.release = AsyncMock()

        pb_result = MagicMock()
        pb_result.success = True
        pb_result.output = "done"
        pb_result.error = None
        mock_executor.execute = AsyncMock(return_value=pb_result)
        mock_executor.available_playbooks = {"read"}

        plan = _make_plan(risk_class=RC_1, status="auto_approved")

        result = await wf.execute_plan(plan)

        assert result.executed is True
        mock_lock.release.assert_awaited()
        # RC-1 auto-approved goes directly to execution — no HITL submission.
        mock_hitl.submit.assert_not_called()

    @pytest.mark.asyncio
    async def test_lock_denied_returns_blocked_result(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_policy.check.return_value = policy_result

        mock_lock.acquire = AsyncMock(return_value=None)

        plan = _make_plan(risk_class=RC_1, status="auto_approved")

        result = await wf.execute_plan(plan)

        assert result.executed is False
        assert result.lock_denied is True
        assert "already in progress" in (result.blocked_reason or "")
        # Lock denied path must not proceed to HITL or execution.
        mock_hitl.submit.assert_not_called()
        mock_executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_rc1_non_auto_approved_blocked(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_policy.check.return_value = policy_result

        plan = _make_plan(risk_class=RC_1, status="pending")

        result = await wf.execute_plan(plan)

        assert result.executed is False
        assert result.blocked_reason is not None
        # Non-auto-approved RC-1 must not touch HITL, executor, or lock.
        mock_hitl.submit.assert_not_called()
        mock_executor.execute.assert_not_called()
        mock_lock.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_playbook_failure_returns_blocked(self) -> None:
        wf, mock_policy, mock_hitl, mock_executor, mock_lock = _make_workflow()

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_policy.check.return_value = policy_result

        mock_lock.acquire = AsyncMock(return_value="token-abc")
        mock_lock.release = AsyncMock()

        pb_result = MagicMock()
        pb_result.success = False
        pb_result.output = None
        pb_result.error = "timeout"
        mock_executor.execute = AsyncMock(return_value=pb_result)
        mock_executor.available_playbooks = {"read"}

        plan = _make_plan(risk_class=RC_1, status="auto_approved")

        result = await wf.execute_plan(plan)

        assert result.executed is False
        assert "timeout" in (result.blocked_reason or "")
        # Playbook failure should not trigger HITL escalation.
        mock_hitl.submit.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: close
# ---------------------------------------------------------------------------


class TestClose:
    @pytest.mark.asyncio
    async def test_close_releases_lock(self) -> None:
        wf, _mock_policy, _mock_hitl, _mock_executor, mock_lock = _make_workflow()
        mock_lock.close = AsyncMock()

        await wf.close()

        mock_lock.close.assert_awaited_once()
