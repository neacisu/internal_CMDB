---
id: GOV-007
title: internalCMDB — Policy Matrix, Risk Classes and Deny-by-Default Rules (Wave-1)
doc_class: policy_pack
domain: governance
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: security_and_policy_owner
tags: [policy-matrix, risk-classes, deny-by-default, action-governance, wave-1]
depends_on: [ADR-004, GOV-006, GOV-002]
---

# internalCMDB — Policy Matrix, Risk Classes and Deny-by-Default Rules (Wave-1)

**Milestone**: m5-1 — Policy Matrix and Risk Classes Approved
**Program task**: pt-016

---

## Purpose

This document defines the formal policy matrix for all supported wave-1 action classes. It specifies:

- What **risk class** applies to each action class (RC-1 through RC-4, per ADR-004)
- What **evidence requirements** must be met before the action can execute
- What **approval authority** is required
- What **post-execution verification** is mandatory
- What **blocking rules** apply (deny-by-default conditions)

**Deny-by-default**: any action not listed in this matrix is denied. No action class can be added to a running agent without a policy matrix update and a version increment to this document.

---

## Risk Class Definitions (ADR-004)

| Risk class | Description | Default approval surface |
|-----------|-------------|--------------------------|
| RC-1 | Read-only query, analysis, or report generation. No state change. | None required — evidence pack sufficient |
| RC-2 | Agent produces a draft, plan, or proposal. Human must review and commit. | Human review before any write |
| RC-3 | Bounded, supervised write within explicit scope. Reversible. | Named approver per scope |
| RC-4 | Bulk, structural, or high-risk infrastructure action. Potentially irreversible. | Quorum approval + pre-execution snapshot |

---

## Action Class Definitions

### AC-001 — registry-read

**Description:** Query or export data from any registry, discovery, or retrieval schema table (SELECT-only).

| Field | Value |
|-------|-------|
| Risk class | RC-1 |
| Evidence required | Valid evidence pack for the task type; no mandatory class violations |
| Approval required | None |
| Post-execution verification | None |
| Deny conditions | Evidence pack missing; task type not in supported catalog; disallowed context class present |

---

### AC-002 — document-validation-run

**Description:** Execute the metadata validator against one or more documents.

| Field | Value |
|-------|-------|
| Risk class | RC-1 |
| Evidence required | Evidence pack; canonical_doc mandatory class satisfied |
| Approval required | None |
| Post-execution verification | Validator exit code 0; no ERROR lines in output |
| Deny conditions | Validator not available; target document path outside `docs/` tree |

---

### AC-003 — registry-entity-create

**Description:** INSERT a new entity into any registry schema table.

| Field | Value |
|-------|-------|
| Risk class | RC-3 |
| Evidence required | Evidence pack; registry_ownership mandatory; canonical_doc recommended (service dossier or ADR) |
| Approval required | Named approver: registry owner role for the entity kind |
| Post-execution verification | Row exists with expected primary key; ownership record created; no constraint violation |
| Deny conditions | No approval record; approval expired; approver role not assigned for entity kind; evidence pack missing mandatory ownership class |

---

### AC-004 — registry-entity-update

**Description:** UPDATE an existing entity in any registry schema table.

| Field | Value |
|-------|-------|
| Risk class | RC-3 |
| Evidence required | Evidence pack; registry_ownership mandatory; observed_fact recommended |
| Approval required | Named approver; approval scope must name the specific entity ID |
| Post-execution verification | Updated row matches intended change; previous state captured in discovery.observed_fact |
| Deny conditions | No approval record; approval scope does not include target entity ID; approval expired; bulk UPDATE without explicit entity list |

---

### AC-005 — discovery-run

**Description:** Execute a discovery collection run against one or more hosts.

| Field | Value |
|-------|-------|
| Risk class | RC-2 |
| Evidence required | Evidence pack; registry_host mandatory; registry_ownership recommended |
| Approval required | Human review of discovery scope before run |
| Post-execution verification | CollectionRun record created with status completed; at least one EvidenceArtifact produced |
| Deny conditions | Target host not in registry; host lifecycle_term is decommissioned; no read-only constraint on discovery source |

---

### AC-006 — document-create

**Description:** Create a new governance or infrastructure document under `docs/`.

