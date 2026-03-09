---
id: metadata-schema-v1
title: Platform Document Metadata Schema — Frontmatter Rules and Link Conventions
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
approved_by: architecture_board
approved_at: 2026-03-08
tags: [metadata, frontmatter, schema, validation, wave-1]
binding:
  - entity_type: docs.document
    entity_id: metadata-schema-v1
    relation: governs
---

# Platform Document Metadata Schema v1

## Purpose

This document defines the versioned metadata contract for all platform documents. It specifies
mandatory, recommended and optional frontmatter fields, their types and validation rules.

The authoritative validator is `src/internalcmdb/governance/metadata_validator.py`.
This specification is the source of truth; the validator implements it.

---

## Frontmatter Schema

All platform documents must begin with a YAML frontmatter block delimited by `---`.

### Mandatory Fields

All documents **must** include these fields. Validation fails without them.

| Field | Type | Permitted Values | Notes |
| --- | --- | --- | --- |
| `id` | string | Matches identifier grammar (see taxonomy) | Unique within the repository |
| `title` | string | Free text, ≥ 10 chars | Descriptive, human-readable |
| `doc_class` | string | See Class Token column in document-taxonomy.md | Must be a known class token |
| `domain` | string | See domains.txt (taxonomy domains) | Lowercase, hyphenated |
| `version` | string | `"N.M"` (quoted, semantic) | e.g. `"1.0"`, `"2.3"` |
| `status` | string | `draft`, `in-review`, `approved`, `superseded`, `deprecated`, `rejected` | |
| `created` | date | `YYYY-MM-DD` | Date of initial authoring |
| `updated` | date | `YYYY-MM-DD` | Must be ≥ `created` |
| `owner` | string | A valid platform role token | e.g. `platform_architecture_lead` |

### Recommended Fields

Strongly recommended for governance and retrieval quality. Documents without these generate
warnings during validation.

| Field | Type | Notes |
| --- | --- | --- |
| `approved_by` | string | Role or name of approver |
| `approved_at` | date | Date approval was granted |
| `tags` | list[string] | Lowercase, hyphenated tokens for retrieval filtering |
| `binding` | list[object] | Registry entity bindings (see format below) |
| `related_adrs` | list[string] | IDs of related ADRs, e.g. `[ADR-001, ADR-003]` |

### Optional Fields

May be included when applicable. Validator will not warn on absence.

| Field | Type | Notes |
| --- | --- | --- |
| `superseded_by` | string | ID of the document that replaces this one |
| `depends_on` | list[string] | Document IDs that must exist and be approved first |
| `evidence_artifacts` | list[string] | IDs of supporting evidence artifacts |
| `review_by` | date | Target review-by date for expiring documents |
| `doc_type` | string | Sub-type within the doc_class (free text) |

---

## Binding Object Schema

The `binding` list items follow this schema:

```yaml
binding:
  - entity_type: "<schema>.<table>"   # required: e.g. registry.host
    entity_id: "<string>"             # required: UUID or stable slug identifier
    relation: "<relation>"            # required: describes | governs | references |
                                      #           evidence_for | supersedes
```

Validation rules:
- `entity_type` must match `schema.table` from the approved table list.
- `relation` must be one of the five permitted values.
- `entity_id` format is not validated against the live database in default mode;
  use `--check-db` flag in the validator for live resolution.

---

## Platform Role Tokens

The `owner` and `approved_by` fields must use one of these canonical role tokens:

```
executive_sponsor
architecture_board
platform_program_manager
platform_architecture_lead
platform_engineering_lead
data_registry_owner
discovery_owner
security_and_policy_owner
sre_observability_owner
domain_owners
```

Named individuals (e.g. `Alex Neacsu`) are accepted in `approved_by` as an alternative.

---

## Validation Rules Summary

The validator enforces these rules at two levels:

### Default validation (no flags)

1. All mandatory fields are present.
2. `doc_class` is a known class token (from document-taxonomy.md).
3. `domain` is a known taxonomy domain.
4. `version` matches pattern `"N.M"`.
5. `status` is a permitted status value.
6. `created` ≤ `updated` (chronological order enforced).
7. `owner` is a permitted role token or named individual.
8. If `superseded_by` is present, `status` must be `superseded`.
9. `binding[].relation` must be a permitted relation value.
10. `binding[].entity_type` must match `schema.table` format.

### Strict validation (`--strict` flag)

Additional rules:
11. `approved_by` and `approved_at` are present when `status` is `approved`.
12. `tags` list is non-empty.
13. `binding` list is non-empty for classes that require binding
    (see binding requirements in document-taxonomy.md).
14. `[[doc:ID]]` cross-references resolve to files in the `docs/` tree.
15. `related_adrs` entries resolve to existing ADR files.

---

## Permitted Taxonomy Domains

The `domain` field must be one of these values (derived from `taxonomy.taxonomy_domain`
seed data — 22 domains):

```
platform-foundations    infrastructure          networking
storage                 security                observability
discovery               registry                retrieval
agent-control           governance              taxonomy
docs                    deployment              postgresql
ai-infrastructure       llm-runtime             shared-services
applications            development             operations
compliance
```

---

## Complete Frontmatter Example

```yaml
---
id: svc-postgresql-17
title: Shared Service Dossier — PostgreSQL 17 (internalcmdb-postgres)
doc_class: service_dossier
domain: postgresql
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: data_registry_owner
approved_by: architecture_board
approved_at: 2026-03-08
tags: [postgresql, shared-service, registry, wave-1]
binding:
  - entity_type: registry.shared_service
    entity_id: "postgresql-17-internalcmdb"
    relation: describes
related_adrs: [ADR-002]
evidence_artifacts: [ea-trust-surface-orchestrator-20260308]
---
```

---

## Malformed Example (validator rejects)

```yaml
---
id: my doc          # INVALID: spaces in id
title: Short        # INVALID: title < 10 chars
doc_class: thing    # INVALID: unknown class token
domain: MyDomain    # INVALID: uppercase and not in permitted domains
version: 1          # INVALID: not quoted, not "N.M" format
status: active      # INVALID: not a permitted status value
created: 08/03/2026 # INVALID: not YYYY-MM-DD format
updated: 2026-03-01 # INVALID: updated < created
owner: someone      # INVALID: not a role token
---
```

---

*Source: blueprint_platforma_interna.md §10, pt-005 deliverable, approved 2026-03-08*
