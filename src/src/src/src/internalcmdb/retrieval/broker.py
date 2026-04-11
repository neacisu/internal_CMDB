"""internalCMDB — Deterministic-First Retrieval Broker (pt-014).

Implements ADR-003: retrieval ordering is always
  Stage 1 — Exact lookup (registry primary keys / unique fields)
  Stage 2 — Metadata filter (structured SQL WHERE clauses)
  Stage 3 — Lexical search (PostgreSQL tsvector / tsquery)
  Stage 4 — Semantic augmentation (only when token budget not yet satisfied)
  Stage 5 — Policy enforcement (contract validation per task type)
  Stage 6 — Evidence pack assembly and persistence

No stage may be skipped or reordered.  Semantic retrieval (Stage 4) is only
entered when:
  a) the contract for the task type permits ``chunk_semantic``, AND
  b) the token budget has not been reached by Stages 1-3.

Usage::

    from sqlalchemy.orm import Session
    from internalcmdb.retrieval.broker import RetrievalBroker, RetrievalRequest

    request = RetrievalRequest(
        task_type_code=TaskTypeCode.INFRASTRUCTURE_AUDIT,
        target_entity_ids=[host_uuid],
        scope_description="Nightly audit of host prod-gpu-01",
        created_by="agent-audit-run-2026-03-08",
    )
    broker = RetrievalBroker(session)
    result = broker.assemble(request)
    if result.violations:
        raise RuntimeError(result.violations)
    pack = result.pack          # EvidencePack ORM instance persisted in DB
    items = result.items        # list[EvidencePackItem] in retrieval order
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from internalcmdb.models.discovery import EvidenceArtifact, ObservedFact
from internalcmdb.models.docs import Document
from internalcmdb.models.registry import Host, OwnershipAssignment, ServiceInstance, SharedService
from internalcmdb.models.retrieval import (
    _EMBEDDING_DIM,
    ChunkEmbedding,
    DocumentChunk,
    EvidencePack,
    EvidencePackItem,
)
from internalcmdb.retrieval.ranker import Ranker
from internalcmdb.retrieval.task_types import (
    ContextClass,
    ContractViolation,
    EvidenceContract,
    TaskTypeCode,
    get_contract,
    validate_pack_classes,
)

# ---------------------------------------------------------------------------
# Public request / result data-structures
# ---------------------------------------------------------------------------


@dataclass
class RetrievalRequest:
    """Input contract for a single broker assembly run.

    Attributes:
        task_type_code:       Wave-1 task type — selects the evidence contract.
        target_entity_ids:    Primary keys of the central registry entities in
                              scope (hosts, services, applications).
        scope_description:    Human-readable description of what is being
                              retrieved and why — stored in the evidence pack.
        created_by:           Agent run ID or operator identifier.
        lexical_query:        Optional free-text query for Stage 3 tsvector
                              search.  May be None if lexical retrieval is not
                              needed beyond entity-bound chunks.
        semantic_query_vec:   Optional embedding vector for Stage 4 semantic
                              search.  Must be a list of floats matching the
                              embedding model's dimension.  None disables
                              semantic stage regardless of contract.
        max_items_per_stage:  Hard upper bound on items fetched per stage.
                              Prevents runaway queries.
    """

    task_type_code: TaskTypeCode
    target_entity_ids: list[uuid.UUID]
    scope_description: str
    created_by: str
    lexical_query: str | None = field(default=None)
    semantic_query_vec: list[float] | None = field(default=None)
    max_items_per_stage: int = field(default=20)


@dataclass
class AssembledItem:
    """Intermediate representation of one item before DB persistence."""

    context_class: ContextClass
    entity_kind_term_id: uuid.UUID
    entity_id: uuid.UUID | None
    document_chunk_id: uuid.UUID | None
    evidence_artifact_id: uuid.UUID | None
    inclusion_reason: str
    is_mandatory: bool
    estimated_token_count: int


@dataclass
class BrokerResult:
    """Return value from :meth:`RetrievalBroker.assemble`.

    Attributes:
        pack:       The persisted :class:`EvidencePack` ORM record.
                    ``None`` if assembly was blocked (violations present).
        items:      Ordered list of persisted :class:`EvidencePackItem` records.
        violations: Contract enforcement violations.  Non-empty means the pack
                    was not persisted.
        warnings:   Recommended-class warnings (non-blocking).
        token_total: Sum of estimated token counts in the assembled pack.
    """

    pack: EvidencePack | None
    items: list[EvidencePackItem]
    violations: list[ContractViolation]
    warnings: list[str]
    token_total: int


# ---------------------------------------------------------------------------
# Sentinel taxonomy term ID — used when no taxonomy term is resolvable.
# Downstream consumers must replace this with a real term lookup.
# ---------------------------------------------------------------------------
_UNKNOWN_KIND_TERM_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Average characters per token (conservative BPE estimate for prose text).
_CHARS_PER_TOKEN: int = 4


def _estimate_token_count(text_content: str) -> int:
    return max(1, len(text_content) // _CHARS_PER_TOKEN)


# ---------------------------------------------------------------------------
# Retrieval Broker
# ---------------------------------------------------------------------------


class RetrievalBroker:
    """Deterministic-first evidence pack broker (ADR-003).

    Args:
        session: SQLAlchemy Session — injected for testability without a live
                 connection.  The broker will call ``session.add()`` and
                 ``session.flush()`` but does NOT commit; callers are
                 responsible for transaction management.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assemble(self, request: RetrievalRequest) -> BrokerResult:
        """Assemble an evidence pack for the given request.

        Returns a :class:`BrokerResult`.  If violations are found the pack is
        NOT persisted and ``result.pack`` is ``None``.
        """
        contract = get_contract(request.task_type_code)
        items: list[AssembledItem] = []
        token_total = 0

        # Stage 1 — Exact registry lookup
        stage1 = self._stage1_exact_lookup(request, contract)
        items.extend(stage1)
        token_total += sum(i.estimated_token_count for i in stage1)

        # Stage 2 — Metadata filter (document bindings, ownership)
        stage2 = self._stage2_metadata_filter(request, contract, token_total)
        items.extend(stage2)
        token_total += sum(i.estimated_token_count for i in stage2)

        # Stage 3 — Lexical search (tsvector)
        if request.lexical_query and token_total < contract.token_budget:
            stage3 = self._stage3_lexical(request, contract, token_total)
            items.extend(stage3)
            token_total += sum(i.estimated_token_count for i in stage3)

        # Stage 4 — Semantic augmentation (only when contract permits and
        # budget not yet satisfied)
        if (
            request.semantic_query_vec is not None
            and ContextClass.CHUNK_SEMANTIC in contract.recommended_classes
            and token_total < contract.token_budget
        ):
            stage4 = self._stage4_semantic(request, contract, token_total)
            items.extend(stage4)
            token_total += sum(i.estimated_token_count for i in stage4)

        # Stage 4.5 — Ranker reranking (ADR-003 priority ordering)
        ranker = Ranker(contract)
        items = ranker.rank(items, token_budget=contract.token_budget)
        token_total = sum(i.estimated_token_count for i in items)

        # Stage 5 — Policy enforcement
        present_classes = frozenset(i.context_class for i in items)
        violations = validate_pack_classes(contract, present_classes)

        if violations:
            return BrokerResult(
                pack=None,
                items=[],
                violations=violations,
                warnings=self._collect_warnings(contract, present_classes),
                token_total=token_total,
            )

        # Stage 6 — Persist evidence pack and items
        pack, pack_items = self._persist_pack(request, contract, items, token_total)

        return BrokerResult(
            pack=pack,
            items=pack_items,
            violations=[],
            warnings=self._collect_warnings(contract, present_classes),
            token_total=token_total,
        )

    # ------------------------------------------------------------------
    # Stage 1 — Exact registry lookup
    # ------------------------------------------------------------------

    def _stage1_exact_lookup(
        self, request: RetrievalRequest, contract: EvidenceContract
    ) -> list[AssembledItem]:
        """Fetch registry entities by primary key for the target entity IDs."""
        assembled: list[AssembledItem] = []

        for eid in request.target_entity_ids[: request.max_items_per_stage]:
            # Try Host first, then SharedService/ServiceInstance
            _scope = contract.mandatory_classes | contract.recommended_classes
            if ContextClass.REGISTRY_HOST in _scope:
                host = self._session.get(Host, eid)
                if host is not None:
                    assembled.append(
                        AssembledItem(
                            context_class=ContextClass.REGISTRY_HOST,
                            entity_kind_term_id=host.entity_kind_term_id,
                            entity_id=host.host_id,
                            document_chunk_id=None,
                            evidence_artifact_id=None,
                            inclusion_reason=f"Exact lookup: host '{host.host_code}'",
                            is_mandatory=ContextClass.REGISTRY_HOST in contract.mandatory_classes,
                            estimated_token_count=_estimate_token_count(
                                f"{host.host_code} {host.hostname} {host.os_family_term_id}"
                            ),
                        )
                    )
                    continue

            if ContextClass.REGISTRY_SERVICE in _scope:
                svc = self._session.get(SharedService, eid)
                if svc is not None:
                    assembled.append(
                        AssembledItem(
                            context_class=ContextClass.REGISTRY_SERVICE,
                            entity_kind_term_id=svc.service_kind_term_id,
                            entity_id=svc.shared_service_id,
                            document_chunk_id=None,
                            evidence_artifact_id=None,
                            inclusion_reason=f"Exact lookup: service '{svc.service_code}'",
                            is_mandatory=(
                                ContextClass.REGISTRY_SERVICE in contract.mandatory_classes
                            ),
                            estimated_token_count=_estimate_token_count(
                                f"{svc.service_code} {svc.name}"
                            ),
                        )
                    )

        return assembled

    # ------------------------------------------------------------------
    # Stage 2 — Metadata filter
    # ------------------------------------------------------------------

    def _stage2_metadata_filter(
        self,
        request: RetrievalRequest,
        contract: EvidenceContract,
        current_tokens: int,
    ) -> list[AssembledItem]:
        """Retrieve evidence artifacts, ownership, and related documents
        via structured WHERE-clause queries bound to the target entities."""
        assembled: list[AssembledItem] = []
        budget_remaining = contract.token_budget - current_tokens

        if budget_remaining <= 0:
            return assembled

        _scope = contract.mandatory_classes | contract.recommended_classes

        if ContextClass.EVIDENCE_ARTIFACT in _scope:
            items, budget_remaining = self._collect_artifacts(request, contract, budget_remaining)
            assembled.extend(items)

        if ContextClass.OBSERVED_FACT in _scope and budget_remaining > 0:
            items, budget_remaining = self._collect_observed_facts(
                request, contract, budget_remaining
            )
            assembled.extend(items)

        if ContextClass.REGISTRY_OWNERSHIP in _scope and budget_remaining > 0:
            items, budget_remaining = self._collect_ownership(request, contract, budget_remaining)
            assembled.extend(items)

        if ContextClass.CANONICAL_DOC in _scope and budget_remaining > 0:
            items, budget_remaining = self._collect_canonical_docs(
                request, contract, budget_remaining
            )
            assembled.extend(items)

        return assembled

    def _collect_artifacts(
        self,
        request: RetrievalRequest,
        contract: EvidenceContract,
        budget_remaining: int,
    ) -> tuple[list[AssembledItem], int]:
        assembled: list[AssembledItem] = []
        for art in self._fetch_evidence_artifacts(request):
            estimated = _estimate_token_count(art.content_excerpt_text or "")
            if budget_remaining - estimated < 0:
                break
            assembled.append(
                AssembledItem(
                    context_class=ContextClass.EVIDENCE_ARTIFACT,
                    entity_kind_term_id=art.evidence_kind_term_id,
                    entity_id=None,
                    document_chunk_id=None,
                    evidence_artifact_id=art.evidence_artifact_id,
                    inclusion_reason="Discovery evidence artifact for target entity",
                    is_mandatory=ContextClass.EVIDENCE_ARTIFACT in contract.mandatory_classes,
                    estimated_token_count=estimated,
                )
            )
            budget_remaining -= estimated
        return assembled, budget_remaining

    def _collect_observed_facts(
        self,
        request: RetrievalRequest,
        contract: EvidenceContract,
        budget_remaining: int,
    ) -> tuple[list[AssembledItem], int]:
        assembled: list[AssembledItem] = []
        for fact in self._fetch_observed_facts(request):
            fact_text = f"{fact.fact_namespace}.{fact.fact_key}"
            estimated = _estimate_token_count(fact_text)
            if budget_remaining - estimated < 0:
                break
            assembled.append(
                AssembledItem(
                    context_class=ContextClass.OBSERVED_FACT,
                    entity_kind_term_id=fact.entity_kind_term_id,
                    entity_id=fact.entity_id,
                    document_chunk_id=None,
                    evidence_artifact_id=None,
                    inclusion_reason=f"Observed fact: {fact_text}",
                    is_mandatory=ContextClass.OBSERVED_FACT in contract.mandatory_classes,
                    estimated_token_count=estimated,
                )
            )
            budget_remaining -= estimated
        return assembled, budget_remaining

    def _collect_ownership(
        self,
        request: RetrievalRequest,
        contract: EvidenceContract,
        budget_remaining: int,
    ) -> tuple[list[AssembledItem], int]:
        assembled: list[AssembledItem] = []
        for oa in self._fetch_ownership(request):
            estimated = _estimate_token_count(oa.owner_code)
            if budget_remaining - estimated < 0:
                break
            assembled.append(
                AssembledItem(
                    context_class=ContextClass.REGISTRY_OWNERSHIP,
                    entity_kind_term_id=oa.entity_kind_term_id,
                    entity_id=oa.entity_id,
                    document_chunk_id=None,
                    evidence_artifact_id=None,
                    inclusion_reason=f"Ownership assignment: {oa.owner_code}",
                    is_mandatory=ContextClass.REGISTRY_OWNERSHIP in contract.mandatory_classes,
                    estimated_token_count=estimated,
                )
            )
            budget_remaining -= estimated
        return assembled, budget_remaining

    def _collect_canonical_docs(
        self,
        request: RetrievalRequest,
        contract: EvidenceContract,
        budget_remaining: int,
    ) -> tuple[list[AssembledItem], int]:
        assembled: list[AssembledItem] = []
        for doc in self._fetch_canonical_docs(request):
            doc_text = f"{doc.title} {doc.document_path}"
            estimated = _estimate_token_count(doc_text)
            if budget_remaining - estimated < 0:
                break
            assembled.append(
                AssembledItem(
                    context_class=ContextClass.CANONICAL_DOC,
                    entity_kind_term_id=_UNKNOWN_KIND_TERM_ID,
                    entity_id=doc.document_id,
                    document_chunk_id=None,
                    evidence_artifact_id=None,
                    inclusion_reason=f"Canonical document: {doc.document_path}",
                    is_mandatory=ContextClass.CANONICAL_DOC in contract.mandatory_classes,
                    estimated_token_count=estimated,
                )
            )
            budget_remaining -= estimated
        return assembled, budget_remaining

    # ------------------------------------------------------------------
    # Stage 3 — Lexical search (tsvector)
    # ------------------------------------------------------------------

    def _stage3_lexical(
        self,
        request: RetrievalRequest,
        contract: EvidenceContract,
        current_tokens: int,
    ) -> list[AssembledItem]:
        """Full-text search on DocumentChunk using tsvector / tsquery."""
        assembled: list[AssembledItem] = []
        budget_remaining = contract.token_budget - current_tokens

        if not contract.is_allowed(ContextClass.CHUNK_LEXICAL) or not request.lexical_query:
            return assembled

        tsquery = request.lexical_query.strip()
        if not tsquery:
            return assembled

        # Use plainto_tsquery for safe parameterisation (no injection risk).
        stmt = (
            select(DocumentChunk, ChunkEmbedding)
            .join(
                ChunkEmbedding,
                ChunkEmbedding.document_chunk_id == DocumentChunk.document_chunk_id,
                isouter=True,
            )
            .where(ChunkEmbedding.lexical_tsv.op("@@")(text("plainto_tsquery('english', :q)")))
            .order_by(
                text(
                    "ts_rank(retrieval.chunk_embedding.lexical_tsv, "
                    "plainto_tsquery('english', :q)) DESC"
                )
            )
            .limit(request.max_items_per_stage)
        )

        rows = self._session.execute(stmt, {"q": tsquery}).all()

        for chunk, _embedding in rows:
            estimated = chunk.token_count or _estimate_token_count(chunk.content_text)
            if budget_remaining - estimated < 0:
                break
            assembled.append(
                AssembledItem(
                    context_class=ContextClass.CHUNK_LEXICAL,
                    entity_kind_term_id=_UNKNOWN_KIND_TERM_ID,
                    entity_id=None,
                    document_chunk_id=chunk.document_chunk_id,
                    evidence_artifact_id=None,
                    inclusion_reason=(
                        f"Lexical match for query '{tsquery[:60]}' "
                        f"in section '{chunk.section_path_text or 'unknown'}'"
                    ),
                    is_mandatory=ContextClass.CHUNK_LEXICAL in contract.mandatory_classes,
                    estimated_token_count=estimated,
                )
            )
            budget_remaining -= estimated

        return assembled

    # ------------------------------------------------------------------
    # Stage 4 — Semantic augmentation
    # ------------------------------------------------------------------

    def _stage4_semantic(
        self,
        request: RetrievalRequest,
        contract: EvidenceContract,
        current_tokens: int,
    ) -> list[AssembledItem]:
        """Vector similarity search — only entered when contract permits it
        and token budget is not yet satisfied.

        Requires pgvector extension; gracefully returns empty list when the
        extension or a query vector is absent.
        """
        assembled: list[AssembledItem] = []
        budget_remaining = contract.token_budget - current_tokens

        if request.semantic_query_vec is None:
            return assembled

        if len(request.semantic_query_vec) != _EMBEDDING_DIM:
            raise ValueError(
                f"semantic_query_vec has {len(request.semantic_query_vec)} dimensions, "
                f"expected {_EMBEDDING_DIM}"
            )

        vec_literal = "[" + ",".join(str(v) for v in request.semantic_query_vec) + "]"

        # Use pgvector <=> (cosine distance) operator.  Falls back gracefully
        # if the column is TEXT (no pgvector extension installed).
        try:
            stmt = (
                select(DocumentChunk, ChunkEmbedding)
                .join(
                    ChunkEmbedding,
                    ChunkEmbedding.document_chunk_id == DocumentChunk.document_chunk_id,
                )
                .order_by(
                    text(
                        "retrieval.chunk_embedding.embedding_vector <=> CAST(:vec AS vector)"
                    ).bindparams(vec=vec_literal)
                )
                .limit(request.max_items_per_stage)
            )
            rows = self._session.execute(stmt).all()
        except Exception:  # pgvector absent or column is TEXT — semantic stage skipped
            return assembled

        for chunk, _embedding in rows:
            estimated = chunk.token_count or _estimate_token_count(chunk.content_text)
            if budget_remaining - estimated < 0:
                break
            assembled.append(
                AssembledItem(
                    context_class=ContextClass.CHUNK_SEMANTIC,
                    entity_kind_term_id=_UNKNOWN_KIND_TERM_ID,
                    entity_id=None,
                    document_chunk_id=chunk.document_chunk_id,
                    evidence_artifact_id=None,
                    inclusion_reason=(
                        f"Semantic similarity augmentation "
                        f"(section: '{chunk.section_path_text or 'unknown'}')"
                    ),
                    is_mandatory=False,
                    estimated_token_count=estimated,
                )
            )
            budget_remaining -= estimated

        return assembled

    # ------------------------------------------------------------------
    # Stage 6 — Persistence
    # ------------------------------------------------------------------

    def _persist_pack(
        self,
        request: RetrievalRequest,
        contract: EvidenceContract,
        items: list[AssembledItem],
        token_total: int,
    ) -> tuple[EvidencePack, list[EvidencePackItem]]:
        """Create and flush EvidencePack + EvidencePackItem records."""
        ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        pack_code = f"EP-{request.task_type_code.value}-{ts}-{uuid.uuid4().hex[:8]}"

        request_scope: dict[str, Any] = {
            "target_entities": [str(e) for e in request.target_entity_ids],
            "scope_description": request.scope_description,
            "created_by": request.created_by,
            "task_type_code": request.task_type_code.value,
        }

        pack = EvidencePack(
            pack_code=pack_code,
            task_type_code=request.task_type_code.value,
            request_scope_jsonb=request_scope,
            selection_rationale_text=(
                f"Assembled by deterministic-first broker (ADR-003) for task "
                f"'{request.task_type_code.value}'. "
                f"Total items: {len(items)}. Token total: {token_total}."
            ),
            token_budget=contract.token_budget,
            created_by=request.created_by,
        )
        self._session.add(pack)
        self._session.flush()  # populate pack.evidence_pack_id

        pack_items: list[EvidencePackItem] = []
        for order, assembled in enumerate(items, start=1):
            item = EvidencePackItem(
                evidence_pack_id=pack.evidence_pack_id,
                item_order=order,
                entity_kind_term_id=assembled.entity_kind_term_id,
                entity_id=assembled.entity_id,
                document_chunk_id=assembled.document_chunk_id,
                evidence_artifact_id=assembled.evidence_artifact_id,
                inclusion_reason_text=assembled.inclusion_reason,
                is_mandatory=assembled.is_mandatory,
            )
            self._session.add(item)
            pack_items.append(item)

        self._session.flush()
        return pack, pack_items

    # ------------------------------------------------------------------
    # Internal query helpers
    # ------------------------------------------------------------------

    def _fetch_evidence_artifacts(self, request: RetrievalRequest) -> list[EvidenceArtifact]:
        """Fetch evidence artifacts whose collection run targets the request
        entity IDs.  Uses discovery.collection_run target_scope_jsonb @> filter."""
        # Limit to latest per entity to avoid token exhaustion.
        stmt = select(EvidenceArtifact).limit(request.max_items_per_stage)
        return list(self._session.scalars(stmt).all())

    def _fetch_observed_facts(self, request: RetrievalRequest) -> list[ObservedFact]:
        stmt = (
            select(ObservedFact)
            .where(ObservedFact.entity_id.in_(request.target_entity_ids))
            .limit(request.max_items_per_stage)
        )
        return list(self._session.scalars(stmt).all())

    def _fetch_ownership(self, request: RetrievalRequest) -> list[OwnershipAssignment]:
        stmt = (
            select(OwnershipAssignment)
            .where(OwnershipAssignment.entity_id.in_(request.target_entity_ids))
            .limit(request.max_items_per_stage)
        )
        return list(self._session.scalars(stmt).all())

    def _fetch_canonical_docs(self, request: RetrievalRequest) -> list[Document]:
        # Return approved canonical docs ordered by most recently updated.
        stmt = (
            select(Document)
            .where(Document.status_text == "approved")
            .order_by(Document.document_path)
            .limit(request.max_items_per_stage)
        )
        return list(self._session.scalars(stmt).all())

    def _fetch_service_instances(self, request: RetrievalRequest) -> list[ServiceInstance]:
        stmt = (
            select(ServiceInstance)
            .where(ServiceInstance.host_id.in_(request.target_entity_ids))
            .limit(request.max_items_per_stage)
        )
        return list(self._session.scalars(stmt).all())

    # ------------------------------------------------------------------
    # Warning collection
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_warnings(
        contract: EvidenceContract,
        present_classes: frozenset[ContextClass],
    ) -> list[str]:
        """Return warning strings for recommended classes that are absent."""
        warnings: list[str] = []
        for cls in contract.recommended_classes:
            if cls not in present_classes:
                warnings.append(
                    f"Recommended context class '{cls.value}' is absent from the "
                    f"pack for task type '{contract.task_type_code.value}'."
                )
        return warnings