| Field | Value |
|-------|-------|
| Risk class | RC-2 |
| Evidence required | Evidence pack; canonical_doc (template) mandatory; schema_entity mandatory; taxonomy_term mandatory |
| Approval required | Human review and commit (agent produces draft only) |
| Post-execution verification | Metadata validator PASS; document committed by human author |
| Deny conditions | Template not found; metadata schema validation fails; agent attempting autonomous commit |

---

### AC-007 — document-update

**Description:** Modify an existing governance or infrastructure document.

| Field | Value |
|-------|-------|
| Risk class | RC-2 |
| Evidence required | Evidence pack; existing canonical_doc mandatory; schema_entity mandatory |
| Approval required | Human review and commit |
| Post-execution verification | Metadata validator PASS; version increment applied; git diff reviewed by owner |
| Deny conditions | Agent attempting autonomous commit; ownership field changed without explicit owner approval |

---

### AC-008 — schema-migration

**Description:** Apply a database schema migration (Alembic revision).

| Field | Value |
|-------|-------|
| Risk class | RC-4 |
| Evidence required | Evidence pack; schema_entity mandatory; canonical_doc (ADR or policy) mandatory |
| Approval required | Quorum: platform_architecture_lead + database_owner |
| Post-execution verification | Alembic version table updated; migration idempotent (can be run twice without error); rollback tested |
| Deny conditions | No quorum approval; migration modifies a schema not listed in the evidence pack scope; no rollback script present |

---

### AC-009 — agent-run-trigger

**Description:** Trigger a new AgentRun for a supported task type.

| Field | Value |
|-------|-------|
| Risk class | RC-2 |
| Evidence required | Evidence pack assembled and validated for the task type; all mandatory context classes present |
| Approval required | Human authorisation for RC-2/RC-3/RC-4 sub-actions that the run will invoke |
| Post-execution verification | AgentRun record created; evidence pack ID linked; run outcome captured |
| Deny conditions | Evidence pack has violations; task type not in supported catalog; sub-action classes deny conditions apply to any planned write |

---

### AC-010 — bulk-registry-import

**Description:** Bulk INSERT or UPSERT of registry entities from a discovery artifact or external data source.

| Field | Value |
|-------|-------|
| Risk class | RC-4 |
| Evidence required | Evidence pack; registry_ownership mandatory; evidence_artifact mandatory (source artifact) |
| Approval required | Quorum: registry_owner_role + platform_architecture_lead; pre-import snapshot required |
| Post-execution verification | Row count matches import manifest; no orphaned foreign keys; ownership records created for all new entities |
| Deny conditions | No quorum approval; no pre-import snapshot; import scope exceeds approved entity list; target schema not registry |

---

## Deny-by-Default Rules

The following conditions unconditionally deny any action, regardless of risk class:

| Rule ID | Condition | Rationale |
|---------|-----------|-----------|
| D-001 | Action class not listed in this matrix | No policy entry means no permission |
| D-002 | Evidence pack has at least one MANDATORY_MISSING violation | Mandatory context class absent — execution is epistemically unsound |
| D-003 | Evidence pack has at least one DISALLOWED_PRESENT violation | Disallowed context class in pack — context contract violated |
| D-004 | Approval record is expired | Time-bounded approval is no longer valid |
| D-005 | Approval record scope does not cover the target entity | Out-of-scope write is equivalent to no approval |
| D-006 | Agent attempts an RC-4 action without a pre-execution snapshot record | Irreversibility requires a documented recovery path |
| D-007 | Two or more deny conditions are triggered simultaneously | Additive denial — each deny condition is independent |
| D-008 | Action class requires quorum but only one approver record is present | Quorum is not satisfied by a single record |

---

## Enforcement Boundary

Policy enforcement is the responsibility of the `control.policy_matrix` Python module.  No code may bypass the `PolicyEnforcer.check()` method for any governed write path.  Read-only actions (RC-1) are exempt from approval enforcement but must still have a valid evidence pack (D-002 and D-003 still apply).

The `PolicyEnforcer` is invoked:
1. Before evidence pack assembly (task type must be supported)
2. After evidence pack assembly (D-002, D-003 validation)
3. Before any write action execution (approval check, scope check)
4. After write action execution (post-execution verification recording)
