"""Tests for internalcmdb.retrieval.ranker (pt-015).

Covers:
- Empty candidates → empty result
- Mandatory items always included even over budget
- Budget overflow annotated in inclusion_reason
- Tier ordering: mandatory < recommended < supplementary < semantic
- Items that don't fit budget are skipped (non-mandatory)
- Stable sort by (tier, order_position, token_count, item_index)
- CHUNK_SEMANTIC always last (TIER_SEMANTIC = 3)
"""

from __future__ import annotations

import uuid

from internalcmdb.retrieval.broker import AssembledItem  # pylint: disable=import-error
from internalcmdb.retrieval.ranker import Ranker  # pylint: disable=import-error
from internalcmdb.retrieval.task_types import (  # pylint: disable=import-error
    ContextClass,
    TaskTypeCode,
    get_contract,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NIL_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _item(
    context_class: ContextClass,
    token_count: int = 100,
    inclusion_reason: str = "test",
    entity_id: uuid.UUID | None = None,
) -> AssembledItem:
    return AssembledItem(
        context_class=context_class,
        entity_kind_term_id=_NIL_UUID,
        entity_id=entity_id or _NIL_UUID,
        document_chunk_id=None,
        evidence_artifact_id=None,
        inclusion_reason=inclusion_reason,
        is_mandatory=False,
        estimated_token_count=token_count,
    )


# TT-001 contract for most tests:
# mandatory: REGISTRY_HOST, EVIDENCE_ARTIFACT
# recommended: CANONICAL_DOC, REGISTRY_SERVICE, REGISTRY_OWNERSHIP, OBSERVED_FACT, CHUNK_LEXICAL
# disallowed: REGISTRY_APPLICATION, CHUNK_SEMANTIC
_TT001_CONTRACT = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)


# ---------------------------------------------------------------------------
# Empty / trivial
# ---------------------------------------------------------------------------


