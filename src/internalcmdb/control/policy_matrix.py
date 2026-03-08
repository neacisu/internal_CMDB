"""internalCMDB — Policy Matrix and Deny-by-Default Enforcement (pt-016).

Implements the formal policy matrix defined in ``docs/governance/policy-matrix.md``
(GOV-007) as Python dataclasses and an enforcement engine.

The :class:`PolicyEnforcer` is the single entry point for policy enforcement.
All governed write paths must call :meth:`PolicyEnforcer.check` before
executing any state-changing operation.

Read-only actions (RC-1) are exempt from approval checks but must still
satisfy evidence pack contract validation (deny rules D-002 and D-003).

Usage::

    from internalcmdb.control.policy_matrix import ActionClass, PolicyEnforcer
    from internalcmdb.control.policy_matrix import EnforcementContext, DenyDecision

    ctx = EnforcementContext(
        action_class=ActionClass.REGISTRY_ENTITY_CREATE,
        present_evidence_classes=frozenset({ContextClass.REGISTRY_HOST, ...}),
        task_type_code=TaskTypeCode.INFRASTRUCTURE_AUDIT,
        approval_record=my_approval,
        target_entity_ids=[uuid],
    )
    result = PolicyEnforcer().check(ctx)
    if result.denied:
        raise PermissionError(result.deny_reasons)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from internalcmdb.retrieval.task_types import (
    ContextClass,
    RiskClass,
    TaskTypeCode,
    get_contract,
    validate_pack_classes,
)

# ---------------------------------------------------------------------------
# Action class enumeration (GOV-007)
# ---------------------------------------------------------------------------


class ActionClass(StrEnum):
    """Wave-1 supported action classes (GOV-007)."""

    REGISTRY_READ = "AC-001"
    DOCUMENT_VALIDATION_RUN = "AC-002"
    REGISTRY_ENTITY_CREATE = "AC-003"
    REGISTRY_ENTITY_UPDATE = "AC-004"
    DISCOVERY_RUN = "AC-005"
    DOCUMENT_CREATE = "AC-006"
    DOCUMENT_UPDATE = "AC-007"
    SCHEMA_MIGRATION = "AC-008"
    AGENT_RUN_TRIGGER = "AC-009"
    BULK_REGISTRY_IMPORT = "AC-010"


# ---------------------------------------------------------------------------
# Policy entry per action class
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyEntry:
    """Policy contract for one action class.

    Attributes:
        action_class:             Canonical action class identifier.
        risk_class:               Risk tier per ADR-004.
        mandatory_evidence_classes: Evidence classes that must be present.
        approval_required:        True when a non-expired approval record is required.
        quorum_required:          True when more than one approver is needed (RC-4).
        snapshot_required:        True when a pre-execution snapshot must exist.
        post_verification_required: True when post-execution verification is mandatory.
        description:              Human-readable description.
    """

    action_class: ActionClass
    risk_class: RiskClass
    mandatory_evidence_classes: frozenset[ContextClass]
    approval_required: bool
    quorum_required: bool
    snapshot_required: bool
    post_verification_required: bool
    description: str


# ---------------------------------------------------------------------------
# Policy registry — one entry per action class
# ---------------------------------------------------------------------------


_POLICY_REGISTRY: dict[ActionClass, PolicyEntry] = {
    ActionClass.REGISTRY_READ: PolicyEntry(
        action_class=ActionClass.REGISTRY_READ,
        risk_class=RiskClass.RC1_READ_ONLY,
        mandatory_evidence_classes=frozenset(),
        approval_required=False,
        quorum_required=False,
        snapshot_required=False,
        post_verification_required=False,
        description="Read-only query or export from registry/discovery/retrieval schemas.",
    ),
    ActionClass.DOCUMENT_VALIDATION_RUN: PolicyEntry(
        action_class=ActionClass.DOCUMENT_VALIDATION_RUN,
        risk_class=RiskClass.RC1_READ_ONLY,
        mandatory_evidence_classes=frozenset({ContextClass.CANONICAL_DOC}),
        approval_required=False,
        quorum_required=False,
        snapshot_required=False,
        post_verification_required=True,
        description="Execute metadata validator against one or more documents.",
    ),
    ActionClass.REGISTRY_ENTITY_CREATE: PolicyEntry(
        action_class=ActionClass.REGISTRY_ENTITY_CREATE,
        risk_class=RiskClass.RC3_SUPERVISED_WRITE,
        mandatory_evidence_classes=frozenset({ContextClass.REGISTRY_OWNERSHIP}),
        approval_required=True,
        quorum_required=False,
        snapshot_required=False,
        post_verification_required=True,
        description="INSERT a new entity into a registry schema table.",
    ),
    ActionClass.REGISTRY_ENTITY_UPDATE: PolicyEntry(
        action_class=ActionClass.REGISTRY_ENTITY_UPDATE,
        risk_class=RiskClass.RC3_SUPERVISED_WRITE,
        mandatory_evidence_classes=frozenset({ContextClass.REGISTRY_OWNERSHIP}),
        approval_required=True,
        quorum_required=False,
        snapshot_required=False,
        post_verification_required=True,
        description="UPDATE an existing entity in a registry schema table.",
    ),
    ActionClass.DISCOVERY_RUN: PolicyEntry(
        action_class=ActionClass.DISCOVERY_RUN,
        risk_class=RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE,
        mandatory_evidence_classes=frozenset({ContextClass.REGISTRY_HOST}),
        approval_required=True,
        quorum_required=False,
        snapshot_required=False,
        post_verification_required=True,
        description="Execute a discovery collection run against one or more hosts.",
    ),
    ActionClass.DOCUMENT_CREATE: PolicyEntry(
        action_class=ActionClass.DOCUMENT_CREATE,
        risk_class=RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE,
        mandatory_evidence_classes=frozenset(
            {ContextClass.CANONICAL_DOC, ContextClass.SCHEMA_ENTITY, ContextClass.TAXONOMY_TERM}
        ),
        approval_required=True,
        quorum_required=False,
        snapshot_required=False,
        post_verification_required=True,
        description="Create a new governance or infrastructure document (draft; human commits).",
    ),
    ActionClass.DOCUMENT_UPDATE: PolicyEntry(
        action_class=ActionClass.DOCUMENT_UPDATE,
        risk_class=RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE,
        mandatory_evidence_classes=frozenset(
            {ContextClass.CANONICAL_DOC, ContextClass.SCHEMA_ENTITY}
        ),
        approval_required=True,
        quorum_required=False,
        snapshot_required=False,
        post_verification_required=True,
        description="Modify an existing governance or infrastructure document.",
    ),
    ActionClass.SCHEMA_MIGRATION: PolicyEntry(
        action_class=ActionClass.SCHEMA_MIGRATION,
        risk_class=RiskClass.RC4_BULK_STRUCTURAL,
        mandatory_evidence_classes=frozenset(
            {ContextClass.SCHEMA_ENTITY, ContextClass.CANONICAL_DOC}
        ),
        approval_required=True,
        quorum_required=True,
        snapshot_required=True,
        post_verification_required=True,
        description="Apply a database schema migration (Alembic revision).",
    ),
    ActionClass.AGENT_RUN_TRIGGER: PolicyEntry(
        action_class=ActionClass.AGENT_RUN_TRIGGER,
        risk_class=RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE,
        mandatory_evidence_classes=frozenset(),
        approval_required=True,
        quorum_required=False,
        snapshot_required=False,
        post_verification_required=True,
        description="Trigger a new AgentRun for a supported task type.",
    ),
    ActionClass.BULK_REGISTRY_IMPORT: PolicyEntry(
        action_class=ActionClass.BULK_REGISTRY_IMPORT,
        risk_class=RiskClass.RC4_BULK_STRUCTURAL,
        mandatory_evidence_classes=frozenset(
            {ContextClass.REGISTRY_OWNERSHIP, ContextClass.EVIDENCE_ARTIFACT}
        ),
        approval_required=True,
        quorum_required=True,
        snapshot_required=True,
        post_verification_required=True,
        description="Bulk INSERT/UPSERT of registry entities from a discovery artifact.",
    ),
}


def get_policy(action_class: ActionClass) -> PolicyEntry:
    """Return the policy entry for *action_class*.

    Raises:
        KeyError: if no policy entry exists (should never happen with a valid
                  ``ActionClass`` enum member).
    """
    try:
        return _POLICY_REGISTRY[action_class]
    except KeyError:
        known = ", ".join(ac.value for ac in ActionClass)
        raise KeyError(
            f"No policy entry defined for action class {action_class!r}. "
            f"Known wave-1 classes: {known}"
        ) from None


# ---------------------------------------------------------------------------
# Approval record (lightweight DTO — not an ORM model itself)
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRecord:
    """Minimal representation of an approval for enforcement checks.

    Attributes:
        approval_id:      UUID of the approval record in the DB.
        approver_codes:   Set of approver identity codes who have approved.
        action_class:     The action class this approval covers.
        scope_entity_ids: Explicit set of entity IDs covered by the approval.
                          Empty set means the approval covers all entities in
                          the request scope (use with caution).
        is_expired:       True if the approval wall-clock has passed.
        metadata:         Free-form additional context.
    """

    approval_id: uuid.UUID
    approver_codes: frozenset[str]
    action_class: ActionClass
    scope_entity_ids: frozenset[uuid.UUID]
    is_expired: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def approver_count(self) -> int:
        return len(self.approver_codes)


# ---------------------------------------------------------------------------
# Enforcement input context
# ---------------------------------------------------------------------------


@dataclass
class EnforcementContext:
    """Input to :meth:`PolicyEnforcer.check`.

    Attributes:
        action_class:           The action to be evaluated.
        task_type_code:         Task type for evidence contract lookup.
        present_evidence_classes: Context classes actually present in the
                                  assembled evidence pack.
        target_entity_ids:      Entity IDs that will be affected by the action.
        approval_record:        The approval record (if any) presented for
                                this action.  None for RC-1 actions.
        snapshot_exists:        True if a pre-execution snapshot has been
                                recorded (required for RC-4 actions).
        approver_codes:         Alias for approval_record.approver_codes when
                                no approval record object is available.
    """

    action_class: ActionClass
    task_type_code: TaskTypeCode
    present_evidence_classes: frozenset[ContextClass]
    target_entity_ids: list[uuid.UUID] = field(default_factory=list)
    approval_record: ApprovalRecord | None = field(default=None)
    snapshot_exists: bool = field(default=False)


# ---------------------------------------------------------------------------
# Enforcement result
# ---------------------------------------------------------------------------


@dataclass
class EnforcementResult:
    """Result from :meth:`PolicyEnforcer.check`.

    Attributes:
        denied:       True if any deny condition was triggered.
        deny_reasons: List of human-readable deny rule IDs and explanations.
        warnings:     Non-blocking warnings (e.g. recommended evidence absent).
        policy:       The policy entry that was evaluated.
    """

    denied: bool
    deny_reasons: list[str]
    warnings: list[str]
    policy: PolicyEntry


# ---------------------------------------------------------------------------
# Policy Enforcer
# ---------------------------------------------------------------------------


_MIN_QUORUM_APPROVERS: int = 2


class PolicyEnforcer:
    """Stateless policy enforcement engine.

    Call :meth:`check` before any governed action.  The enforcer applies all
    deny-by-default rules (D-001 through D-008) and returns an
    :class:`EnforcementResult`.
    """

    def check(self, ctx: EnforcementContext) -> EnforcementResult:
        """Evaluate policy for *ctx*.

        Returns:
            :class:`EnforcementResult` with ``denied=True`` if any deny
            condition is triggered.
        """
        policy = get_policy(ctx.action_class)
        deny_reasons: list[str] = []
        warnings: list[str] = []

        # D-002 + D-003: evidence contract violations
        try:
            contract = get_contract(ctx.task_type_code)
            violations = validate_pack_classes(contract, ctx.present_evidence_classes)
            for v in violations:
                deny_reasons.append(f"{v.code} [{v.context_class}]: {v.message}")
        except KeyError as exc:
            deny_reasons.append(f"D-001: {exc}")

        # Policy mandatory evidence classes
        for cls in policy.mandatory_evidence_classes:
            if cls not in ctx.present_evidence_classes:
                deny_reasons.append(
                    f"POLICY_EVIDENCE_MISSING: action {ctx.action_class.value} "
                    f"requires mandatory context class '{cls.value}' which is absent."
                )

        # Approval checks (not required for RC-1)
        if policy.approval_required:
            deny_reasons.extend(self._check_approval(ctx, policy))

        # Quorum check (RC-4)
        if policy.quorum_required:
            deny_reasons.extend(self._check_quorum(ctx))

        # Snapshot check (RC-4)
        if policy.snapshot_required and not ctx.snapshot_exists:
            deny_reasons.append(
                "D-006: RC-4 action requires a pre-execution snapshot record but none was recorded."
            )

        return EnforcementResult(
            denied=bool(deny_reasons),
            deny_reasons=deny_reasons,
            warnings=warnings,
            policy=policy,
        )

    # ------------------------------------------------------------------
    # Internal check helpers (each covers one deny-rule group)
    # ------------------------------------------------------------------

    def _check_approval(self, ctx: EnforcementContext, policy: PolicyEntry) -> list[str]:
        """Return deny reasons for approval-related rules (D-003 through D-005)."""
        reasons: list[str] = []
        rec = ctx.approval_record

        if rec is None:
            reasons.append(
                f"D-003-APPROVAL: action {ctx.action_class.value} requires an "
                f"approval record but none was provided."
            )
            return reasons

        if rec.is_expired:
            reasons.append("D-004: Approval record is expired — approval is no longer valid.")
        elif rec.action_class != ctx.action_class:
            reasons.append(
                f"D-005: Approval record covers action "
                f"'{rec.action_class.value}' but requested action "
                f"is '{ctx.action_class.value}' — scope mismatch."
            )
        elif (
            rec.scope_entity_ids
            and ctx.target_entity_ids
            and not all(eid in rec.scope_entity_ids for eid in ctx.target_entity_ids)
        ):
            out_of_scope = [
                str(eid) for eid in ctx.target_entity_ids if eid not in rec.scope_entity_ids
            ]
            reasons.append(
                f"D-005: Target entities {out_of_scope} are outside the approval record scope."
            )
        return reasons

    def _check_quorum(self, ctx: EnforcementContext) -> list[str]:
        """Return deny reasons for quorum rule D-008."""
        reasons: list[str] = []
        rec = ctx.approval_record
        if rec is None:
            reasons.append(
                f"D-008: action {ctx.action_class.value} requires quorum approval "
                f"but no approval record was provided."
            )
        elif rec.approver_count < _MIN_QUORUM_APPROVERS:
            reasons.append(
                f"D-008: Quorum not satisfied — found "
                f"{rec.approver_count} approver(s), "
                f"need >= {_MIN_QUORUM_APPROVERS}."
            )
        return reasons

    def get_risk_class(self, action_class: ActionClass) -> RiskClass:
        """Return the risk class for *action_class* without full enforcement."""
        return get_policy(action_class).risk_class

    def is_read_only(self, action_class: ActionClass) -> bool:
        """Return True if *action_class* is RC-1 (read-only)."""
        return get_policy(action_class).risk_class == RiskClass.RC1_READ_ONLY
