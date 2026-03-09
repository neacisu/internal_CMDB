---
id: GOV-005
title: internalCMDB — Template Pack Author Guide
doc_class: policy_pack
domain: docs
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_program_manager
tags: [templates, authoring, guidance, wave-1]
depends_on: [GOV-003, GOV-004, GOV-002]
---

# internalCMDB — Template Pack Author Guide

**Milestone**: m1-2 — Taxonomy and Metadata Contract Approved
**Program task**: pt-006

---

## Purpose

This guide explains how to use the templates in this directory to create, validate, and submit wave-1 canonical documents. Every new document must start from one of these templates — original freeform authoring is not permitted for governed document classes.

---

## Templates Available

| Template file | Document class token | When to use |
| --- | --- | --- |
| `adr-template.md` | `adr` | Architectural or governance decisions |
| `runbook-template.md` | `runbook` | Operational procedures and recovery steps |
| `service-dossier-template.md` | `service_dossier` | Canonical record for an infrastructure service |
| `research-dossier-template.md` | `research_dossier` | Investigation, feasibility, spike or PoC outcomes |
| `policy-pack-template.md` | `policy_pack` | Platform or domain policies and rules |
| `verification-spec-template.md` | `verification_spec` | Test plans, acceptance criteria and evidence maps |
| `product-intent-template.md` | `product_intent` | Application definition and requirements scope |

---

## How to Create a New Document

### Step 1 — Copy the right template

```bash
cp docs/templates/<template-name>.md docs/<target-dir>/<document-slug>.md
```

Do not create a document file from scratch. Always copy from the template.

### Step 2 — Fill in the frontmatter

Edit the frontmatter block at the top of the file. Required fields are marked with `# REQUIRED`. Optional fields are marked with `# OPTIONAL`.

**Mandatory fields (all templates):**

| Field | Type | Example |
| --- | --- | --- |
| `id` | string | `ADR-006`, `SVC-001`, `POL-003` |
| `title` | string | Short unambiguous title |
| `doc_class` | token | See table above |
| `domain` | string | See permitted domain list below |
| `version` | string | `"1.0"` (quoted) |
| `status` | token | `draft` → `in-review` → `approved` |
| `created` | date | `2026-03-15` |
| `updated` | date | `2026-03-15` |
| `owner` | role token | See permitted role tokens below |

**Permitted `domain` values:**
`platform-foundations`, `infrastructure`, `networking`, `storage`, `security`,
`observability`, `discovery`, `registry`, `retrieval`, `agent-control`,
`governance`, `taxonomy`, `docs`, `deployment`, `postgresql`, `ai-infrastructure`,
`application`, `compute`, `backup`, `identity`, `audit`, `logging`

**Permitted `owner` role tokens:**
`executive_sponsor`, `architecture_board`, `platform_program_manager`,
`platform_architecture_lead`, `platform_engineering_lead`, `data_registry_owner`,
`discovery_owner`, `security_and_policy_owner`, `sre_observability_owner`, `domain_owners`

### Step 3 — Fill in the content sections

Each template has sections with guidance comments (lines starting with `<!-- `). Replace guidance comments with real content. Do not leave guidance comments in your final document.

### Step 4 — Validate the document

Run the metadata validator before submitting for review:

```bash
# From the repository root
PYTHONPATH=src .venv/bin/python -m internalcmdb.governance.metadata_validator docs/path/to/your-doc.md -v
```

Or use the convenience script:

```bash
./scripts/validate_docs.sh docs/path/to/your-doc.md
```

The document must report `✓ PASS` with zero errors before submission.

For strict mode (checks cross-references and binding targets):

```bash
./scripts/validate_docs.sh --strict docs/path/to/your-doc.md
```

### Step 5 — Submit for review

Set `status: in-review` in the frontmatter and open a pull request. The reviewer for your document is determined by the `owner` role token:

| Owner role token | Reviewer |
| --- | --- |
| `architecture_board` | Architecture Board chair |
| `platform_program_manager` | Program Manager |
| `platform_architecture_lead` | Platform Architecture Lead |
| `platform_engineering_lead` | Platform Engineering Lead |
| `data_registry_owner` | Data Registry Owner |
| `security_and_policy_owner` | Security & Policy Owner |
| `sre_observability_owner` | SRE / Observability Owner |

### Step 6 — Approval

After review, the designated owner sets `status: approved` and merges the PR. No document may be acted upon operationally until its status is `approved`.

---

## Document IDs

Use the following ID prefix conventions:

| Prefix | Class |
| --- | --- |
| `ADR-NNN` | `adr` |
| `SVC-NNN` | `service_dossier` |
| `RUN-NNN` | `runbook` |
| `RES-NNN` | `research_dossier` |
| `POL-NNN` | `policy_pack` |
| `GOV-NNN` | Governance documents |
| `APP-NNN` | `product_intent` |
| `VER-NNN` | `verification_spec` |
| `PLAN-NNN` | Plans |
| `BLUEPRINT-NNN` | `arch_view_pack` |

NNN is a zero-padded three-digit integer. Assign the next available number in sequence.

---

## Cross-Reference Syntax

Use these link formats inside document bodies:

- Reference another document: `[[doc:ADR-001]]`
- Reference a registry entity: `[[entity:registry.hosts:hostname]]`
- Reference a service: `[[entity:registry.services:service_name]]`

---

## Common Mistakes

| Mistake | Correct approach |
| --- | --- |
| Using `status: accepted` | Use `status: approved` |
| Freeform `owner: "Alex"` | Use canonical role token: `owner: platform_architecture_lead` |
| Missing `created` or `updated` | Both are mandatory — set to authoring date |
| `version: 1.0` (unquoted) | Must be quoted: `version: "1.0"` |
| `doc_class: policy` | Use canonical token: `doc_class: policy_pack` |
| Leaving guidance comments in final doc | Remove all `<!-- ... -->` guidance comments |

---

## Validation Reference

The validator is at `src/internalcmdb/governance/metadata_validator.py`.
Exit codes: `0` = all valid, `1` = errors found, `2` = usage error.

Validation rules enforced:
- All 9 mandatory frontmatter fields present
- `doc_class` is a known class token
- `domain` is a known domain value
- `version` matches `N.N` pattern
- `status` is a permitted status value
- `created` and `updated` are valid ISO dates
- `owner` is a canonical role token (warning if unknown)
- `id` matches the `[A-Za-z0-9][A-Za-z0-9\-]*` pattern
- Referenced doc IDs in `[[doc:ID]]` links follow the ID pattern