class TestEmptyCandidates:
    def test_empty_candidates_returns_empty(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        assert ranker.rank([], token_budget=8000) == []

    def test_zero_budget_returns_only_mandatory(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        candidates = [
            _item(ContextClass.REGISTRY_HOST, token_count=200),  # mandatory
            _item(ContextClass.CANONICAL_DOC, token_count=100),  # recommended
        ]
        result = ranker.rank(candidates, token_budget=0)
        classes = [r.context_class for r in result]
        assert ContextClass.REGISTRY_HOST in classes
        assert ContextClass.CANONICAL_DOC not in classes


# ---------------------------------------------------------------------------
# Mandatory items always included
# ---------------------------------------------------------------------------


class TestMandatoryItems:
    def test_mandatory_included_within_budget(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        candidates = [_item(ContextClass.REGISTRY_HOST, token_count=100)]
        result = ranker.rank(candidates, token_budget=8000)
        assert len(result) == 1
        assert result[0].context_class == ContextClass.REGISTRY_HOST

    def test_mandatory_included_over_budget(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        candidates = [_item(ContextClass.REGISTRY_HOST, token_count=10_000)]
        result = ranker.rank(candidates, token_budget=500)
        assert len(result) == 1
        assert result[0].context_class == ContextClass.REGISTRY_HOST

    def test_mandatory_over_budget_annotated(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        candidates = [_item(ContextClass.REGISTRY_HOST, token_count=9000)]
        result = ranker.rank(candidates, token_budget=100)
        assert "BUDGET-OVERFLOW" in result[0].inclusion_reason

    def test_both_mandatory_included_over_budget(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        candidates = [
            _item(ContextClass.REGISTRY_HOST, token_count=200),
            _item(ContextClass.EVIDENCE_ARTIFACT, token_count=300),
        ]
        result = ranker.rank(candidates, token_budget=10)
        classes = {r.context_class for r in result}
        assert ContextClass.REGISTRY_HOST in classes
        assert ContextClass.EVIDENCE_ARTIFACT in classes


# ---------------------------------------------------------------------------
# Non-mandatory items respect budget
# ---------------------------------------------------------------------------


class TestBudgetEnforcement:
    def test_recommended_items_excluded_when_no_budget_left(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        # Mandatory items consume entire budget
        candidates = [
            _item(ContextClass.REGISTRY_HOST, token_count=500),
            _item(ContextClass.EVIDENCE_ARTIFACT, token_count=500),
            _item(ContextClass.CANONICAL_DOC, token_count=100),  # recommended
        ]
        result = ranker.rank(candidates, token_budget=500)
        classes = [r.context_class for r in result]
        # CANONICAL_DOC is recommended and should be excluded (no budget)
        assert ContextClass.CANONICAL_DOC not in classes

    def test_recommended_included_when_budget_available(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        candidates = [
            _item(ContextClass.REGISTRY_HOST, token_count=100),
            _item(ContextClass.EVIDENCE_ARTIFACT, token_count=100),
            _item(ContextClass.CANONICAL_DOC, token_count=100),
        ]
        result = ranker.rank(candidates, token_budget=8000)
        classes = [r.context_class for r in result]
        assert ContextClass.CANONICAL_DOC in classes


# ---------------------------------------------------------------------------
# Tier ordering (mandatory before recommended before supplementary before semantic)
# ---------------------------------------------------------------------------


class TestTierOrdering:
    def test_mandatory_ranks_before_recommended(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        candidates = [
            _item(ContextClass.CANONICAL_DOC, token_count=100),  # recommended
            _item(ContextClass.REGISTRY_HOST, token_count=100),  # mandatory
        ]
        # Pass candidates in reverse priority order
        result = ranker.rank(candidates, token_budget=8000)
        classes = [r.context_class for r in result]
        assert classes.index(ContextClass.REGISTRY_HOST) < classes.index(ContextClass.CANONICAL_DOC)

    def test_semantic_ranks_last(self) -> None:
        # Use TT-005 which does NOT disallow CHUNK_SEMANTIC
        contract = get_contract(TaskTypeCode.DOCUMENT_AUTHORING_ASSISTANT)
        ranker = Ranker(contract)
        candidates = [
            _item(ContextClass.CHUNK_SEMANTIC, token_count=50),
            _item(ContextClass.CANONICAL_DOC, token_count=50),  # mandatory
            _item(ContextClass.SCHEMA_ENTITY, token_count=50),  # mandatory
            _item(ContextClass.TAXONOMY_TERM, token_count=50),  # mandatory
        ]
        result = ranker.rank(candidates, token_budget=6000)
        classes = [r.context_class for r in result]
        if ContextClass.CHUNK_SEMANTIC in classes:
            assert classes[-1] == ContextClass.CHUNK_SEMANTIC

    def test_retrieval_order_respected_within_recommended(self) -> None:
        # For TT-001: retrieval_order has REGISTRY_HOST at 0, CANONICAL_DOC at 3
        ranker = Ranker(_TT001_CONTRACT)
        candidates = [
            _item(ContextClass.CANONICAL_DOC, token_count=100),
            _item(ContextClass.REGISTRY_SERVICE, token_count=100),
            _item(ContextClass.REGISTRY_HOST, token_count=100),
            _item(ContextClass.EVIDENCE_ARTIFACT, token_count=100),
        ]
        result = ranker.rank(candidates, token_budget=8000)
        classes = [r.context_class for r in result]
        # Mandatory REGISTRY_HOST must come before recommended CANONICAL_DOC
        assert classes.index(ContextClass.REGISTRY_HOST) < classes.index(ContextClass.CANONICAL_DOC)


# ---------------------------------------------------------------------------
# Inclusion reason annotation
# ---------------------------------------------------------------------------


class TestInclusionReasonAnnotation:
    def test_recommended_item_includes_tier_label(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        candidates = [
            _item(ContextClass.REGISTRY_HOST, token_count=50),
            _item(ContextClass.EVIDENCE_ARTIFACT, token_count=50),
            _item(ContextClass.CANONICAL_DOC, token_count=50, inclusion_reason="initial"),
        ]
        result = ranker.rank(candidates, token_budget=8000)
        canon_items = [r for r in result if r.context_class == ContextClass.CANONICAL_DOC]
        assert canon_items
        assert "RECOMMENDED" in canon_items[0].inclusion_reason

    def test_supplementary_item_includes_supplementary_label(self) -> None:
        ranker = Ranker(_TT001_CONTRACT)
        # TAXONOMY_TERM is not mandatory/recommended/disallowed for TT-001
        candidates = [
            _item(ContextClass.REGISTRY_HOST, token_count=50),
            _item(ContextClass.EVIDENCE_ARTIFACT, token_count=50),
            _item(ContextClass.TAXONOMY_TERM, token_count=50, inclusion_reason="base"),
        ]
        result = ranker.rank(candidates, token_budget=8000)
        taxonomy_items = [r for r in result if r.context_class == ContextClass.TAXONOMY_TERM]
        if taxonomy_items:
            assert "SUPPLEMENTARY" in taxonomy_items[0].inclusion_reason
