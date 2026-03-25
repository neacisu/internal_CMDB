"""Tests for internalcmdb.retrieval.broker — dataclasses, pure helpers, and mocked assemble."""
# Whitebox unit tests deliberately call private stage methods on RetrievalBroker.
# pylint: disable=protected-access

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

from internalcmdb.retrieval.broker import (
    _UNKNOWN_KIND_TERM_ID,
    AssembledItem,
    BrokerResult,
    RetrievalBroker,
    RetrievalRequest,
    _estimate_token_count,
)
from internalcmdb.retrieval.task_types import (
    ContextClass,
    ContractViolation,
    TaskTypeCode,
    get_contract,
)

# ---------------------------------------------------------------------------
# _estimate_token_count
# ---------------------------------------------------------------------------


class TestEstimateTokenCount:
    def test_empty_string_returns_one(self) -> None:
        assert _estimate_token_count("") == 1

    def test_single_char_returns_one(self) -> None:
        assert _estimate_token_count("a") == 1

    def test_four_chars_returns_one(self) -> None:
        assert _estimate_token_count("abcd") == 1

    def test_eight_chars_returns_two(self) -> None:
        assert _estimate_token_count("abcdefgh") == 2

    def test_long_text(self) -> None:
        text = "a" * 400
        assert _estimate_token_count(text) == 100

    def test_whitespace_counts(self) -> None:
        text = " " * 8
        assert _estimate_token_count(text) == 2


# ---------------------------------------------------------------------------
# RetrievalRequest
# ---------------------------------------------------------------------------


class TestRetrievalRequest:
    def test_minimal_instantiation(self) -> None:
        req = RetrievalRequest(
            task_type_code=TaskTypeCode.INFRASTRUCTURE_AUDIT,
            target_entity_ids=[uuid.uuid4()],
            scope_description="test scope",
            created_by="agent-001",
        )
        assert req.task_type_code == TaskTypeCode.INFRASTRUCTURE_AUDIT
        assert req.lexical_query is None
        assert req.semantic_query_vec is None
        assert req.max_items_per_stage == 20

    def test_full_request(self) -> None:
        uid = uuid.uuid4()
        req = RetrievalRequest(
            task_type_code=TaskTypeCode.INFRASTRUCTURE_AUDIT,
            target_entity_ids=[uid],
            scope_description="audit run",
            created_by="agent-audit",
            lexical_query="GPU cluster status",
            semantic_query_vec=[0.1, 0.2, 0.3],
            max_items_per_stage=50,
        )
        assert req.lexical_query == "GPU cluster status"
        assert req.semantic_query_vec == [0.1, 0.2, 0.3]
        assert req.max_items_per_stage == 50


# ---------------------------------------------------------------------------
# AssembledItem
# ---------------------------------------------------------------------------


class TestAssembledItem:
    def test_instantiation(self) -> None:
        item = AssembledItem(
            context_class=ContextClass.CHUNK_LEXICAL,
            entity_kind_term_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
            document_chunk_id=None,
            evidence_artifact_id=None,
            inclusion_reason="mandatory:CHUNK_LEXICAL",
            is_mandatory=True,
            estimated_token_count=50,
        )
        assert item.context_class == ContextClass.CHUNK_LEXICAL
        assert item.is_mandatory is True
        assert item.estimated_token_count == 50

    def test_inclusion_reason_mutable(self) -> None:
        item = AssembledItem(
            context_class=ContextClass.EVIDENCE_ARTIFACT,
            entity_kind_term_id=uuid.uuid4(),
            entity_id=None,
            document_chunk_id=None,
            evidence_artifact_id=uuid.uuid4(),
            inclusion_reason="supplementary",
            is_mandatory=False,
            estimated_token_count=10,
        )
        item.inclusion_reason = "BUDGET-OVERFLOW:supplementary"
        assert "BUDGET-OVERFLOW" in item.inclusion_reason


# ---------------------------------------------------------------------------
# BrokerResult
# ---------------------------------------------------------------------------


class TestBrokerResult:
    def test_empty_violations_is_ok(self) -> None:
        result = BrokerResult(
            pack=None,
            items=[],
            violations=[],
            warnings=[],
            token_total=0,
        )
        assert result.pack is None
        assert not result.violations

    def test_with_violation(self) -> None:
        v = ContractViolation(
            code="MANDATORY_MISSING",
            message="Missing required context class",
            context_class=ContextClass.REGISTRY_HOST,
        )
        result = BrokerResult(
            pack=None,
            items=[],
            violations=[v],
            warnings=[],
            token_total=0,
        )
        assert len(result.violations) == 1


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------


