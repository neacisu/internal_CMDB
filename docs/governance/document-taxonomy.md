---
id: doc-taxonomy-wave1
title: Wave-1 Document Taxonomy — Classes, Identifiers and Registry Binding Rules
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
approved_by: architecture_board
approved_at: 2026-03-08
tags: [taxonomy, document-classes, wave-1, governance]
binding: []
---

# Wave-1 Document Taxonomy

## Purpose

This document defines the canonical taxonomy for all platform documents in wave-1: the permitted
document classes, their identifier format, required frontmatter, and rules for binding documents
to operational registry entities.

This taxonomy is the authoritative reference for the metadata schema validator
(`src/internalcmdb/governance/metadata_validator.py`) and for all document authors.

---

## Document Class Registry

### Class A — Infrastructure & Operations

Documents that describe or govern physical and virtual infrastructure.

| Class Token | Class Name | Identifier Prefix | Registry Binding Targets |
| --- | --- | --- | --- |
| `infra_record` | Infrastructure Record | `infra-` | `registry.host`, `registry.cluster`, `registry.network_segment`, `registry.storage_asset` |
| `node_record` | Node / Host Record | `node-` | `registry.host`, `registry.host_hardware_snapshot` |
| `service_dossier` | Shared Service Dossier | `svc-` | `registry.shared_service`, `registry.service_instance` |
| `runbook` | Operational Runbook | `runbook-` | Any registry entity with `lifecycle_status` |
| `incident_record` | Incident Record | `incident-` | `registry.service_instance`, `registry.host` |

### Class B — Governance & Decisions

Documents that capture approved decisions, policies and ownership.

| Class Token | Class Name | Identifier Prefix | Registry Binding Targets |
| --- | --- | --- | --- |
| `adr` | Architecture Decision Record | `ADR-` | None (decisions reference entities, not bound to them) |
| `policy_pack` | Policy Pack | `policy-` | `governance.policy_record` |
| `ownership_matrix` | Ownership Matrix / RACI | `raci-` | All schemas (cross-cutting) |
| `change_template` | Change Template | `change-` | `governance.change_log` |
| `approval_pattern` | Approval Pattern | `approval-` | `governance.approval_record` |

### Class C — Application Definition

Documents that define a governed application before or during delivery.

| Class Token | Class Name | Identifier Prefix | Registry Binding Targets |
| --- | --- | --- | --- |
| `product_intent` | Product Intent Record | `pi-` | `registry.service_instance`, `registry.shared_service` |
| `context_boundary` | Context Boundary Record | `cb-` | `registry.cluster`, `registry.network_segment`, `registry.shared_service` |
| `domain_model` | Canonical Domain Model | `dm-` | `registry.service_instance` |
| `arch_view_pack` | Architecture View Pack | `avp-` | `registry.cluster`, `registry.service_exposure` |
| `service_contract` | Shared Service Contract | `sc-` | `registry.shared_service`, `registry.service_dependency` |
| `eng_policy` | Engineering Policy Pack | `ep-` | `registry.service_instance` |
| `repo_instructions` | Repository Instruction Layer | `ri-` | `registry.service_instance` |
| `verification_spec` | Verification Specification | `vs-` | `registry.service_instance`, `discovery.evidence_artifact` |
| `evidence_map` | Evidence Map | `em-` | `discovery.evidence_artifact`, `retrieval.evidence_pack` |
| `research_dossier` | Research Dossier | `rd-` | `registry.cluster`, `registry.shared_service` |

### Class D — Agent Governance

Documents that govern agent behavior, retrieval policies and prompt templates.

| Class Token | Class Name | Identifier Prefix | Registry Binding Targets |
| --- | --- | --- | --- |
| `agent_policy` | Agent Policy | `ap-` | `agent_control.action_request`, `governance.policy_record` |
| `retrieval_policy` | Retrieval Policy | `rp-` | `retrieval.evidence_pack` |
| `prompt_template` | Prompt Template | `pt-` | `agent_control.prompt_template_registry` |
| `task_brief` | Task Brief Template | `tb-` | `agent_control.agent_run` |

### Class E — Observable Operations

