"""Tests for internalcmdb.control.policy_matrix (pt-016).

Covers:
- PolicyEnforcer.check: RC-1 read-only pass (no approval required)
- PolicyEnforcer.check: RC-3 deny D-003 (no approval record)
- PolicyEnforcer.check: RC-3 deny D-004 (expired approval)
- PolicyEnforcer.check: RC-3 deny D-005 (scope mismatch — wrong action class)
- PolicyEnforcer.check: RC-3 deny D-005 (out-of-scope entity IDs)
- PolicyEnforcer.check: RC-4 deny D-008 (quorum insufficient)
- PolicyEnforcer.check: RC-4 deny D-006 (no snapshot)
- PolicyEnforcer.check: mandatory evidence missing (POLICY_EVIDENCE_MISSING)
- PolicyEnforcer.check: D-002/D-003 contract violations (evidence pack)
- PolicyEnforcer.check_quorum: public delegator works correctly
- PolicyEnforcer.get_risk_class: returns correct RiskClass per ActionClass
- PolicyEnforcer.is_read_only: True for RC-1, False for others
- get_policy: raises KeyError for unknown class
- ApprovalRecord.approver_count property
"""

from __future__ import annotations

import uuid

import pytest

from internalcmdb.control.policy_matrix import (  # pylint: disable=import-error
    ActionClass,
    ApprovalRecord,
    EnforcementContext,
    PolicyEnforcer,
    get_policy,
)
from internalcmdb.retrieval.task_types import (  # pylint: disable=import-error
    ContextClass,
    RiskClass,
    TaskTypeCode,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _approval(
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


def _ctx(
    action_class: ActionClass = ActionClass.REGISTRY_ENTITY_CREATE,
    task_type: TaskTypeCode = TaskTypeCode.REGISTRY_RECONCILIATION,
    evidence: frozenset[ContextClass] | None = None,
    approval: ApprovalRecord | None = None,
    target_ids: list[uuid.UUID] | None = None,
    snapshot_exists: bool = False,
) -> EnforcementContext:
    # Default: provide sufficient evidence for TT-003 contract validation
    default_evidence = frozenset(
        {
            ContextClass.REGISTRY_HOST,
            ContextClass.REGISTRY_SERVICE,
            ContextClass.EVIDENCE_ARTIFACT,
            ContextClass.OBSERVED_FACT,
            ContextClass.REGISTRY_OWNERSHIP,  # mandatory for AC-003 policy
        }
    )
    return EnforcementContext(
        action_class=action_class,
        task_type_code=task_type,
        present_evidence_classes=evidence if evidence is not None else default_evidence,
        target_entity_ids=target_ids or [],
        approval_record=approval,
        snapshot_exists=snapshot_exists,
    )


_ENFORCER = PolicyEnforcer()


# ---------------------------------------------------------------------------
# RC-1 read-only — no approval required
# ---------------------------------------------------------------------------


class TestReadOnlyActions:
    def test_rc1_registry_read_no_approval_passes(self) -> None:
        ctx = _ctx(
            action_class=ActionClass.REGISTRY_READ,
            task_type=TaskTypeCode.INFRASTRUCTURE_AUDIT,
            evidence=frozenset({ContextClass.REGISTRY_HOST, ContextClass.EVIDENCE_ARTIFACT}),
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is False

    def test_rc1_document_validation_no_approval_passes(self) -> None:
        ctx = _ctx(
            action_class=ActionClass.DOCUMENT_VALIDATION_RUN,
            task_type=TaskTypeCode.DOCUMENT_VALIDATION,
            evidence=frozenset(
                {
                    ContextClass.CANONICAL_DOC,
                    ContextClass.SCHEMA_ENTITY,
                    ContextClass.TAXONOMY_TERM,
                }
            ),
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is False


# ---------------------------------------------------------------------------
# D-003: No approval record
# ---------------------------------------------------------------------------


class TestD003NoApproval:
    @pytest.mark.parametrize(
        "action_class",
        [
            ActionClass.REGISTRY_ENTITY_CREATE,
            ActionClass.REGISTRY_ENTITY_UPDATE,
            ActionClass.DISCOVERY_RUN,
            ActionClass.DOCUMENT_CREATE,
            ActionClass.DOCUMENT_UPDATE,
        ],
    )
    def test_approval_required_actions_denied_without_approval(
        self, action_class: ActionClass
    ) -> None:
        ctx = _ctx(action_class=action_class, approval=None)
        result = _ENFORCER.check(ctx)
        assert result.denied is True
        assert any("D-003" in r for r in result.deny_reasons)

    def test_deny_reasons_non_empty(self) -> None:
        ctx = _ctx(action_class=ActionClass.REGISTRY_ENTITY_CREATE, approval=None)
        result = _ENFORCER.check(ctx)
        assert result.deny_reasons


# ---------------------------------------------------------------------------
# D-004: Expired approval
# ---------------------------------------------------------------------------


class TestD004ExpiredApproval:
    def test_expired_approval_denied(self) -> None:
        rec = _approval(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            is_expired=True,
        )
        ctx = _ctx(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            approval=rec,
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is True
        assert any("D-004" in r for r in result.deny_reasons)


# ---------------------------------------------------------------------------
# D-005: Scope mismatch
# ---------------------------------------------------------------------------


class TestD005ScopeMismatch:
    def test_wrong_action_class_in_approval(self) -> None:
        rec = _approval(
            action_class=ActionClass.DOCUMENT_CREATE,  # wrong class
            is_expired=False,
        )
        ctx = _ctx(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            approval=rec,
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is True
        assert any("D-005" in r for r in result.deny_reasons)

    def test_out_of_scope_entity_ids(self) -> None:
        eid_in_scope = uuid.uuid4()
        eid_out_of_scope = uuid.uuid4()
        rec = _approval(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            scope_entity_ids=frozenset({eid_in_scope}),
        )
        ctx = _ctx(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            approval=rec,
            target_ids=[eid_in_scope, eid_out_of_scope],
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is True
        assert any("D-005" in r for r in result.deny_reasons)

    def test_empty_scope_covers_all_entities(self) -> None:
        # When scope_entity_ids is empty, any target IDs are covered
        eid = uuid.uuid4()
        rec = _approval(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            scope_entity_ids=frozenset(),  # empty = covers all
        )
        ctx = _ctx(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            approval=rec,
            target_ids=[eid],
        )
        result = _ENFORCER.check(ctx)
        # Should not have D-005 denial (scope is empty = open)
        assert not any("D-005" in r for r in result.deny_reasons)


# ---------------------------------------------------------------------------
# D-006: Missing snapshot for RC-4
# ---------------------------------------------------------------------------


class TestD006Snapshot:
    def test_schema_migration_requires_snapshot(self) -> None:
        rec = _approval(
            action_class=ActionClass.SCHEMA_MIGRATION,
            approver_codes=frozenset({"approver-a", "approver-b"}),
        )
        ctx = EnforcementContext(
            action_class=ActionClass.SCHEMA_MIGRATION,
            task_type_code=TaskTypeCode.REGISTRY_RECONCILIATION,
            present_evidence_classes=frozenset(
                {
                    ContextClass.SCHEMA_ENTITY,
                    ContextClass.CANONICAL_DOC,
                    ContextClass.REGISTRY_HOST,
                    ContextClass.REGISTRY_SERVICE,
                    ContextClass.EVIDENCE_ARTIFACT,
                    ContextClass.OBSERVED_FACT,
                }
            ),
            approval_record=rec,
            snapshot_exists=False,
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is True
        assert any("D-006" in r for r in result.deny_reasons)

    def test_schema_migration_with_snapshot_and_quorum_passes(self) -> None:
        rec = _approval(
            action_class=ActionClass.SCHEMA_MIGRATION,
            approver_codes=frozenset({"approver-a", "approver-b"}),
        )
        ctx = EnforcementContext(
            action_class=ActionClass.SCHEMA_MIGRATION,
            task_type_code=TaskTypeCode.REGISTRY_RECONCILIATION,
            present_evidence_classes=frozenset(
                {
                    ContextClass.SCHEMA_ENTITY,
                    ContextClass.CANONICAL_DOC,
                    ContextClass.REGISTRY_HOST,
                    ContextClass.REGISTRY_SERVICE,
                    ContextClass.EVIDENCE_ARTIFACT,
                    ContextClass.OBSERVED_FACT,
                }
            ),
            approval_record=rec,
            snapshot_exists=True,
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is False


# ---------------------------------------------------------------------------
# D-008: Quorum
# ---------------------------------------------------------------------------


class TestD008Quorum:
    def test_single_approver_fails_quorum(self) -> None:
        rec = _approval(
            action_class=ActionClass.BULK_REGISTRY_IMPORT,
            approver_codes=frozenset({"approver-1"}),  # only 1 approver
        )
        ctx = EnforcementContext(
            action_class=ActionClass.BULK_REGISTRY_IMPORT,
            task_type_code=TaskTypeCode.REGISTRY_RECONCILIATION,
            present_evidence_classes=frozenset(
                {
                    ContextClass.REGISTRY_OWNERSHIP,
                    ContextClass.EVIDENCE_ARTIFACT,
                    ContextClass.REGISTRY_HOST,
                    ContextClass.REGISTRY_SERVICE,
                    ContextClass.OBSERVED_FACT,
                }
            ),
            approval_record=rec,
            snapshot_exists=True,
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is True
        assert any("D-008" in r for r in result.deny_reasons)

    def test_two_approvers_satisfies_quorum(self) -> None:
        rec = _approval(
            action_class=ActionClass.BULK_REGISTRY_IMPORT,
            approver_codes=frozenset({"approver-1", "approver-2"}),
        )
        ctx = EnforcementContext(
            action_class=ActionClass.BULK_REGISTRY_IMPORT,
            task_type_code=TaskTypeCode.REGISTRY_RECONCILIATION,
            present_evidence_classes=frozenset(
                {
                    ContextClass.REGISTRY_OWNERSHIP,
                    ContextClass.EVIDENCE_ARTIFACT,
                    ContextClass.REGISTRY_HOST,
                    ContextClass.REGISTRY_SERVICE,
                    ContextClass.OBSERVED_FACT,
                }
            ),
            approval_record=rec,
            snapshot_exists=True,
        )
        result = _ENFORCER.check(ctx)
        assert not any("D-008" in r for r in result.deny_reasons)

    def test_no_approval_for_quorum_action_fails(self) -> None:
        ctx = EnforcementContext(
            action_class=ActionClass.SCHEMA_MIGRATION,
            task_type_code=TaskTypeCode.REGISTRY_RECONCILIATION,
            present_evidence_classes=frozenset(
                {
                    ContextClass.SCHEMA_ENTITY,
                    ContextClass.CANONICAL_DOC,
                }
            ),
            approval_record=None,
            snapshot_exists=True,
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is True
        assert any("D-008" in r or "D-003" in r for r in result.deny_reasons)


# ---------------------------------------------------------------------------
# POLICY_EVIDENCE_MISSING
# ---------------------------------------------------------------------------


class TestPolicyEvidenceMissing:
    def test_registry_create_requires_registry_ownership(self) -> None:
        rec = _approval(action_class=ActionClass.REGISTRY_ENTITY_CREATE)
        ctx = EnforcementContext(
            action_class=ActionClass.REGISTRY_ENTITY_CREATE,
            task_type_code=TaskTypeCode.REGISTRY_RECONCILIATION,
            present_evidence_classes=frozenset(
                {
                    ContextClass.REGISTRY_HOST,
                    ContextClass.REGISTRY_SERVICE,
                    ContextClass.EVIDENCE_ARTIFACT,
                    ContextClass.OBSERVED_FACT,
                    # REGISTRY_OWNERSHIP intentionally absent
                }
            ),
            approval_record=rec,
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is True
        assert any("POLICY_EVIDENCE_MISSING" in r for r in result.deny_reasons)


# ---------------------------------------------------------------------------
# Evidence contract violations (D-002 / D-003)
# ---------------------------------------------------------------------------


class TestContractViolations:
    def test_mandatory_evidence_class_absent_denies(self) -> None:
        ctx = _ctx(
            action_class=ActionClass.REGISTRY_READ,
            task_type=TaskTypeCode.INFRASTRUCTURE_AUDIT,
            evidence=frozenset(),  # missing REGISTRY_HOST + EVIDENCE_ARTIFACT
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is True

    def test_disallowed_evidence_class_present_denies(self) -> None:
        ctx = _ctx(
            action_class=ActionClass.REGISTRY_READ,
            task_type=TaskTypeCode.INFRASTRUCTURE_AUDIT,
            evidence=frozenset(
                {
                    ContextClass.REGISTRY_HOST,
                    ContextClass.EVIDENCE_ARTIFACT,
                    ContextClass.CHUNK_SEMANTIC,  # disallowed for TT-001
                }
            ),
        )
        result = _ENFORCER.check(ctx)
        assert result.denied is True


# ---------------------------------------------------------------------------
# check_quorum — public API
# ---------------------------------------------------------------------------


class TestCheckQuorum:
    def test_no_approval_record_quorum_fails(self) -> None:
        ctx = _ctx(action_class=ActionClass.SCHEMA_MIGRATION, approval=None)
        reasons = _ENFORCER.check_quorum(ctx)
        assert len(reasons) > 0
        assert any("D-008" in r for r in reasons)

    def test_single_approver_quorum_fails(self) -> None:
        rec = _approval(approver_codes=frozenset({"one"}))
        ctx = _ctx(action_class=ActionClass.SCHEMA_MIGRATION, approval=rec)
        reasons = _ENFORCER.check_quorum(ctx)
        assert any("D-008" in r for r in reasons)

    def test_two_approvers_quorum_passes(self) -> None:
        rec = _approval(approver_codes=frozenset({"one", "two"}))
        ctx = _ctx(action_class=ActionClass.SCHEMA_MIGRATION, approval=rec)
        reasons = _ENFORCER.check_quorum(ctx)
        assert reasons == []


# ---------------------------------------------------------------------------
# get_risk_class
# ---------------------------------------------------------------------------


class TestGetRiskClass:
    @pytest.mark.parametrize(
        ("action_class", "expected_risk"),
        [
            (ActionClass.REGISTRY_READ, RiskClass.RC1_READ_ONLY),
            (ActionClass.DOCUMENT_VALIDATION_RUN, RiskClass.RC1_READ_ONLY),
            (ActionClass.DISCOVERY_RUN, RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE),
            (ActionClass.DOCUMENT_CREATE, RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE),
            (ActionClass.DOCUMENT_UPDATE, RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE),
            (ActionClass.AGENT_RUN_TRIGGER, RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE),
            (ActionClass.REGISTRY_ENTITY_CREATE, RiskClass.RC3_SUPERVISED_WRITE),
            (ActionClass.REGISTRY_ENTITY_UPDATE, RiskClass.RC3_SUPERVISED_WRITE),
            (ActionClass.SCHEMA_MIGRATION, RiskClass.RC4_BULK_STRUCTURAL),
            (ActionClass.BULK_REGISTRY_IMPORT, RiskClass.RC4_BULK_STRUCTURAL),
        ],
    )
    def test_risk_class_mapping(self, action_class: ActionClass, expected_risk: RiskClass) -> None:
        assert _ENFORCER.get_risk_class(action_class) == expected_risk


# ---------------------------------------------------------------------------
# is_read_only
# ---------------------------------------------------------------------------


class TestIsReadOnly:
    def test_registry_read_is_read_only(self) -> None:
        assert _ENFORCER.is_read_only(ActionClass.REGISTRY_READ) is True

    def test_document_validation_run_is_read_only(self) -> None:
        assert _ENFORCER.is_read_only(ActionClass.DOCUMENT_VALIDATION_RUN) is True

    @pytest.mark.parametrize(
        "action_class",
        [
            ActionClass.REGISTRY_ENTITY_CREATE,
            ActionClass.REGISTRY_ENTITY_UPDATE,
            ActionClass.SCHEMA_MIGRATION,
            ActionClass.BULK_REGISTRY_IMPORT,
            ActionClass.DISCOVERY_RUN,
        ],
    )
    def test_write_actions_not_read_only(self, action_class: ActionClass) -> None:
        assert _ENFORCER.is_read_only(action_class) is False


# ---------------------------------------------------------------------------
# get_policy
# ---------------------------------------------------------------------------


class TestGetPolicy:
    @pytest.mark.parametrize("ac", list(ActionClass))
    def test_all_10_action_classes_have_policy(self, ac: ActionClass) -> None:
        policy = get_policy(ac)
        assert policy.action_class == ac

    def test_unknown_class_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="No policy entry"):
            get_policy("AC-999")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ApprovalRecord.approver_count
# ---------------------------------------------------------------------------


class TestApprovalRecordApproverCount:
    def test_single_approver(self) -> None:
        rec = _approval(approver_codes=frozenset({"alice"}))
        assert rec.approver_count == 1

    def test_two_approvers(self) -> None:
        rec = _approval(approver_codes=frozenset({"alice", "bob"}))
        assert rec.approver_count == 2

    def test_zero_approvers(self) -> None:
        rec = _approval(approver_codes=frozenset())
        assert rec.approver_count == 0
