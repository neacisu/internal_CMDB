---
id: GOV-006
title: internalCMDB — Task Type Catalog and Evidence Pack Contracts (Wave-1)
doc_class: policy_pack
domain: retrieval
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [task-types, evidence-pack, retrieval, context-assembly, wave-1]
depends_on: [ADR-001, ADR-002, ADR-003, GOV-002]
---

# internalCMDB — Task Type Catalog and Evidence Pack Contracts (Wave-1)

**Milestone**: m4-1 — Task-Type and Evidence Contracts Approved
**Program task**: pt-013

---

## Purpose

This document defines the supported task types for wave-1 and the evidence pack contract for each. An evidence pack contract specifies:

- What context classes are **mandatory** (must be present, task is blocked otherwise)
- What context classes are **recommended** (should be present, absence logged as warning)
- What context classes are **disallowed** (must not appear in the assembled context pack)
- The **token budget** (maximum total tokens in the evidence pack)
- The **retrieval ordering** rules (per ADR-003: deterministic first)

All downstream consumers — agents, operators, retrieval broker — must treat this catalog as the authoritative source for context assembly. No ad-hoc context expansion is permitted without a version increment to this document.

---

## Definitions

### Task Type

A bounded unit of work that can be delegated to an agent or operator. A task type determines:
- What evidence is needed
- What registry entities are in scope
- What action class applies (RC-N per ADR-004)
- What verification must follow

### Evidence Pack

A bounded, ordered, provenance-tagged collection of context items assembled for a single task run. An evidence pack is immutable once assembled for a run — it cannot be modified mid-execution.

### Context Classes

| Class code | Description |
|-----------|-------------|
| `canonical_doc` | Approved governance document (ADR, policy, runbook, dossier) |
| `registry_host` | Host record from `registry.hosts` |
| `registry_service` | Service record from `registry.services` |
| `registry_application` | Application record from `registry.applications` |
| `registry_ownership` | Ownership and RACI records |
| `evidence_artifact` | Discovery evidence artifact (from `discovery.evidence_artifact`) |
| `observed_fact` | Observed runtime state with provenance timestamp |
| `taxonomy_term` | Taxonomy classification term |
| `schema_entity` | Registry schema definition or data dictionary entry |
| `chunk_lexical` | Document chunk retrieved by lexical/full-text search |
| `chunk_semantic` | Document chunk retrieved by vector similarity (semantic fallback) |

---

## Wave-1 Supported Task Types

### TT-001 — infrastructure-audit

**Description:** Read-only audit of a host or cluster — collect facts, compare to canonical state, produce reconciliation summary.

**Risk class:** RC-1 (read-only, no writes)

**Token budget:** 8 000 tokens

| Context class | Requirement | Notes |
|--------------|-------------|-------|
| `registry_host` | **mandatory** | Target host record(s) must be present |
| `evidence_artifact` | **mandatory** | At least one discovery run artifact for the host |
| `canonical_doc` | **recommended** | Applicable runbooks and service dossiers |
| `registry_service` | **recommended** | Services observed on the target host |
| `registry_ownership` | **recommended** | Owner and responsible role |
| `observed_fact` | **recommended** | Latest observed state with provenance |
| `chunk_lexical` | **recommended** | Relevant runbook or dossier excerpts |
| `registry_application` | disallowed | Out of scope for host-level audit |
| `chunk_semantic` | disallowed | Semantic fallback not permitted for audit tasks |

**Retrieval ordering:** `registry_host` → `evidence_artifact` → `registry_service` → `canonical_doc` (lexical) → no semantic fallback

---

### TT-002 — service-health-check

**Description:** Verify current health status of a registered service against its canonical definition and observed state.

**Risk class:** RC-1 (read-only)

**Token budget:** 4 000 tokens

