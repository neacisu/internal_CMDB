---
id: ADR-003
title: Retrieval Ordering — Deterministic-First Pipeline Before Semantic Augmentation
status: approved
date: 2026-03-08
created: 2026-03-08
updated: 2026-03-08
deciders:
  - name: Alex Neacsu
    role: Architecture Board
    approved_at: 2026-03-08
doc_class: adr
domain: platform-foundations
version: "1.0"
owner: platform_architecture_lead
binding: []
tags: [retrieval, deterministic-first, semantic, context-broker, wave-1]
---

# ADR-003 — Retrieval Ordering: Deterministic-First Before Semantic

## Status

**Accepted** — 2026-03-08, Alex Neacsu (Architecture Board)

---

## Context

AI agents consume context assembled from structured registry data, canonical documents and
observed facts. Context assembly strategy has a direct impact on:

- hallucination rate (agents filling gaps with invented facts);
- token consumption (loading irrelevant semantic results);
- auditability (provenance of each context item);
- safety (semantic results may match intent but not accuracy).

Two extreme approaches exist: pure semantic retrieval (embed everything, retrieve by cosine
similarity) and pure structured retrieval (exact SQL lookups only). Both fail: the former
introduces hallucination risk from imprecise similarity; the latter fails for unstructured
document content.

---

## Decision

**The platform enforces a deterministic-first retrieval ordering. Semantic retrieval is always
the last stage and is applied only on a pre-filtered, policy-bounded subset. No retrieval flow
may start from semantic search when structured data exists for the query.**

### Retrieval pipeline — mandatory ordering

```
Stage 1: Exact lookup
  └── Registry entity lookup by identifier (UUID, hostname, service_name)
  └── Document lookup by doc_id, doc_class, domain combination
  └── Taxonomy term exact match

Stage 2: Metadata filtering
  └── Filter by doc_class, domain, environment, lifecycle_status
  └── Filter by confidence threshold, recency (collected_at / updated_at)
  └── Filter by ownership (owner, approver role)

Stage 3: Lexical search (PostgreSQL FTS)
  └── tsvector/tsquery on document chunks, titles, summaries
  └── Applied on pre-filtered subset from Stage 2

Stage 4: Semantic retrieval (pgvector cosine similarity)
  └── Applied ONLY on the subset passing Stages 1-3
  └── Max result limit enforced per task type
  └── Minimum similarity threshold enforced per task type

Stage 5: Reranking and deduplication
  └── Cross-stage deduplication by source hash
  └── Reranking by relevance + provenance quality + recency

Stage 6: Evidence pack generation
  └── Each included item carries: source, state_type, confidence, collected_at, selection_reason
  └── Items with no provenance are excluded regardless of similarity score

Stage 7: Answer constraints enforcement
  └── Gaps in required evidence classes reported as specification gaps
  └── Evidence pack size bounded by task type contract (token budget)
```

### Enforcement rules

1. **Stage ordering is non-negotiable.** A retrieval implementation that inverts or skips stages
   fails its verification contract.
2. **Semantic retrieval is forbidden as the first stage** when a structured identifier or
   metadata query is sufficient to obtain the result.
3. **Every evidence pack item must have provenance**: source document/entity ID, state type,
   confidence level ≥ 0.0, and collection timestamp.
4. **Gaps in required evidence classes are surfaced as findings**, not silently filled by
   semantic results.
5. **Token budget per task type** must be defined in the task type catalog (pt-013) before
   semantic augmentation is enabled for that task type.

---

## Alternatives Considered

### Alt A — Pure semantic retrieval for all queries
Embed all documents and registry summaries, retrieve by cosine similarity for every query.
**Rejected**: semantic retrieval is imprecise for entity lookups (e.g., "which host runs
postgres?" should be an exact registry join, not a similarity search), inflates token cost,
loses structured provenance, enables hallucination when similar but incorrect chunks rank high.

### Alt B — Structured-only retrieval (no semantic)
All context assembled exclusively through SQL and exact matching. **Rejected**: insufficient for
unstructured document content where the relevant section is not identifiable by exact term match.
Fails for discovery queries over runbooks, ADRs and policy packs.

### Alt C — Parallel retrieval (structured + semantic simultaneously, merged by score)
Both pipelines run concurrently and results are merged by a fusion ranking function.
**Rejected**: loses the deterministic guarantee that exact and filtered results always dominate;
a high-similarity semantic result could rank above a lower-scored but definitive exact match.
Increases latency and complexity without improving correctness for structured queries.

---

## Consequences

### Positive
- Exact registry facts always dominate over approximate semantic matches.
- Token consumption is minimized by filtering before semantic expansion.
- Evidence packs are auditable: each item's inclusion reason is explicit.
- Hallucination rate is bounded: agents cannot receive semantically plausible but structurally
  incorrect facts when exact data exists.

### Negative / Tradeoffs
- Retrieval implementation must be stage-aware, not a simple similarity search.
- Task type catalog (ADR dependency: pt-013) must be defined before semantic stage is enabled.
- Chunking and embedding pipelines are required for Stage 4 to function.
- Retrieval verification requires controlled tests per task type.

---

## Implementation Bindings

| Constraint | Binding |
| --- | --- |
| Structured retrieval | SQLAlchemy queries on `registry`, `discovery`, `docs` schemas |
| Lexical search | PostgreSQL `tsvector` + `tsquery` on `retrieval.document_chunk` |
| Vector storage | `retrieval.chunk_embedding` via pgvector |
| Evidence pack schema | `retrieval.evidence_pack` + `retrieval.evidence_pack_item` |
| Task type catalog | pt-013 deliverable (sprint-6) — required before semantic stage activation |
| Retrieval broker | Part of epic-4 / impl-epic-7 delivery |

---

*Source: blueprint_platforma_interna.md §13.3, explicit_decisions.retrieval_execution_model, ADR review 2026-03-08*