class TestSentinelTermId:
    def test_is_deterministic_uuid(self) -> None:
        assert str(_UNKNOWN_KIND_TERM_ID) == "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# RetrievalBroker.assemble() — mocked
# ---------------------------------------------------------------------------


class TestRetrievalBrokerAssemble:
    def _make_session(self) -> MagicMock:
        session = MagicMock()
        session.flush = MagicMock()
        return session

    def _make_request(self) -> RetrievalRequest:
        return RetrievalRequest(
            task_type_code=TaskTypeCode.INFRASTRUCTURE_AUDIT,
            target_entity_ids=[uuid.uuid4()],
            scope_description="test audit",
            created_by="test-agent",
        )

    def test_assemble_violations_when_no_mandatory_classes(self) -> None:
        session = self._make_session()
        broker = RetrievalBroker(session)
        req = self._make_request()

        with (
            patch.object(broker, "_stage1_exact_lookup", return_value=[]),
            patch.object(broker, "_stage2_metadata_filter", return_value=[]),
            patch.object(broker, "_stage3_lexical", return_value=[]),
            patch.object(broker, "_stage4_semantic", return_value=[]),
        ):
            result = broker.assemble(req)

        # All stages return []: every mandatory class is absent.
        # ADR-003 §5 contract: violations → pack is never persisted (None).
        # validate_pack_classes emits exactly one MANDATORY_MISSING violation per absent class.
        assert result.pack is None
        assert len(result.violations) == len(get_contract(req.task_type_code).mandatory_classes)
        assert all(v.code == "MANDATORY_MISSING" for v in result.violations)

    def test_broker_init_stores_session(self) -> None:
        session = self._make_session()
        broker = RetrievalBroker(session)
        assert broker._session is session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_broker_and_session() -> tuple[RetrievalBroker, MagicMock]:
    session = MagicMock()
    session.flush = MagicMock()
    return RetrievalBroker(session), session


def _infra_request(**kwargs: Any) -> RetrievalRequest:
    defaults: dict[str, Any] = {
        "task_type_code": TaskTypeCode.INFRASTRUCTURE_AUDIT,
        "target_entity_ids": [uuid.uuid4()],
        "scope_description": "test",
        "created_by": "test-agent",
    }
    defaults.update(kwargs)
    return RetrievalRequest(**defaults)


def _make_host_mock() -> MagicMock:
    h = MagicMock()
    h.entity_kind_term_id = uuid.uuid4()
    h.host_id = uuid.uuid4()
    h.host_code = "prod-01"
    h.hostname = "prod-01.internal"
    h.os_family_term_id = uuid.uuid4()
    return h


def _make_svc_mock() -> MagicMock:
    s = MagicMock()
    s.service_kind_term_id = uuid.uuid4()
    s.shared_service_id = uuid.uuid4()
    s.service_code = "redis"
    s.name = "Redis Cache"
    return s


def _make_artifact_mock(content: str = "artifact content here") -> MagicMock:
    a = MagicMock()
    a.evidence_kind_term_id = uuid.uuid4()
    a.evidence_artifact_id = uuid.uuid4()
    a.content_excerpt_text = content
    return a


def _make_chunk_mock(content: str = "chunk content text", tokens: int = 5) -> MagicMock:
    c = MagicMock()
    c.document_chunk_id = uuid.uuid4()
    c.content_text = content
    c.section_path_text = "section/path"
    c.token_count = tokens
    return c


# ---------------------------------------------------------------------------
# Stage 1 — exact lookup
# ---------------------------------------------------------------------------


