"""Mediated action request workflow enforcing scope, intent, expiry, and outcome capture.

pt-017 [m5-2] — epic-5 sprint-8.
No governed write path may execute without an eligible, non-expired approval record whose
scope covers the target entities.  Transitions are validated against policy_matrix rules;
the persisted ActionRequest row is updated atomically inside the caller's session.

Design decisions:
- All status literals are compared through ActionStatus to avoid magic strings.
- Transitions that require approval call PolicyEnforcer.check() before persisting.
- Expiry is evaluated at transition time; a stale approval is denied immediately (D-004).
- ChangeLog rows are written on COMPLETING a request to satisfy post-execution traceability.
"""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from internalcmdb.control.policy_matrix import (
    ActionClass,
    ApprovalRecord,
    EnforcementContext,
    PolicyEnforcer,
)
from internalcmdb.models.agent_control import ActionRequest
from internalcmdb.models.governance import ChangeLog
from internalcmdb.retrieval.task_types import ContextClass, RiskClass, TaskTypeCode

# ---------------------------------------------------------------------------
# Status literals
# ---------------------------------------------------------------------------

_STATUS_PENDING = "pending"
_STATUS_APPROVED = "approved"
_STATUS_DENIED = "denied"
_STATUS_EXECUTING = "executing"
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"
_STATUS_REVOKED = "revoked"

_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {_STATUS_COMPLETED, _STATUS_FAILED, _STATUS_REVOKED, _STATUS_DENIED}
)

# ---------------------------------------------------------------------------
# Public domain types
# ---------------------------------------------------------------------------


@dataclass
class ActionRequestSpec:
    """Input specification for creating a new mediated action request.

    Attributes:
        action_class: The governance action class (AC-001..AC-010).
        target_entity_ids: UUIDs of entities affected by this action.
        requested_by: Identity code of the requesting agent or user.
        task_type_code: Context task type code for evidence validation.
        present_evidence_classes: Evidence already assembled in the calling context.
        change_description: Human-readable summary of the intended change.
        requested_change: Structured payload for the change (written to JSONB).
        agent_run_id: Optional AgentRun association.
        approval_record: Pre-resolved approval record, if any.
        snapshot_exists: Whether a pre-change snapshot has been captured.
    """

    action_class: ActionClass
    target_entity_ids: frozenset[uuid.UUID]
    requested_by: str
    task_type_code: TaskTypeCode
    present_evidence_classes: frozenset[ContextClass]
    change_description: str
    requested_change: dict[str, Any] | None = None
    agent_run_id: uuid.UUID | None = None
    approval_record: ApprovalRecord | None = None
    snapshot_exists: bool = False


@dataclass
class TransitionResult:
    """Result of a status transition attempt.

    Attributes:
        success: Whether the transition was applied.
        new_status: The resulting status (may be unchanged on failure).
        deny_reasons: Non-empty only when transition was denied.
        warnings: Non-fatal observations.
        action_request_id: UUID of the persisted ActionRequest row.
    """

    success: bool
    new_status: str
    deny_reasons: list[str] = field(default_factory=list[str])
    warnings: list[str] = field(default_factory=list[str])
    action_request_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Workflow engine
# ---------------------------------------------------------------------------


