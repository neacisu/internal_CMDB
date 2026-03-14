"""Tests for internalcmdb.retrieval.task_types (pt-013).

Covers:
- All 7 wave-1 task type contracts are retrievable and well-formed
- get_contract raises KeyError for unknown codes
- EvidenceContract.is_allowed / is_mandatory / is_recommended
- validate_pack_classes: MANDATORY_MISSING violations
- validate_pack_classes: DISALLOWED_PRESENT violations
- validate_pack_classes: clean pack → empty violations
- all_contracts() returns all 7
"""

from __future__ import annotations

import pytest

from internalcmdb.retrieval.task_types import (  # pylint: disable=import-error
    ContextClass,
    ContractViolation,
    RiskClass,
    TaskTypeCode,
    all_contracts,
    check_disallowed_absent,
    check_mandatory_satisfied,
    get_contract,
    validate_pack_classes,
)

# ---------------------------------------------------------------------------
# get_contract / all_contracts
# ---------------------------------------------------------------------------


class TestGetContract:
    @pytest.mark.parametrize("tt", list(TaskTypeCode))
    def test_all_7_contracts_present(self, tt: TaskTypeCode) -> None:
        contract = get_contract(tt)
        assert contract.task_type_code == tt

    def test_unknown_code_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="No evidence contract"):
            get_contract("TT-999")  # type: ignore[arg-type]

    def test_all_contracts_returns_7(self) -> None:
        assert len(all_contracts()) == 7

    def test_all_contracts_ordered_by_task_type(self) -> None:
        contracts = all_contracts()
        codes = [c.task_type_code for c in contracts]
        assert codes == list(TaskTypeCode)


# ---------------------------------------------------------------------------
# Contract shape invariants
# ---------------------------------------------------------------------------


class TestContractInvariants:
    @pytest.mark.parametrize("tt", list(TaskTypeCode))
    def test_description_non_empty(self, tt: TaskTypeCode) -> None:
        assert len(get_contract(tt).description) > 10

    @pytest.mark.parametrize("tt", list(TaskTypeCode))
    def test_token_budget_positive(self, tt: TaskTypeCode) -> None:
        assert get_contract(tt).token_budget > 0

    @pytest.mark.parametrize("tt", list(TaskTypeCode))
    def test_retrieval_order_non_empty(self, tt: TaskTypeCode) -> None:
        assert len(get_contract(tt).retrieval_order) >= 1

    @pytest.mark.parametrize("tt", list(TaskTypeCode))
    def test_no_overlap_mandatory_disallowed(self, tt: TaskTypeCode) -> None:
        c = get_contract(tt)
        assert c.mandatory_classes.isdisjoint(c.disallowed_classes), (
            f"{tt}: mandatory and disallowed sets overlap"
        )

    @pytest.mark.parametrize("tt", list(TaskTypeCode))
    def test_contract_frozen(self, tt: TaskTypeCode) -> None:
        c = get_contract(tt)
        with pytest.raises((AttributeError, TypeError)):
            c.token_budget = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Risk class assignments
# ---------------------------------------------------------------------------


class TestRiskClasses:
    def test_tt001_is_rc1(self) -> None:
        assert get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT).risk_class == RiskClass.RC1_READ_ONLY

    def test_tt002_is_rc1(self) -> None:
        assert get_contract(TaskTypeCode.SERVICE_HEALTH_CHECK).risk_class == RiskClass.RC1_READ_ONLY

    def test_tt003_is_rc1(self) -> None:
        assert (
            get_contract(TaskTypeCode.REGISTRY_RECONCILIATION).risk_class == RiskClass.RC1_READ_ONLY
        )

    def test_tt004_is_rc1(self) -> None:
        assert get_contract(TaskTypeCode.DOCUMENT_VALIDATION).risk_class == RiskClass.RC1_READ_ONLY

    def test_tt005_is_rc2(self) -> None:
        assert (
            get_contract(TaskTypeCode.DOCUMENT_AUTHORING_ASSISTANT).risk_class
            == RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE
        )

    def test_tt006_is_rc2(self) -> None:
        assert (
            get_contract(TaskTypeCode.INFRASTRUCTURE_CHANGE_PLANNING).risk_class
            == RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE
        )

    def test_tt007_is_rc1(self) -> None:
        assert (
            get_contract(TaskTypeCode.POLICY_COMPLIANCE_CHECK).risk_class == RiskClass.RC1_READ_ONLY
        )


# ---------------------------------------------------------------------------
# EvidenceContract helper methods
# ---------------------------------------------------------------------------