class TestStage1ExactLookup:
    def test_host_found_returns_registry_host_item(self) -> None:
        broker, session = _make_broker_and_session()
        host = _make_host_mock()
        session.get.return_value = host

        req = _infra_request(target_entity_ids=[host.host_id])
        contract = get_contract(req.task_type_code)
        items = broker._stage1_exact_lookup(req, contract)

        assert len(items) == 1
        assert items[0].context_class == ContextClass.REGISTRY_HOST
        assert items[0].entity_id == host.host_id

    def test_host_not_found_service_found_returns_service_item(self) -> None:
        broker, session = _make_broker_and_session()
        svc = _make_svc_mock()
        # First call (Host) → None, second call (SharedService) → svc
        session.get.side_effect = [None, svc]

        req = _infra_request(target_entity_ids=[uuid.uuid4()])
        contract = get_contract(req.task_type_code)
        items = broker._stage1_exact_lookup(req, contract)

        assert len(items) == 1
        assert items[0].context_class == ContextClass.REGISTRY_SERVICE

    def test_both_not_found_returns_empty(self) -> None:
        broker, session = _make_broker_and_session()
        session.get.return_value = None

        req = _infra_request(target_entity_ids=[uuid.uuid4()])
        contract = get_contract(req.task_type_code)
        items = broker._stage1_exact_lookup(req, contract)

        assert not items

    def test_empty_target_ids_returns_empty(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request(target_entity_ids=[])
        contract = get_contract(req.task_type_code)
        items = broker._stage1_exact_lookup(req, contract)
        assert not items

    def test_mandatory_flag_set_correctly(self) -> None:
        broker, session = _make_broker_and_session()
        host = _make_host_mock()
        session.get.return_value = host

        req = _infra_request(target_entity_ids=[host.host_id])
        contract = get_contract(req.task_type_code)
        items = broker._stage1_exact_lookup(req, contract)

        # REGISTRY_HOST is mandatory in INFRASTRUCTURE_AUDIT
        assert items[0].is_mandatory is True


# ---------------------------------------------------------------------------
# Stage 2 — metadata filter
# ---------------------------------------------------------------------------


class TestStage2MetadataFilter:
    def test_budget_zero_returns_empty(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request()
        contract = get_contract(req.task_type_code)
        # Pass current_tokens equal to budget → no room left
        items = broker._stage2_metadata_filter(req, contract, contract.token_budget)
        assert not items

    def test_collects_artifacts_when_available(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request()
        contract = get_contract(req.task_type_code)

        artifact = _make_artifact_mock()
        with (
            patch.object(broker, "_fetch_evidence_artifacts", return_value=[artifact]),
            patch.object(broker, "_fetch_observed_facts", return_value=[]),
            patch.object(broker, "_fetch_ownership", return_value=[]),
            patch.object(broker, "_fetch_canonical_docs", return_value=[]),
        ):
            items = broker._stage2_metadata_filter(req, contract, 0)

        assert any(i.context_class == ContextClass.EVIDENCE_ARTIFACT for i in items)

    def test_collects_observed_facts(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request()
        contract = get_contract(req.task_type_code)

        fact = MagicMock()
        fact.entity_kind_term_id = uuid.uuid4()
        fact.entity_id = uuid.uuid4()
        fact.fact_namespace = "runtime"
        fact.fact_key = "posture"

        with (
            patch.object(broker, "_fetch_evidence_artifacts", return_value=[]),
            patch.object(broker, "_fetch_observed_facts", return_value=[fact]),
            patch.object(broker, "_fetch_ownership", return_value=[]),
            patch.object(broker, "_fetch_canonical_docs", return_value=[]),
        ):
            items = broker._stage2_metadata_filter(req, contract, 0)

        assert any(i.context_class == ContextClass.OBSERVED_FACT for i in items)

    def test_collects_ownership(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request()
        contract = get_contract(req.task_type_code)

        oa = MagicMock()
        oa.entity_kind_term_id = uuid.uuid4()
        oa.entity_id = uuid.uuid4()
        oa.owner_code = "team:platform"

        with (
            patch.object(broker, "_fetch_evidence_artifacts", return_value=[]),
            patch.object(broker, "_fetch_observed_facts", return_value=[]),
            patch.object(broker, "_fetch_ownership", return_value=[oa]),
            patch.object(broker, "_fetch_canonical_docs", return_value=[]),
        ):
            items = broker._stage2_metadata_filter(req, contract, 0)

        assert any(i.context_class == ContextClass.REGISTRY_OWNERSHIP for i in items)

    def test_artifact_over_budget_skipped(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request()
        contract = get_contract(req.task_type_code)

        # artifact content so large it exceeds budget
        huge_artifact = _make_artifact_mock("x" * (contract.token_budget * 8))

        with (
            patch.object(broker, "_fetch_evidence_artifacts", return_value=[huge_artifact]),
            patch.object(broker, "_fetch_observed_facts", return_value=[]),
            patch.object(broker, "_fetch_ownership", return_value=[]),
            patch.object(broker, "_fetch_canonical_docs", return_value=[]),
        ):
            items = broker._stage2_metadata_filter(req, contract, 0)

        # Artifact should be skipped if it doesn't fit
        assert not any(i.context_class == ContextClass.EVIDENCE_ARTIFACT for i in items)


# ---------------------------------------------------------------------------
# Stage 3 — lexical search
# ---------------------------------------------------------------------------


class TestStage3Lexical:
    def test_no_lexical_query_returns_empty(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request(lexical_query=None)
        contract = get_contract(req.task_type_code)
        items = broker._stage3_lexical(req, contract, 0)
        assert not items

    def test_empty_lexical_query_returns_empty(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request(lexical_query="   ")
        contract = get_contract(req.task_type_code)
        # CHUNK_LEXICAL is allowed in INFRASTRUCTURE_AUDIT (recommended), but empty query → skip
        items = broker._stage3_lexical(req, contract, 0)
        assert not items

    def test_no_query_at_all_skips_lexical(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request(lexical_query="")  # empty string
        contract = get_contract(req.task_type_code)
        items = broker._stage3_lexical(req, contract, 0)
        assert not items

    def test_lexical_query_returns_chunk_items(self) -> None:
        broker, session = _make_broker_and_session()
        req = _infra_request(lexical_query="gpu cluster")
        contract = get_contract(req.task_type_code)

        chunk = _make_chunk_mock()
        embedding = MagicMock()
        session.execute.return_value.all.return_value = [(chunk, embedding)]

        items = broker._stage3_lexical(req, contract, 0)

        assert len(items) == 1
        assert items[0].context_class == ContextClass.CHUNK_LEXICAL
        assert items[0].document_chunk_id == chunk.document_chunk_id

    def test_chunk_over_budget_breaks(self) -> None:
        broker, session = _make_broker_and_session()
        req = _infra_request(lexical_query="gpu cluster")
        contract = get_contract(req.task_type_code)

        chunk = _make_chunk_mock(tokens=contract.token_budget + 100)
        embedding = MagicMock()
        session.execute.return_value.all.return_value = [(chunk, embedding)]

        items = broker._stage3_lexical(req, contract, 0)
        assert not items


# ---------------------------------------------------------------------------
# Stage 4 — semantic augmentation
# ---------------------------------------------------------------------------


class TestStage4Semantic:
    def test_no_vector_returns_empty(self) -> None:
        broker, _ = _make_broker_and_session()
        req = _infra_request(semantic_query_vec=None)
        contract = get_contract(req.task_type_code)
        items = broker._stage4_semantic(req, contract, 0)
        assert not items

    def test_exception_in_query_returns_empty(self) -> None:
        broker, session = _make_broker_and_session()
        req = _infra_request(semantic_query_vec=[0.1] * 4096)
        contract = get_contract(TaskTypeCode.REGISTRY_RECONCILIATION)
        session.execute.side_effect = Exception("pgvector not installed")
        items = broker._stage4_semantic(req, contract, 0)
        assert not items

    def test_semantic_returns_chunk_items(self) -> None:
        broker, session = _make_broker_and_session()
        req = _infra_request(
            task_type_code=TaskTypeCode.REGISTRY_RECONCILIATION,
            semantic_query_vec=[0.1] * 4096,
        )
        contract = get_contract(req.task_type_code)

        chunk = _make_chunk_mock()
        embedding = MagicMock()
        session.execute.return_value.all.return_value = [(chunk, embedding)]

        items = broker._stage4_semantic(req, contract, 0)
        # Result depends on whether contract allows CHUNK_SEMANTIC
        assert isinstance(items, list)


# ---------------------------------------------------------------------------
# Persist pack
# ---------------------------------------------------------------------------


class TestPersistPack:
    def test_creates_pack_and_items(self) -> None:
        broker, session = _make_broker_and_session()
        # session.flush() is already a MagicMock no-op — no side_effect override needed.
        # EvidencePack.evidence_pack_id remains a mock attribute, which is sufficient
        # for verifying that add() and flush() were called and pack_items were built.
        req = _infra_request()
        contract = get_contract(req.task_type_code)

        assembled = AssembledItem(
            context_class=ContextClass.REGISTRY_HOST,
            entity_kind_term_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
            document_chunk_id=None,
            evidence_artifact_id=None,
            inclusion_reason="test",
            is_mandatory=True,
            estimated_token_count=10,
        )

        _, pack_items = broker._persist_pack(req, contract, [assembled], 10)

        # session.add should have been called at least twice (pack + item)
        assert session.add.call_count >= 2
        assert session.flush.call_count >= 1
        assert len(pack_items) == 1


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------


class TestFetchHelpers:
    def test_fetch_evidence_artifacts(self) -> None:
        broker, session = _make_broker_and_session()
        artifact = _make_artifact_mock()
        session.scalars.return_value.all.return_value = [artifact]

        req = _infra_request()
        results = broker._fetch_evidence_artifacts(req)
        assert results == [artifact]

    def test_fetch_observed_facts(self) -> None:
        broker, session = _make_broker_and_session()
        fact = MagicMock()
        session.scalars.return_value.all.return_value = [fact]

        req = _infra_request()
        results = broker._fetch_observed_facts(req)
        assert results == [fact]

    def test_fetch_ownership(self) -> None:
        broker, session = _make_broker_and_session()
        oa = MagicMock()
        session.scalars.return_value.all.return_value = [oa]

        req = _infra_request()
        results = broker._fetch_ownership(req)
        assert results == [oa]

    def test_fetch_canonical_docs(self) -> None:
        broker, session = _make_broker_and_session()
        doc = MagicMock()
        session.scalars.return_value.all.return_value = [doc]

        req = _infra_request()
        results = broker._fetch_canonical_docs(req)
        assert results == [doc]

    def test_fetch_service_instances(self) -> None:
        broker, session = _make_broker_and_session()
        si = MagicMock()
        session.scalars.return_value.all.return_value = [si]

        req = _infra_request()
        results = broker._fetch_service_instances(req)
        assert results == [si]


# ---------------------------------------------------------------------------
# Collect warnings
# ---------------------------------------------------------------------------


class TestCollectWarnings:
    def test_missing_recommended_produces_warning(self) -> None:
        contract = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        # None of the recommended classes present
        present: frozenset[ContextClass] = frozenset()
        warnings = RetrievalBroker._collect_warnings(contract, present)
        assert len(warnings) > 0
        assert all("absent" in w for w in warnings)

    def test_all_recommended_present_no_warnings(self) -> None:
        contract = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        present = contract.recommended_classes | contract.mandatory_classes
        warnings = RetrievalBroker._collect_warnings(contract, present)
        assert not warnings

    def test_partial_recommended_produces_partial_warnings(self) -> None:
        contract = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        # Provide some recommended but not all
        one_present = frozenset(list(contract.recommended_classes)[:1])
        warnings = RetrievalBroker._collect_warnings(contract, one_present)
        # Should warn about the remaining absent ones
        assert len(warnings) == len(contract.recommended_classes) - 1


# ---------------------------------------------------------------------------
# Full assemble with mocked stages — success path
# ---------------------------------------------------------------------------


class TestAssembleSuccessPath:
    def test_assemble_with_all_mandatory_classes_returns_pack(self) -> None:
        broker, _ = _make_broker_and_session()

        # Build AssembledItems for all mandatory classes in INFRASTRUCTURE_AUDIT
        contract = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
        mandatory_items = [
            AssembledItem(
                context_class=cls,
                entity_kind_term_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                document_chunk_id=None,
                evidence_artifact_id=None,
                inclusion_reason=f"mandatory:{cls.value}",
                is_mandatory=True,
                estimated_token_count=10,
            )
            for cls in contract.mandatory_classes
        ]

        with (
            patch.object(broker, "_stage1_exact_lookup", return_value=mandatory_items),
            patch.object(broker, "_stage2_metadata_filter", return_value=[]),
            patch.object(broker, "_stage3_lexical", return_value=[]),
            patch.object(broker, "_stage4_semantic", return_value=[]),
            patch.object(broker, "_persist_pack", return_value=(MagicMock(), [])),
        ):
            result = broker.assemble(_infra_request())

        assert not result.violations
        assert result.pack is not None or result.violations