Documents produced as artifacts of operational execution.

| Class Token | Class Name | Identifier Prefix | Registry Binding Targets |
| --- | --- | --- | --- |
| `operational_declaration` | Operational Declaration | `od-` | `governance.approval_record` |
| `reconciliation_report` | Reconciliation Report | `rr-` | `discovery.reconciliation_result` |
| `data_quality_report` | Data Quality Report | `dqr-` | `discovery.collection_run` |
| `readiness_review` | Readiness Review | `rrv-` | `governance.change_log` |

---

## Identifier Format

All document identifiers follow this grammar:

```
<prefix><domain-slug>-<sequence-or-name>

Examples:
  ADR-001                          (adr, sequence)
  svc-postgresql-17                (service_dossier, slug)
  runbook-postgres-backup-restore  (runbook, slug)
  policy-write-approval-model      (policy_pack, slug)
  pi-internalcmdb-health-api       (product_intent, slug)
```

Rules:
- Identifiers are lowercase except for `ADR-` prefix (historically uppercase).
- Sequence numbers are zero-padded to 3 digits for `adr` class.
- Slug components use hyphens only (no underscores, no spaces).
- Domain slug mirrors the `domain` frontmatter field.
- Identifiers are immutable once assigned. Superseded documents use `superseded_by` frontmatter.

---

## Registry Binding Rules

### Binding format in frontmatter

```yaml
binding:
  - entity_type: registry.host
    entity_id: "<uuid>"
    relation: describes
  - entity_type: registry.shared_service
    entity_id: "<uuid>"
    relation: governs
```

Permitted `relation` values:

| Relation | Meaning |
| --- | --- |
| `describes` | Document is the canonical description of the entity |
| `governs` | Document defines policy or rules that apply to the entity |
| `references` | Document references the entity without being its canonical description |
| `evidence_for` | Document serves as evidence for the entity's state or properties |
| `supersedes` | Document replaces a prior document bound to the same entity |

### Binding requirements by class

| Class Token | Binding Required? | Notes |
| --- | --- | --- |
| `infra_record` | Required | Must bind to at least one `registry.*` entity |
| `node_record` | Required | Must bind to `registry.host` |
| `service_dossier` | Required | Must bind to `registry.shared_service` |
| `adr` | Not required | ADRs reference entities descriptively, not as registy bindings |
| `policy_pack` | Required if entity-specific | Optional for platform-wide policies |
| `runbook` | Required | Must bind to the entity the runbook operates on |
| `product_intent` | Required | Must bind to `registry.service_instance` after delivery |
| `operational_declaration` | Required | Must bind to `governance.approval_record` |
| `reconciliation_report` | Required | Must bind to `discovery.reconciliation_result` |

### Document status lifecycle

All documents carry a `status` field with the following permitted values:

| Status | Meaning |
| --- | --- |
| `draft` | Under authoring, not yet reviewed |
| `in-review` | Submitted for review by approver class |
| `approved` | Reviewed and approved by required approver(s) |
| `superseded` | Replaced by a newer document (`superseded_by` required) |
| `deprecated` | No longer applicable; retained for audit history |
| `rejected` | Review completed, document was not approved |

---

## Cross-Reference Conventions

Within documents, use the following reference link syntax to create traceable links:

| Reference Type | Syntax | Example |
| --- | --- | --- |
| Another document | `[[doc:DOC-ID]]` | `[[doc:ADR-001]]` |
| Registry entity | `[[entity:table:identifier]]` | `[[entity:registry.host:orchestrator]]` |
| Taxonomy term | `[[term:TERM-TOKEN]]` | `[[term:postgresql]]` |
| Evidence artifact | `[[evidence:ARTIFACT-ID]]` | `[[evidence:ea-trust-surface-orchestrator-20260308]]` |
| Collection run | `[[run:RUN-ID]]` | `[[run:aa5c8b96]]` |

The metadata validator checks that `[[doc:ID]]` references resolve to existing documents when
validation is run in `--strict` mode.

---

*Source: blueprint_platforma_interna.md §10, pt-004 deliverable, approved 2026-03-08*