class TestEvidenceContractMethods:
    def test_is_mandatory_true(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        assert c.is_mandatory(ContextClass.REGISTRY_HOST)

    def test_is_mandatory_false(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        assert not c.is_mandatory(ContextClass.TAXONOMY_TERM)

    def test_is_allowed_returns_false_for_disallowed(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        # CHUNK_SEMANTIC is disallowed for TT-001
        assert not c.is_allowed(ContextClass.CHUNK_SEMANTIC)

    def test_is_allowed_returns_true_for_neutral(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        assert c.is_allowed(ContextClass.REGISTRY_HOST)

    def test_is_recommended(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        assert c.is_recommended(ContextClass.CANONICAL_DOC)

    def test_is_recommended_false_for_mandatory(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        assert not c.is_recommended(ContextClass.REGISTRY_HOST)


# ---------------------------------------------------------------------------
# check_mandatory_satisfied
# ---------------------------------------------------------------------------


class TestCheckMandatorySatisfied:
    def test_all_mandatory_present_gives_no_violations(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        present = frozenset({ContextClass.REGISTRY_HOST, ContextClass.EVIDENCE_ARTIFACT})
        violations = check_mandatory_satisfied(c, present)
        assert violations == []

    def test_missing_mandatory_gives_violation(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        # Only one of two mandatory classes present
        present = frozenset({ContextClass.REGISTRY_HOST})
        violations = check_mandatory_satisfied(c, present)
        assert len(violations) == 1
        assert violations[0].code == "MANDATORY_MISSING"
        assert violations[0].context_class == ContextClass.EVIDENCE_ARTIFACT

    def test_all_mandatory_missing_gives_all_violations(self) -> None:
        c = get_contract(TaskTypeCode.SERVICE_HEALTH_CHECK)
        # TT-002 requires: REGISTRY_SERVICE, CANONICAL_DOC, EVIDENCE_ARTIFACT
        violations = check_mandatory_satisfied(c, frozenset())
        assert len(violations) == 3

    def test_violation_message_contains_class_and_task(self) -> None:
        c = get_contract(TaskTypeCode.DOCUMENT_VALIDATION)
        present = frozenset({ContextClass.CANONICAL_DOC})  # missing SCHEMA_ENTITY, TAXONOMY_TERM
        violations = check_mandatory_satisfied(c, present)
        for v in violations:
            assert "TT-004" in v.message


# ---------------------------------------------------------------------------
# check_disallowed_absent
# ---------------------------------------------------------------------------


class TestCheckDisallowedAbsent:
    def test_no_disallowed_present_gives_no_violations(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        # Provide only allowed classes
        present = frozenset({ContextClass.REGISTRY_HOST, ContextClass.EVIDENCE_ARTIFACT})
        violations = check_disallowed_absent(c, present)
        assert violations == []

    def test_disallowed_class_present_gives_violation(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        present = frozenset(
            {
                ContextClass.REGISTRY_HOST,
                ContextClass.EVIDENCE_ARTIFACT,
                ContextClass.CHUNK_SEMANTIC,  # disallowed
            }
        )
        violations = check_disallowed_absent(c, present)
        assert len(violations) == 1
        assert violations[0].code == "DISALLOWED_PRESENT"
        assert violations[0].context_class == ContextClass.CHUNK_SEMANTIC

    def test_tt003_disallowed_classes(self) -> None:
        c = get_contract(TaskTypeCode.REGISTRY_RECONCILIATION)
        present = frozenset(
            {
                ContextClass.REGISTRY_HOST,
                ContextClass.REGISTRY_SERVICE,
                ContextClass.EVIDENCE_ARTIFACT,
                ContextClass.OBSERVED_FACT,
                ContextClass.CHUNK_LEXICAL,  # disallowed in TT-003
            }
        )
        violations = check_disallowed_absent(c, present)
        assert any(v.context_class == ContextClass.CHUNK_LEXICAL for v in violations)


# ---------------------------------------------------------------------------
# validate_pack_classes (combines both checks)
# ---------------------------------------------------------------------------


class TestValidatePackClasses:
    def test_empty_pack_tt001_gives_mandatory_violations(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        violations = validate_pack_classes(c, frozenset())
        codes = [v.code for v in violations]
        assert "MANDATORY_MISSING" in codes

    def test_compliant_tt001_pack_no_violations(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        present = frozenset({ContextClass.REGISTRY_HOST, ContextClass.EVIDENCE_ARTIFACT})
        violations = validate_pack_classes(c, present)
        assert violations == []

    def test_simultaneous_mandatory_missing_and_disallowed_present(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        present = frozenset(
            {
                ContextClass.REGISTRY_HOST,  # only one of mandatory two
                ContextClass.CHUNK_SEMANTIC,  # disallowed
            }
        )
        violations = validate_pack_classes(c, present)
        codes = [v.code for v in violations]
        assert "MANDATORY_MISSING" in codes
        assert "DISALLOWED_PRESENT" in codes

    def test_tt004_complete_compliant_pack(self) -> None:
        c = get_contract(TaskTypeCode.DOCUMENT_VALIDATION)
        present = frozenset(
            {
                ContextClass.CANONICAL_DOC,
                ContextClass.SCHEMA_ENTITY,
                ContextClass.TAXONOMY_TERM,
            }
        )
        assert validate_pack_classes(c, present) == []

    def test_violation_has_all_fields(self) -> None:
        c = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        violations = validate_pack_classes(c, frozenset())
        for v in violations:
            assert isinstance(v, ContractViolation)
            assert v.code
            assert v.message