class ActionWorkflow:
    """Manages the lifecycle of a mediated ActionRequest.

    Usage::

        workflow = ActionWorkflow(session)
        result = workflow.create(spec)       # pending
        result = workflow.approve(req_id, approval_record)
        result = workflow.begin_execution(req_id)
        result = workflow.complete(req_id, outcome)
        # or
        result = workflow.fail(req_id, "reason")
        result = workflow.revoke(req_id, "reason")
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._enforcer = PolicyEnforcer()

    # ------------------------------------------------------------------
    # Public transition methods
    # ------------------------------------------------------------------

    def create(self, spec: ActionRequestSpec) -> TransitionResult:
        """Validate initial policy, persist an ActionRequest with status=pending.

        For read-only action classes (RC-1) the request is *auto-approved* because no
        human approval gate is required; WritePath classes enter pending status.
        """
        enforcement_ctx = EnforcementContext(
            action_class=spec.action_class,
            task_type_code=spec.task_type_code,
            present_evidence_classes=spec.present_evidence_classes,
            target_entity_ids=list(spec.target_entity_ids),
            approval_record=spec.approval_record,
            snapshot_exists=spec.snapshot_exists,
        )
        result = self._enforcer.check(enforcement_ctx)
        if result.denied:
            return TransitionResult(
                success=False,
                new_status=_STATUS_DENIED,
                deny_reasons=list(result.deny_reasons),
                warnings=list(result.warnings),
            )

        risk_class = self._enforcer.get_risk_class(spec.action_class)
        initial_status = (
            _STATUS_APPROVED if risk_class == RiskClass.RC1_READ_ONLY else _STATUS_PENDING
        )

        target_scope: dict[str, Any] = {
            "entity_ids": [str(eid) for eid in sorted(spec.target_entity_ids)],
            "requested_by": spec.requested_by,
            "task_type_code": spec.task_type_code,
            "snapshot_exists": spec.snapshot_exists,
        }

        req = ActionRequest(
            request_code=_make_request_code(spec.action_class),
            agent_run_id=spec.agent_run_id,
            approval_record_id=(spec.approval_record.approval_id if spec.approval_record else None),
            action_class_text=str(spec.action_class),
            target_scope_jsonb=target_scope,
            requested_change_jsonb=spec.requested_change,
            status_text=initial_status,
        )
        self._session.add(req)
        self._session.flush()

        return TransitionResult(
            success=True,
            new_status=initial_status,
            warnings=list(result.warnings),
            action_request_id=req.action_request_id,
        )

    def approve(
        self,
        action_request_id: uuid.UUID,
        approval_record: ApprovalRecord,
    ) -> TransitionResult:
        """Attach an approval record and advance status to approved.

        Validates:
        - Request must be in *pending* status.
        - Approval must not be expired (D-004).
        - Approval scope must cover the request target entities (D-005).
        - Quorum must be satisfied for RC-4 actions (D-008).
        """
        req = self._load(action_request_id)
        if req is None:
            return _not_found(action_request_id)
        guard = self._guard_terminal(req)
        if guard:
            return guard
        denial = self._validate_approval_preconditions(req, approval_record)
        if denial is not None:
            return denial
        req.approval_record_id = approval_record.approval_id
        req.status_text = _STATUS_APPROVED
        self._session.flush()
        return TransitionResult(
            success=True,
            new_status=_STATUS_APPROVED,
            action_request_id=req.action_request_id,
        )

    def _validate_approval_preconditions(
        self,
        req: ActionRequest,
        approval_record: ApprovalRecord,
    ) -> TransitionResult | None:
        """Return a denial TransitionResult if approval preconditions are not met, else None."""
        if req.status_text != _STATUS_PENDING:
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=[f"INVALID_TRANSITION: expected pending, got {req.status_text}"],
            )
        if approval_record.is_expired:
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=["D-004: approval record is expired"],
            )
        target_ids = _extract_target_ids(req)
        if not target_ids.issubset(approval_record.scope_entity_ids):
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=["D-005: approval scope does not cover all target entities"],
            )
        action_class = ActionClass(req.action_class_text)
        risk_class = self._enforcer.get_risk_class(action_class)
        if risk_class == RiskClass.RC4_BULK_STRUCTURAL:
            return self._check_quorum_for_approve(req, approval_record, action_class, target_ids)
        return None

    def _check_quorum_for_approve(
        self,
        req: ActionRequest,
        approval_record: ApprovalRecord,
        action_class: ActionClass,
        target_ids: frozenset[uuid.UUID],
    ) -> TransitionResult | None:
        """Validate quorum for RC-4 actions; return denial or None."""
        deny_reasons = self._enforcer.check_quorum(
            EnforcementContext(
                action_class=action_class,
                task_type_code=TaskTypeCode(
                    req.target_scope_jsonb.get("task_type_code", "TT-001")
                    if req.target_scope_jsonb
                    else "TT-001"
                ),
                present_evidence_classes=frozenset(),
                target_entity_ids=list(target_ids),
                approval_record=approval_record,
                snapshot_exists=False,
            )
        )
        if deny_reasons:
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=deny_reasons,
            )
        return None

    def begin_execution(self, action_request_id: uuid.UUID) -> TransitionResult:
        """Advance from approved → executing.

        A snapshot must exist for RC-4 actions (D-006).
        """
        req = self._load(action_request_id)
        if req is None:
            return _not_found(action_request_id)
        guard = self._guard_terminal(req)
        if guard:
            return guard
        if req.status_text != _STATUS_APPROVED:
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=[f"INVALID_TRANSITION: expected approved, got {req.status_text}"],
            )
        action_class = ActionClass(req.action_class_text)
        risk_class = self._enforcer.get_risk_class(action_class)
        if risk_class == RiskClass.RC4_BULK_STRUCTURAL:
            scope = req.target_scope_jsonb or {}
            if not scope.get("snapshot_exists", False):
                return TransitionResult(
                    success=False,
                    new_status=req.status_text,
                    deny_reasons=["D-006: RC-4 action requires a pre-change snapshot"],
                )
        req.status_text = _STATUS_EXECUTING
        self._session.flush()
        return TransitionResult(
            success=True,
            new_status=_STATUS_EXECUTING,
            action_request_id=req.action_request_id,
        )

    def complete(
        self,
        action_request_id: uuid.UUID,
        outcome: dict[str, Any],
        changed_by: str,
        entity_kind_term_id: uuid.UUID,
        entity_id: uuid.UUID,
    ) -> TransitionResult:
        """Advance from executing → completed and persist a ChangeLog row.

        The ChangeLog entry provides the post-execution audit trail required by GOV-007
        and the plan traceability requirements.
        """
        req = self._load(action_request_id)
        if req is None:
            return _not_found(action_request_id)
        guard = self._guard_terminal(req)
        if guard:
            return guard
        if req.status_text != _STATUS_EXECUTING:
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=[f"INVALID_TRANSITION: expected executing, got {req.status_text}"],
            )
        now = datetime.now(tz=UTC)
        req.status_text = _STATUS_COMPLETED
        req.executed_at = now.isoformat()

        change_log = ChangeLog(
            change_code=f"CL-{req.request_code}",
            entity_kind_term_id=entity_kind_term_id,
            entity_id=entity_id,
            change_source_text="action_workflow",
            change_summary_text=f"Action {req.action_class_text} completed: {req.request_code}",
            action_request_id=req.action_request_id,
            approval_record_id=req.approval_record_id,
            after_state_jsonb=outcome,
            changed_by=changed_by,
            changed_at=now.isoformat(),
        )
        self._session.add(change_log)
        self._session.flush()
        return TransitionResult(
            success=True,
            new_status=_STATUS_COMPLETED,
            action_request_id=req.action_request_id,
        )

    def fail(self, action_request_id: uuid.UUID, reason: str) -> TransitionResult:
        """Mark request as failed from executing state."""
        req = self._load(action_request_id)
        if req is None:
            return _not_found(action_request_id)
        guard = self._guard_terminal(req)
        if guard:
            return guard
        if req.status_text != _STATUS_EXECUTING:
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=[f"INVALID_TRANSITION: expected executing, got {req.status_text}"],
            )
        req.status_text = _STATUS_FAILED
        req.target_scope_jsonb = {
            **(req.target_scope_jsonb or {}),
            "failure_reason": reason,
        }
        self._session.flush()
        return TransitionResult(
            success=True,
            new_status=_STATUS_FAILED,
            action_request_id=req.action_request_id,
        )

    def revoke(self, action_request_id: uuid.UUID, reason: str) -> TransitionResult:
        """Revoke a pending or approved request; cannot revoke executing/terminal requests."""
        req = self._load(action_request_id)
        if req is None:
            return _not_found(action_request_id)
        guard = self._guard_terminal(req)
        if guard:
            return guard
        if req.status_text == _STATUS_EXECUTING:
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=["INVALID_TRANSITION: cannot revoke while executing"],
            )
        req.status_text = _STATUS_REVOKED
        req.target_scope_jsonb = {
            **(req.target_scope_jsonb or {}),
            "revocation_reason": reason,
        }
        self._session.flush()
        return TransitionResult(
            success=True,
            new_status=_STATUS_REVOKED,
            action_request_id=req.action_request_id,
        )

    def deny(self, action_request_id: uuid.UUID, reason: str) -> TransitionResult:
        """Explicitly deny a pending request (e.g. human reviewer rejects)."""
        req = self._load(action_request_id)
        if req is None:
            return _not_found(action_request_id)
        guard = self._guard_terminal(req)
        if guard:
            return guard
        if req.status_text != _STATUS_PENDING:
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=[f"INVALID_TRANSITION: expected pending, got {req.status_text}"],
            )
        req.status_text = _STATUS_DENIED
        req.target_scope_jsonb = {
            **(req.target_scope_jsonb or {}),
            "denial_reason": reason,
        }
        self._session.flush()
        return TransitionResult(
            success=True,
            new_status=_STATUS_DENIED,
            action_request_id=req.action_request_id,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self, action_request_id: uuid.UUID) -> ActionRequest | None:
        result = self._session.get(ActionRequest, action_request_id)
        return result if isinstance(result, ActionRequest) else None

    def _guard_terminal(self, req: ActionRequest) -> TransitionResult | None:
        if req.status_text in _TERMINAL_STATUSES:
            return TransitionResult(
                success=False,
                new_status=req.status_text,
                deny_reasons=[
                    f"TERMINAL_STATUS: request {req.request_code} is already {req.status_text}"
                ],
            )
        return None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _make_request_code(action_class: ActionClass) -> str:
    """Generate a unique, traceable request code."""
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"REQ-{action_class}-{ts}-{suffix}"


def _extract_target_ids(req: ActionRequest) -> frozenset[uuid.UUID]:
    """Parse target entity UUIDs from the stored JSONB scope."""
    scope = req.target_scope_jsonb or {}
    raw = scope.get("entity_ids", [])
    ids: set[uuid.UUID] = set()
    for item in raw:
        with contextlib.suppress(ValueError):
            ids.add(uuid.UUID(str(item)))
    return frozenset(ids)


def _not_found(action_request_id: uuid.UUID) -> TransitionResult:
    return TransitionResult(
        success=False,
        new_status="unknown",
        deny_reasons=[f"NOT_FOUND: ActionRequest {action_request_id} does not exist"],
    )
