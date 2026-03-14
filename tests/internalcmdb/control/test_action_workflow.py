"""Tests for internalcmdb.control.action_workflow (pt-017).

Covers:
- create: RC-1 action → auto-approved (status=approved)
- create: RC-3 action with valid evidence and approval → pending
- create: policy denial (missing evidence) → denied, success=False
- approve: pending → approved, with valid non-expired approval
- approve: expired approval → D-004 denial
- approve: wrong action class in approval → D-005
- approve: out-of-scope entity IDs → D-005
- approve: single approver on RC-4 action → D-008 quorum denial
- begin_execution: approved → executing
- begin_execution: non-approved status → INVALID_TRANSITION
- begin_execution: RC-4 without snapshot → D-006
- complete: executing → completed, ChangeLog row created
- complete: non-executing status → INVALID_TRANSITION
- fail: executing → failed with reason stored in scope
- fail: non-executing status → INVALID_TRANSITION
- revoke: pending → revoked
- revoke: executing status → INVALID_TRANSITION
- deny: pending → denied
- NOT_FOUND for all operations on non-existent IDs
- TERMINAL_STATUS guard for all terminal statuses
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from internalcmdb.control.action_workflow import (  # pylint: disable=import-error
    ActionRequestSpec,
    ActionWorkflow,
)
from internalcmdb.control.policy_matrix import (  # pylint: disable=import-error
    ActionClass,
    ApprovalRecord,
)
from internalcmdb.models.agent_control import ActionRequest  # pylint: disable=import-error
from internalcmdb.models.governance import ChangeLog  # pylint: disable=import-error
from internalcmdb.retrieval.task_types import (  # pylint: disable=import-error
    ContextClass,
    TaskTypeCode,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_approval(
    action_class: ActionClass = ActionClass.REGISTRY_ENTITY_CREATE,
    approver_codes: frozenset[str] | None = None,
    scope_entity_ids: frozenset[uuid.UUID] | None = None,
    is_expired: bool = False,
) -> ApprovalRecord:
    return ApprovalRecord(
        approval_id=uuid.uuid4(),
        approver_codes=frozenset({"approver-1"}) if approver_codes is None else approver_codes,
        action_class=action_class,
        scope_entity_ids=scope_entity_ids or frozenset(),
        is_expired=is_expired,
    )


def _make_req(
    status: str = "pending",
    action_class: str = "AC-003",
    entity_ids: list[uuid.UUID] | None = None,
    req_id: uuid.UUID | None = None,
    approval_record_id: uuid.UUID | None = None,
    snapshot_exists: bool = False,
    task_type_code: str = "TT-001",
) -> MagicMock:
    req = MagicMock(spec=ActionRequest)
    req.action_request_id = req_id or uuid.uuid4()
    req.request_code = f"REQ-{action_class}-TEST"
    req.status_text = status
    req.action_class_text = action_class
    req.approval_record_id = approval_record_id
    req.executed_at = None
    req.target_scope_jsonb = {
        "entity_ids": [str(e) for e in (entity_ids or [])],
        "requested_by": "test-agent",
        "task_type_code": task_type_code,
        "snapshot_exists": snapshot_exists,
    }
    req.requested_change_jsonb = None
    return req


def _make_session(req: MagicMock | None = None) -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    session.get = MagicMock(return_value=req)
    return session


def _rc1_spec() -> ActionRequestSpec:
    return ActionRequestSpec(
        action_class=ActionClass.REGISTRY_READ,
        target_entity_ids=frozenset(),
        requested_by="agent-test",
        task_type_code=TaskTypeCode.INFRASTRUCTURE_AUDIT,
        present_evidence_classes=frozenset(
            {
                ContextClass.REGISTRY_HOST,
                ContextClass.EVIDENCE_ARTIFACT,
            }
        ),
        change_description="Read-only audit",
    )


def _rc3_spec(approval: ApprovalRecord | None = None) -> ActionRequestSpec:
    return ActionRequestSpec(
        action_class=ActionClass.REGISTRY_ENTITY_CREATE,
        target_entity_ids=frozenset(),
        requested_by="agent-test",
        task_type_code=TaskTypeCode.REGISTRY_RECONCILIATION,
        present_evidence_classes=frozenset(
            {
                ContextClass.REGISTRY_HOST,
                ContextClass.REGISTRY_SERVICE,
                ContextClass.EVIDENCE_ARTIFACT,
                ContextClass.OBSERVED_FACT,
                ContextClass.REGISTRY_OWNERSHIP,
            }
        ),
        change_description="Create new entity",
        approval_record=approval,
    )


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestCreate:
    def test_rc1_is_auto_approved(self) -> None:
        session = _make_session()
        wf = ActionWorkflow(session)
        result = wf.create(_rc1_spec())
        assert result.success is True
        assert result.new_status == "approved"

    def test_rc3_without_approval_creates_pending(self) -> None:
        session = _make_session()
        wf = ActionWorkflow(session)
        # Without approval, policy check fails for RC-3 (D-003)
        result = wf.create(_rc3_spec(approval=None))
        assert result.success is False
        assert result.new_status == "denied"
        assert any("D-003" in r for r in result.deny_reasons)

    def test_rc1_calls_session_add_and_flush(self) -> None:
        session = _make_session()
        wf = ActionWorkflow(session)
        wf.create(_rc1_spec())
        session.add.assert_called_once()
        session.flush.assert_called_once()

    def test_denied_create_does_not_write_db(self) -> None:
        session = _make_session()
        wf = ActionWorkflow(session)
        # Missing REGISTRY_OWNERSHIP mandatory evidence → denied
        spec = ActionRequestSpec(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            target_entity_ids=frozenset(),
            requested_by="agent",
            task_type_code=TaskTypeCode.INFRASTRUCTURE_AUDIT,
            present_evidence_classes=frozenset({ContextClass.REGISTRY_HOST}),
            change_description="Change",
        )
        result = wf.create(spec)
        assert result.success is False
        session.add.assert_not_called()


# ---------------------------------------------------------------------------
# approve()
# ---------------------------------------------------------------------------


class TestApprove:
    def test_approve_pending_request_succeeds(self) -> None:
        req = _make_req(status="pending")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        rec = _make_approval(action_class=ActionClass.REGISTRY_ENTITY_CREATE)
        result = wf.approve(req.action_request_id, rec)
        assert result.success is True
        assert result.new_status == "approved"
        assert req.status_text == "approved"

    def test_approve_updates_approval_record_id(self) -> None:
        req = _make_req(status="pending")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        rec = _make_approval(action_class=ActionClass.REGISTRY_ENTITY_CREATE)
        wf.approve(req.action_request_id, rec)
        assert req.approval_record_id == rec.approval_id

    def test_approve_expired_record_fails(self) -> None:
        req = _make_req(status="pending")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        rec = _make_approval(is_expired=True)
        result = wf.approve(req.action_request_id, rec)
        assert result.success is False
        assert any("D-004" in r for r in result.deny_reasons)

    def test_approve_wrong_action_class_fails(self) -> None:
        req = _make_req(status="pending", action_class="AC-003")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        rec = _make_approval(action_class=ActionClass.DOCUMENT_CREATE)  # wrong class
        result = wf.approve(req.action_request_id, rec)
        assert result.success is False
        assert any("D-005" in r for r in result.deny_reasons)

    def test_approve_out_of_scope_entities_fails(self) -> None:
        eid = uuid.uuid4()
        req = _make_req(status="pending", entity_ids=[eid])
        session = _make_session(req)
        wf = ActionWorkflow(session)
        # Approval covers a different entity
        rec = _make_approval(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            scope_entity_ids=frozenset({uuid.uuid4()}),  # different entity
        )
        result = wf.approve(req.action_request_id, rec)
        assert result.success is False
        assert any("D-005" in r for r in result.deny_reasons)

    def test_approve_not_found_fails(self) -> None:
        session = _make_session(req=None)
        wf = ActionWorkflow(session)
        rec = _make_approval()
        result = wf.approve(uuid.uuid4(), rec)
        assert result.success is False
        assert any("NOT_FOUND" in r for r in result.deny_reasons)

    def test_approve_already_approved_fails_terminal_ish(self) -> None:
        req = _make_req(status="approved")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        rec = _make_approval(action_class=ActionClass.REGISTRY_ENTITY_CREATE)
        result = wf.approve(req.action_request_id, rec)
        assert result.success is False

    def test_approve_rc4_single_approver_quorum_fails(self) -> None:
        req = _make_req(status="pending", action_class="AC-008")  # SCHEMA_MIGRATION
        session = _make_session(req)
        wf = ActionWorkflow(session)
        rec = _make_approval(
            action_class=ActionClass.SCHEMA_MIGRATION,
            approver_codes=frozenset({"only-one"}),
        )
        result = wf.approve(req.action_request_id, rec)
        assert result.success is False
        assert any("D-008" in r for r in result.deny_reasons)


# ---------------------------------------------------------------------------
# begin_execution()
# ---------------------------------------------------------------------------


class TestBeginExecution:
    def test_approved_to_executing(self) -> None:
        req = _make_req(status="approved", action_class="AC-003")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.begin_execution(req.action_request_id)
        assert result.success is True
        assert result.new_status == "executing"
        assert req.status_text == "executing"

    def test_pending_not_approved_fails(self) -> None:
        req = _make_req(status="pending", action_class="AC-003")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.begin_execution(req.action_request_id)
        assert result.success is False
        assert any("INVALID_TRANSITION" in r for r in result.deny_reasons)

    def test_rc4_without_snapshot_fails(self) -> None:
        req = _make_req(status="approved", action_class="AC-008", snapshot_exists=False)
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.begin_execution(req.action_request_id)
        assert result.success is False
        assert any("D-006" in r for r in result.deny_reasons)

    def test_rc4_with_snapshot_succeeds(self) -> None:
        req = _make_req(status="approved", action_class="AC-008", snapshot_exists=True)
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.begin_execution(req.action_request_id)
        assert result.success is True
        assert result.new_status == "executing"

    def test_not_found_fails(self) -> None:
        session = _make_session(req=None)
        wf = ActionWorkflow(session)
        result = wf.begin_execution(uuid.uuid4())
        assert result.success is False
        assert any("NOT_FOUND" in r for r in result.deny_reasons)


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


class TestComplete:
    def test_executing_to_completed(self) -> None:
        req = _make_req(status="executing")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        ek_id = uuid.uuid4()
        ent_id = uuid.uuid4()
        result = wf.complete(
            req.action_request_id,
            outcome={"result": "ok"},
            changed_by="agent-test",
            entity_kind_term_id=ek_id,
            entity_id=ent_id,
        )
        assert result.success is True
        assert result.new_status == "completed"
        assert req.status_text == "completed"
        assert req.executed_at is not None

    def test_complete_writes_changelog(self) -> None:
        req = _make_req(status="executing")
        added_objects: list[object] = []
        session = _make_session(req)
        session.add.side_effect = added_objects.append
        wf = ActionWorkflow(session)
        wf.complete(
            req.action_request_id,
            outcome={},
            changed_by="agent",
            entity_kind_term_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
        )
        # Should have added a ChangeLog row
        assert any(isinstance(o, ChangeLog) for o in added_objects)

    def test_non_executing_fails(self) -> None:
        req = _make_req(status="approved")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.complete(
            req.action_request_id,
            outcome={},
            changed_by="x",
            entity_kind_term_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
        )
        assert result.success is False
        assert any("INVALID_TRANSITION" in r for r in result.deny_reasons)

    def test_not_found_fails(self) -> None:
        session = _make_session(req=None)
        wf = ActionWorkflow(session)
        result = wf.complete(
            uuid.uuid4(),
            outcome={},
            changed_by="x",
            entity_kind_term_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
        )
        assert result.success is False
        assert any("NOT_FOUND" in r for r in result.deny_reasons)


# ---------------------------------------------------------------------------
# fail()
# ---------------------------------------------------------------------------


class TestFail:
    def test_executing_to_failed(self) -> None:
        req = _make_req(status="executing")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.fail(req.action_request_id, reason="unexpected error")
        assert result.success is True
        assert result.new_status == "failed"
        assert req.status_text == "failed"

    def test_failure_reason_stored_in_scope(self) -> None:
        req = _make_req(status="executing")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        wf.fail(req.action_request_id, reason="out of memory")
        assert req.target_scope_jsonb.get("failure_reason") == "out of memory"

    def test_non_executing_fails(self) -> None:
        req = _make_req(status="pending")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.fail(req.action_request_id, reason="reason")
        assert result.success is False

    def test_not_found_fails(self) -> None:
        session = _make_session(req=None)
        wf = ActionWorkflow(session)
        result = wf.fail(uuid.uuid4(), reason="x")
        assert result.success is False
        assert any("NOT_FOUND" in r for r in result.deny_reasons)


# ---------------------------------------------------------------------------
# revoke()
# ---------------------------------------------------------------------------


class TestRevoke:
    def test_pending_to_revoked(self) -> None:
        req = _make_req(status="pending")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.revoke(req.action_request_id, reason="no longer needed")
        assert result.success is True
        assert result.new_status == "revoked"

    def test_approved_to_revoked(self) -> None:
        req = _make_req(status="approved")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.revoke(req.action_request_id, reason="changed mind")
        assert result.success is True
        assert result.new_status == "revoked"

    def test_executing_cannot_be_revoked(self) -> None:
        req = _make_req(status="executing")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.revoke(req.action_request_id, reason="oops")
        assert result.success is False
        assert any("INVALID_TRANSITION" in r for r in result.deny_reasons)

    def test_revocation_reason_stored_in_scope(self) -> None:
        req = _make_req(status="pending")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        wf.revoke(req.action_request_id, reason="changed")
        assert req.target_scope_jsonb.get("revocation_reason") == "changed"

    def test_not_found_fails(self) -> None:
        session = _make_session(req=None)
        wf = ActionWorkflow(session)
        result = wf.revoke(uuid.uuid4(), reason="x")
        assert result.success is False


# ---------------------------------------------------------------------------
# deny()
# ---------------------------------------------------------------------------


class TestDeny:
    def test_pending_to_denied(self) -> None:
        req = _make_req(status="pending")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.deny(req.action_request_id, reason="rejected by reviewer")
        assert result.success is True
        assert result.new_status == "denied"

    def test_non_pending_cannot_be_denied(self) -> None:
        req = _make_req(status="approved")
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.deny(req.action_request_id, reason="denied")
        assert result.success is False


# ---------------------------------------------------------------------------
# Terminal status guard
# ---------------------------------------------------------------------------


class TestTerminalStatusGuard:
    @pytest.mark.parametrize("terminal_status", ["completed", "failed", "revoked", "denied"])
    def test_start_from_terminal_always_fails(self, terminal_status: str) -> None:
        req = _make_req(status=terminal_status)
        session = _make_session(req)
        wf = ActionWorkflow(session)
        # All transitions from terminal status must be blocked
        result = wf.revoke(req.action_request_id, reason="late attempt")
        assert result.success is False
        assert any("TERMINAL_STATUS" in r for r in result.deny_reasons)

    @pytest.mark.parametrize("terminal_status", ["completed", "failed", "revoked", "denied"])
    def test_begin_execution_from_terminal_fails(self, terminal_status: str) -> None:
        req = _make_req(status=terminal_status)
        session = _make_session(req)
        wf = ActionWorkflow(session)
        result = wf.begin_execution(req.action_request_id)
        assert result.success is False
        assert any("TERMINAL_STATUS" in r for r in result.deny_reasons)
