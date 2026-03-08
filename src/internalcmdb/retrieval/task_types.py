"""internalCMDB — Task Type Catalog (pt-013).

Defines the wave-1 supported task types and their evidence pack contracts
as Python dataclasses.  This module is the authoritative machine-readable
counterpart to ``docs/retrieval/task-type-catalog.md`` (GOV-006).

ADR-003 mandates deterministic-first retrieval ordering; the per-task
``retrieval_order`` tuple carries that mandate into the broker.

Usage::

    from internalcmdb.retrieval.task_types import TaskTypeCode, get_contract

    contract = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
    assert "registry_host" in contract.mandatory_classes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ContextClass(StrEnum):
    """Permitted context classes for wave-1 evidence packs."""

    CANONICAL_DOC = "canonical_doc"
    REGISTRY_HOST = "registry_host"
    REGISTRY_SERVICE = "registry_service"
    REGISTRY_APPLICATION = "registry_application"
    REGISTRY_OWNERSHIP = "registry_ownership"
    EVIDENCE_ARTIFACT = "evidence_artifact"
    OBSERVED_FACT = "observed_fact"
    TAXONOMY_TERM = "taxonomy_term"
    SCHEMA_ENTITY = "schema_entity"
    CHUNK_LEXICAL = "chunk_lexical"
    CHUNK_SEMANTIC = "chunk_semantic"


class TaskTypeCode(StrEnum):
    """Wave-1 task type identifiers (GOV-006)."""

    INFRASTRUCTURE_AUDIT = "TT-001"
    SERVICE_HEALTH_CHECK = "TT-002"
    REGISTRY_RECONCILIATION = "TT-003"
    DOCUMENT_VALIDATION = "TT-004"
    DOCUMENT_AUTHORING_ASSISTANT = "TT-005"
    INFRASTRUCTURE_CHANGE_PLANNING = "TT-006"
    POLICY_COMPLIANCE_CHECK = "TT-007"


class RiskClass(StrEnum):
    """Write-approval risk classes per ADR-004."""

    RC1_READ_ONLY = "RC-1"
    RC2_AGENT_DRAFT_HUMAN_APPROVE = "RC-2"
    RC3_SUPERVISED_WRITE = "RC-3"
    RC4_BULK_STRUCTURAL = "RC-4"


@dataclass(frozen=True)
class EvidenceContract:
    """Bounded evidence contract for one task type.

    Attributes:
        task_type_code:   Canonical task type identifier from GOV-006.
        description:      Human-readable summary of the task type.
        risk_class:       Write-approval risk class per ADR-004.
        token_budget:     Hard upper bound on total tokens in the packed context.
        mandatory_classes: Context classes that MUST be present before pack is
                          finalised; absence blocks execution.
        recommended_classes: Context classes that SHOULD be included; absence is
                            logged as a warning but does not block execution.
        disallowed_classes: Context classes that MUST NOT appear in the pack.
                           Broker must discard them during assembly.
        retrieval_order:  Ordered sequence of context classes to try first
                         (ADR-003 deterministic priority).
    """

    task_type_code: TaskTypeCode
    description: str
    risk_class: RiskClass
    token_budget: int
    mandatory_classes: frozenset[ContextClass]
    recommended_classes: frozenset[ContextClass]
    disallowed_classes: frozenset[ContextClass]
    retrieval_order: tuple[ContextClass, ...]

    def is_allowed(self, ctx: ContextClass) -> bool:
        """Return True if *ctx* is not explicitly disallowed."""
        return ctx not in self.disallowed_classes

    def is_mandatory(self, ctx: ContextClass) -> bool:
        return ctx in self.mandatory_classes

    def is_recommended(self, ctx: ContextClass) -> bool:
        return ctx in self.recommended_classes


# ---------------------------------------------------------------------------
# Wave-1 contract definitions
# ---------------------------------------------------------------------------

_CC = ContextClass  # local alias


_CONTRACTS: dict[TaskTypeCode, EvidenceContract] = {
    TaskTypeCode.INFRASTRUCTURE_AUDIT: EvidenceContract(
        task_type_code=TaskTypeCode.INFRASTRUCTURE_AUDIT,
        description=(
            "Read-only audit of a host or cluster — collect facts, compare to "
            "canonical state, produce reconciliation summary."
        ),
        risk_class=RiskClass.RC1_READ_ONLY,
        token_budget=8_000,
        mandatory_classes=frozenset({_CC.REGISTRY_HOST, _CC.EVIDENCE_ARTIFACT}),
        recommended_classes=frozenset(
            {
                _CC.CANONICAL_DOC,
                _CC.REGISTRY_SERVICE,
                _CC.REGISTRY_OWNERSHIP,
                _CC.OBSERVED_FACT,
                _CC.CHUNK_LEXICAL,
            }
        ),
        disallowed_classes=frozenset({_CC.REGISTRY_APPLICATION, _CC.CHUNK_SEMANTIC}),
        retrieval_order=(
            _CC.REGISTRY_HOST,
            _CC.EVIDENCE_ARTIFACT,
            _CC.REGISTRY_SERVICE,
            _CC.CANONICAL_DOC,
            _CC.CHUNK_LEXICAL,
        ),
    ),
    TaskTypeCode.SERVICE_HEALTH_CHECK: EvidenceContract(
        task_type_code=TaskTypeCode.SERVICE_HEALTH_CHECK,
        description=(
            "Verify current health status of a registered service against its "
            "canonical definition and observed state."
        ),
        risk_class=RiskClass.RC1_READ_ONLY,
        token_budget=4_000,
        mandatory_classes=frozenset(
            {_CC.REGISTRY_SERVICE, _CC.CANONICAL_DOC, _CC.EVIDENCE_ARTIFACT}
        ),
        recommended_classes=frozenset(
            {_CC.REGISTRY_HOST, _CC.REGISTRY_OWNERSHIP, _CC.CHUNK_LEXICAL}
        ),
        disallowed_classes=frozenset({_CC.CHUNK_SEMANTIC}),
        retrieval_order=(
            _CC.REGISTRY_SERVICE,
            _CC.CANONICAL_DOC,
            _CC.EVIDENCE_ARTIFACT,
            _CC.REGISTRY_HOST,
        ),
    ),
    TaskTypeCode.REGISTRY_RECONCILIATION: EvidenceContract(
        task_type_code=TaskTypeCode.REGISTRY_RECONCILIATION,
        description=(
            "Compare canonical registry state to observed discovery state and "
            "produce a structured diff with classification."
        ),
        risk_class=RiskClass.RC1_READ_ONLY,
        token_budget=12_000,
        mandatory_classes=frozenset(
            {
                _CC.REGISTRY_HOST,
                _CC.REGISTRY_SERVICE,
                _CC.EVIDENCE_ARTIFACT,
                _CC.OBSERVED_FACT,
            }
        ),
        recommended_classes=frozenset(
            {_CC.CANONICAL_DOC, _CC.REGISTRY_OWNERSHIP, _CC.TAXONOMY_TERM}
        ),
        disallowed_classes=frozenset({_CC.CHUNK_LEXICAL, _CC.CHUNK_SEMANTIC}),
        retrieval_order=(
            _CC.REGISTRY_HOST,
            _CC.REGISTRY_SERVICE,
            _CC.EVIDENCE_ARTIFACT,
            _CC.OBSERVED_FACT,
            _CC.CANONICAL_DOC,
        ),
    ),
    TaskTypeCode.DOCUMENT_VALIDATION: EvidenceContract(
        task_type_code=TaskTypeCode.DOCUMENT_VALIDATION,
        description=(
            "Validate a governance or infrastructure document against the "
            "metadata schema and taxonomy rules."
        ),
        risk_class=RiskClass.RC1_READ_ONLY,
        token_budget=2_000,
        mandatory_classes=frozenset({_CC.CANONICAL_DOC, _CC.SCHEMA_ENTITY, _CC.TAXONOMY_TERM}),
        recommended_classes=frozenset(),
        disallowed_classes=frozenset(
            {
                _CC.REGISTRY_HOST,
                _CC.REGISTRY_SERVICE,
                _CC.CHUNK_LEXICAL,
                _CC.CHUNK_SEMANTIC,
            }
        ),
        retrieval_order=(
            _CC.CANONICAL_DOC,
            _CC.SCHEMA_ENTITY,
            _CC.TAXONOMY_TERM,
        ),
    ),
    TaskTypeCode.DOCUMENT_AUTHORING_ASSISTANT: EvidenceContract(
        task_type_code=TaskTypeCode.DOCUMENT_AUTHORING_ASSISTANT,
        description=(
            "Assist a human author in drafting a new wave-1 governance or "
            "infrastructure document.  Agent provides structure and validates "
            "against schema — no autonomous write."
        ),
        risk_class=RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE,
        token_budget=6_000,
        mandatory_classes=frozenset({_CC.CANONICAL_DOC, _CC.SCHEMA_ENTITY, _CC.TAXONOMY_TERM}),
        recommended_classes=frozenset(
            {
                _CC.REGISTRY_SERVICE,
                _CC.REGISTRY_HOST,
                _CC.CHUNK_LEXICAL,
                _CC.CHUNK_SEMANTIC,
            }
        ),
        disallowed_classes=frozenset(),
        retrieval_order=(
            _CC.CANONICAL_DOC,
            _CC.SCHEMA_ENTITY,
            _CC.TAXONOMY_TERM,
            _CC.REGISTRY_SERVICE,
            _CC.REGISTRY_HOST,
            _CC.CHUNK_LEXICAL,
            _CC.CHUNK_SEMANTIC,
        ),
    ),
    TaskTypeCode.INFRASTRUCTURE_CHANGE_PLANNING: EvidenceContract(
        task_type_code=TaskTypeCode.INFRASTRUCTURE_CHANGE_PLANNING,
        description=(
            "Prepare a bounded change plan for a host, service, or cluster "
            "configuration change.  Agent produces draft plan — no execution."
        ),
        risk_class=RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE,
        token_budget=10_000,
        mandatory_classes=frozenset(
            {
                _CC.REGISTRY_HOST,
                _CC.REGISTRY_SERVICE,
                _CC.CANONICAL_DOC,
                _CC.EVIDENCE_ARTIFACT,
                _CC.REGISTRY_OWNERSHIP,
            }
        ),
        recommended_classes=frozenset({_CC.OBSERVED_FACT, _CC.CHUNK_LEXICAL}),
        disallowed_classes=frozenset({_CC.CHUNK_SEMANTIC}),
        retrieval_order=(
            _CC.REGISTRY_HOST,
            _CC.REGISTRY_SERVICE,
            _CC.EVIDENCE_ARTIFACT,
            _CC.CANONICAL_DOC,
            _CC.REGISTRY_OWNERSHIP,
        ),
    ),
    TaskTypeCode.POLICY_COMPLIANCE_CHECK: EvidenceContract(
        task_type_code=TaskTypeCode.POLICY_COMPLIANCE_CHECK,
        description=(
            "Evaluate whether a system, service, or configuration complies "
            "with applicable policy packs."
        ),
        risk_class=RiskClass.RC1_READ_ONLY,
        token_budget=6_000,
        mandatory_classes=frozenset({_CC.CANONICAL_DOC}),
        recommended_classes=frozenset(
            {
                _CC.REGISTRY_HOST,
                _CC.REGISTRY_SERVICE,
                _CC.EVIDENCE_ARTIFACT,
                _CC.REGISTRY_OWNERSHIP,
                _CC.CHUNK_LEXICAL,
            }
        ),
        disallowed_classes=frozenset({_CC.CHUNK_SEMANTIC}),
        retrieval_order=(
            _CC.CANONICAL_DOC,
            _CC.REGISTRY_HOST,
            _CC.REGISTRY_SERVICE,
            _CC.EVIDENCE_ARTIFACT,
        ),
    ),
}


def get_contract(task_type: TaskTypeCode) -> EvidenceContract:
    """Return the evidence contract for the given task type.

    Raises:
        KeyError: if *task_type* is not a known wave-1 task type.  This should
                  never happen with a valid ``TaskTypeCode`` enum member, but
                  the explicit error makes the failure surface early.
    """
    try:
        return _CONTRACTS[task_type]
    except KeyError:
        known = ", ".join(t.value for t in TaskTypeCode)
        raise KeyError(
            f"No evidence contract defined for task type {task_type!r}. Known wave-1 types: {known}"
        ) from None


def all_contracts() -> list[EvidenceContract]:
    """Return all wave-1 evidence contracts in TaskTypeCode order."""
    return [_CONTRACTS[tt] for tt in TaskTypeCode]


# ---------------------------------------------------------------------------
# Validation helpers used by the broker and tests
# ---------------------------------------------------------------------------


@dataclass
class ContractViolation:
    """Describes a single contract enforcement violation."""

    code: str
    message: str
    context_class: ContextClass | None = field(default=None)


def check_mandatory_satisfied(
    contract: EvidenceContract,
    present_classes: frozenset[ContextClass],
) -> list[ContractViolation]:
    """Return violations for any mandatory context class that is absent."""
    violations: list[ContractViolation] = []
    for cls in contract.mandatory_classes:
        if cls not in present_classes:
            violations.append(
                ContractViolation(
                    code="MANDATORY_MISSING",
                    message=(
                        f"Mandatory context class '{cls.value}' is absent from "
                        f"the evidence pack for task type "
                        f"'{contract.task_type_code.value}'."
                    ),
                    context_class=cls,
                )
            )
    return violations


def check_disallowed_absent(
    contract: EvidenceContract,
    present_classes: frozenset[ContextClass],
) -> list[ContractViolation]:
    """Return violations for any disallowed context class that is present."""
    violations: list[ContractViolation] = []
    for cls in contract.disallowed_classes:
        if cls in present_classes:
            violations.append(
                ContractViolation(
                    code="DISALLOWED_PRESENT",
                    message=(
                        f"Disallowed context class '{cls.value}' is present in "
                        f"the evidence pack for task type "
                        f"'{contract.task_type_code.value}'."
                    ),
                    context_class=cls,
                )
            )
    return violations


def validate_pack_classes(
    contract: EvidenceContract,
    present_classes: frozenset[ContextClass],
) -> list[ContractViolation]:
    """Run all contract validations and return combined violations list."""
    return check_mandatory_satisfied(contract, present_classes) + check_disallowed_absent(
        contract, present_classes
    )