| Context class | Requirement | Notes |
|--------------|-------------|-------|
| `registry_service` | **mandatory** | Target service record with current state |
| `canonical_doc` | **mandatory** | Service dossier for the target service |
| `evidence_artifact` | **mandatory** | Latest health observation with timestamp |
| `registry_host` | **recommended** | Host(s) the service runs on |
| `registry_ownership` | **recommended** | Service owner role |
| `chunk_lexical` | **recommended** | Runbook excerpts for the service |
| `chunk_semantic` | disallowed | Not permitted for health checks |

**Retrieval ordering:** `registry_service` → `canonical_doc (service_dossier)` → `evidence_artifact` → `registry_host`

---

### TT-003 — registry-reconciliation

**Description:** Compare canonical registry state to observed discovery state and produce a structured diff with classification.

**Risk class:** RC-1 (read-only, produces report only — no writes)

**Token budget:** 12 000 tokens

| Context class | Requirement | Notes |
|--------------|-------------|-------|
| `registry_host` | **mandatory** | All hosts in reconciliation scope |
| `registry_service` | **mandatory** | All services in reconciliation scope |
| `evidence_artifact` | **mandatory** | Discovery artifacts for all in-scope hosts |
| `observed_fact` | **mandatory** | Observed state records with provenance |
| `canonical_doc` | **recommended** | Applicable policy packs and ADRs |
| `registry_ownership` | **recommended** | Ownership records for conflict assignment |
| `taxonomy_term` | **recommended** | Classification terms for diff categories |
| `chunk_lexical` | disallowed | Not relevant for structured reconciliation |
| `chunk_semantic` | disallowed | Not permitted for reconciliation tasks |

**Retrieval ordering:** `registry_host` + `registry_service` (parallel) → `evidence_artifact` → `observed_fact` → `canonical_doc`

---

### TT-004 — document-validation

**Description:** Validate a governance or infrastructure document against the metadata schema and taxonomy rules.

**Risk class:** RC-1 (read-only)

**Token budget:** 2 000 tokens

| Context class | Requirement | Notes |
|--------------|-------------|-------|
| `canonical_doc` | **mandatory** | The document being validated |
| `schema_entity` | **mandatory** | Metadata schema definition and permitted values |
| `taxonomy_term` | **mandatory** | Valid class tokens and domain values |
| `registry_host` | disallowed | Not relevant |
| `registry_service` | disallowed | Not relevant |
| `chunk_lexical` | disallowed | Not relevant |
| `chunk_semantic` | disallowed | Not permitted |

**Retrieval ordering:** `canonical_doc` → `schema_entity` → `taxonomy_term`

---

### TT-005 — document-authoring-assistant

**Description:** Assist a human author in drafting a new wave-1 governance or infrastructure document. Agent provides structure and validates against schema — no autonomous write.

**Risk class:** RC-2 (agent produces draft, human must review and commit)

**Token budget:** 6 000 tokens

| Context class | Requirement | Notes |
|--------------|-------------|-------|
| `canonical_doc` | **mandatory** | Relevant template(s) from `docs/templates/` |
| `schema_entity` | **mandatory** | Metadata schema and valid field values |
| `taxonomy_term` | **mandatory** | Permitted class tokens and domains |
| `registry_service` | **recommended** | Reference entity if dossier is being authored |
| `registry_host` | **recommended** | Reference entity if infra record is being authored |
| `canonical_doc` (ADR/policy) | **recommended** | Related decisions for context |
| `chunk_lexical` | **recommended** | Excerpts from related existing documents |
| `chunk_semantic` | **recommended** | Allowed only as supplementary, never primary source |

**Retrieval ordering:** `canonical_doc (template)` → `schema_entity` → `taxonomy_term` → `registry_*` → `chunk_lexical` → `chunk_semantic (supplementary)`

---

### TT-006 — infrastructure-change-planning

**Description:** Prepare a bounded change plan for a host, service, or cluster configuration change. Agent produces draft plan — no execution.

**Risk class:** RC-2 (plan output requires human approval before execution)

**Token budget:** 10 000 tokens

| Context class | Requirement | Notes |
|--------------|-------------|-------|
| `registry_host` | **mandatory** | Target host record |
| `registry_service` | **mandatory** | Services affected by the change |
| `canonical_doc` | **mandatory** | Applicable runbooks, ADRs, and policies |
| `evidence_artifact` | **mandatory** | Latest discovery state for target host/services |
| `registry_ownership` | **mandatory** | Owner and approval authority for change |
| `observed_fact` | **recommended** | Current state with provenance |
| `chunk_lexical` | **recommended** | Procedure excerpts from runbooks |
| `chunk_semantic` | disallowed | Not permitted for change planning |

**Retrieval ordering:** `registry_host` → `registry_service` → `evidence_artifact` → `canonical_doc` → `registry_ownership`

---

### TT-007 — policy-compliance-check

**Description:** Evaluate whether a system, service, or configuration complies with applicable policy packs.

**Risk class:** RC-1 (read-only, produces compliance report)

**Token budget:** 6 000 tokens

| Context class | Requirement | Notes |
|--------------|-------------|-------|
| `canonical_doc` | **mandatory** | All applicable policy_pack documents |
| `registry_host` | **mandatory** (if host compliance) | Target entity |
| `registry_service` | **mandatory** (if service compliance) | Target entity |
| `evidence_artifact` | **recommended** | Discovery evidence for observed state |
| `registry_ownership` | **recommended** | Owner record for violation assignment |
| `chunk_lexical` | **recommended** | Policy definition excerpts |
| `chunk_semantic` | disallowed | Not permitted for compliance checks |

**Retrieval ordering:** `canonical_doc (policy_pack)` → `registry entity` → `evidence_artifact`

---

## Evidence Pack Schema

An evidence pack is created per task run. The following fields are mandatory in every evidence pack record (`retrieval.evidence_pack`):

| Field | Type | Requirement |
|-------|------|-------------|
| `pack_code` | string | Unique identifier: `EP-{task_type_code}-{timestamp_iso}` |
| `task_type_code` | string | Must be one of: TT-001 through TT-007 |
| `request_scope_jsonb` | JSONB | Must include: `target_entities`, `scope_description`, `created_by` |
| `selection_rationale_text` | text | Brief statement of why items were selected |
| `token_budget` | integer | Must not exceed the task type's defined budget |
| `created_by` | string | Agent run ID or operator identifier |

Each item in `retrieval.evidence_pack_item` must include:

| Field | Type | Requirement |
|-------|------|-------------|
| `item_order` | integer | Ascending order reflecting retrieval priority |
| `entity_kind_term_id` | UUID | Must reference a valid taxonomy term |
| `inclusion_reason_text` | text | Why this item was included |
| `is_mandatory` | boolean | True if the item is in the mandatory context class |

At least one item with `is_mandatory = true` must be present. Evidence packs with zero mandatory items are invalid and must be rejected by the broker.

---

## Enforcement Rules

1. An agent may not begin execution of any wave-1 task without a completed evidence pack that satisfies this contract.
2. The retrieval broker must verify that all mandatory context classes are present before finalising the pack.
3. Disallowed context classes must be rejected at assembly time — they may not appear in the pack even if retrieved.
4. Semantic retrieval (`chunk_semantic`) is only permitted for task types where it is listed as recommended or better. For all other task types, semantic results must be discarded before pack assembly.
5. Token budgets are hard limits. Items that would exceed the budget must be excluded, with the exclusion noted in `selection_rationale_text`.
6. Evidence packs are immutable after assembly. No item may be added, removed, or reordered after the pack is created.

---

## Registry Binding

This catalog is operationalised through the following schema objects:

| Object | Schema | Role |
|--------|--------|------|
| `evidence_pack` | `retrieval` | One record per task run |
| `evidence_pack_item` | `retrieval` | Ordered collection of context items per pack |
| `document_chunk` | `retrieval` | Chunks used in `chunk_lexical` and `chunk_semantic` items |
| `taxonomy_term` | `taxonomy` | Entity kind classification for pack items |

The `task_type_code` in `evidence_pack.task_type_code` must be a value from this catalog: `TT-001` through `TT-007` for wave-1.
