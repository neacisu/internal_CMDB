---
id: GOV-002
title: internalCMDB — Agent Operating Rules, Definition of Done and Wave-1 Sequencing Gates
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_program_manager
tags: [operating-rules, definition-of-done, sequencing, agent-governance, wave-1]
depends_on: [ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, GOV-001]
---

## internalCMDB — Agent Operating Rules, Definition of Done and Wave-1 Sequencing Gates

**Milestone**: m0-2 — Execution Governance Operationalized
**Program task**: pt-003
**Status**: approved
**Supersedes**: (none — first version)

---

## Purpose

This document establishes the executable governance baseline for all implementation work in the internalCMDB program. Every agent, engineer, and reviewer working on any task derived from the implementation plan must comply with the rules defined here.

The three components of this document are:

1. **Mandatory Operating Rules** — non-negotiable constraints governing agent behaviour
2. **Definition of Done (DoD)** — per-artifact-type completion criteria used to gate status promotion
3. **Wave-1 Sequencing Gates** — dependency ordering rules that block work packages between epics

These rules apply to all implementation agents and are stable for the duration of wave-1. Changes require a new version of this document and re-approval by the Program Manager and Architecture Board.

---

## Section 1: Mandatory Operating Rules for Agents

The following 13 rules are non-negotiable. Any task where one or more rules cannot be satisfied must be blocked and escalated, not improvised around.

### Rule 1 — No assumptions when canonical data is missing

The agent does not fill gaps with guesses. If canonical data is missing, bindings are absent, ownership mappings are not confirmed, or write approval is not present, the correct action is to report the gap and halt execution on that segment — not to invent a substitute value.

### Rule 2 — Context is loaded in structured-first order

For every task, context must be assembled in this order:

1. Relevant canonical documents (approved ADRs, governance docs, policies)
2. Registry entities and relationships (PostgreSQL structured queries)
3. Observed state with stated provenance
4. Applicable policy rules
5. Lexical/semantic retrieval (supplementary only — never primary)

Semantic retrieval results are contextual support. Operational truth and binding decisions come from canonical approved sources and structured registry queries only.

### Rule 3 — Semantic retrieval is never a source of truth

Results from semantic/lexical search are supplementary context. No decision that affects registry state, written artifacts, infrastructure configuration, or policy compliance may be grounded solely in semantic retrieval output.

### Rule 4 — No direct writes

Any operation that modifies files, infrastructure configuration, registry state, or runtime resources must be mediated through the action broker and the approval chain appropriate to the risk class (RC-1 through RC-4 per ADR-004). No direct write paths bypass this constraint.

### Rule 5 — Every run leaves an audit trail

Each run must have:

- input scope declaration
- context pack used (documents + entities referenced)
- evidence extracted
- decisions taken
- approvals received (reference + timestamp)
- actions executed
- final verification results

### Rule 6 — Minimum sufficient scope

If a task targets a service, host, application, or document package, the context must be scoped to that target. Do not load large shared documents or broad entity sets "for safety". Scope sprawl introduces decision risk.

### Rule 7 — Verify before building

If existing assets in the repository partially satisfy a need, the agent must reuse, normalise, or extend them in a disciplined way. Duplicating functionality is not permitted.

### Rule 8 — Separate facts from interpretation

Every output must clearly distinguish:

- **Canonical fact**: sourced from an approved document or registry record
- **Observed fact**: sourced from runtime/discovery with stated provenance
- **Bounded inference**: derived from facts with assumptions stated
- **Recommendation**: interpretive suggestion requiring owner approval before acting

### Rule 9 — No task closure without verification

Each deliverable must be validated before the task status may be set to `completed`. Acceptable verification evidence:

- automated tests that pass
- structured query/consistency checks against the registry
- formal review sign-off by the artifact owner

The verification method must match the artifact type (see Section 2).

### Rule 10 — Explicit conflict escalation

When canonical state and observed state conflict, the agent does not choose arbitrarily. The conflict must be:

1. marked with type (`canonical-vs-observed`, `ownership-ambiguity`, `policy-conflict`)
2. classified by severity
3. escalated per the escalation model in [[doc:GOV-001]]

### Rule 11 — The plan is read-only

The implementation plan (`PLAN-001`) is read-only for all implementation agents. The only permitted modification is updating the YAML `status` field on execution objects from `in-progress` to `completed` — and only after the completion criteria in Section 2 are fully satisfied.

### Rule 12 — Status progression is binary and verified

All execution objects start as `in-progress`. They may only be changed to `completed` after 100% correct and 100% complete implementation verified against the DoD for the artifact type. Partial completion is not recorded as completed.

### Rule 13 — Scope boundaries are enforced

The agent must not rewrite, extend, or modify acceptance criteria, sequencing rules, task descriptions, or scope definitions in the plan. If a task's scope is ambiguous or insufficient, the ambiguity must be escalated — not resolved by the agent unilaterally.

---

## Section 2: Definition of Done by Artifact Type

The following criteria must all be satisfied before an artifact is considered complete and its task status can be set to `completed`.

### DoD-A: Architecture Decision Record (ADR)

| Criterion | Requirement |
| --- | --- |
| Frontmatter | All mandatory fields present and valid per metadata-schema |
| Structure | Context → Decision → Alternatives → Consequences sections present |
| Decision statement | Single unambiguous sentence naming what is decided |
| Alternatives | At least one rejected alternative with rejection rationale |
| Consequences | At least one binding rule derived from the decision |
| Registry binding | `binding` field references the affected registry target (or explicitly empty with rationale) |
| Validation | `metadata_validator.py` reports PASS |
| Review | Architecture Board owner has reviewed |
| Status | `status: approved` set only after review |

### DoD-B: Policy Document (policy_pack / ownership_matrix)

| Criterion | Requirement |
| --- | --- |
| Frontmatter | All mandatory fields present and valid |
| Coverage | Each rule is stated in imperative form ("must", "must not", "may") |
| Owner | `owner` field maps to a canonical role token |
| Role tokens | All role references use canonical tokens from the permitted list |
| Escalation binding | Policy must reference the escalation model in GOV-001 or define a local escalation path |
| Validation | `metadata_validator.py` reports PASS |
| Review | Designated owner role has reviewed and approved |

### DoD-C: Database Schema / Migration

| Criterion | Requirement |
| --- | --- |
| Migration file | Alembic revision file present with descriptive message |
| Forward migration | `upgrade()` function complete and idempotent |
| Backward migration | `downgrade()` function complete |
| Constraints | PK, FK, NOT NULL, CHECK constraints match approved logical model |
| SQLAlchemy model | ORM model updated to match schema |
| Test | At least one test verifying the model can be instantiated |
| Lint/types | ruff + mypy strict pass with zero issues |
| Live verification | Migration runs successfully against the internalCMDB PostgreSQL instance |

### DoD-D: Python Module / Loader / Service

| Criterion | Requirement |
| --- | --- |
| Module structure | Correct `__init__.py`, proper package hierarchy |
| Types | All public functions have complete type annotations |
| Lint | `ruff check` passes with zero errors |
| Format | `ruff format --check` passes |
| Types | `mypy --strict` passes with zero issues |
| Tests | At least one unit test or integration test per public function |
| Test pass | All tests green |
| Coverage | New code covered at ≥ 80% |
| No hardcoded secrets | No credentials, connection strings, or tokens in source |

### DoD-E: Template / Governance Document

| Criterion | Requirement |
| --- | --- |
| Frontmatter | All mandatory fields present and valid per metadata-schema |
| Skeleton sections | All required sections are present (even if with placeholder guidance) |
| Author guidance | Each section has brief guidance on what content is expected |
| Example | At least one minimal complete example is included |
| Validation | Created from template and validated by `metadata_validator.py` reports PASS |
| Review | Document owner or program manager has reviewed |

### DoD-F: Script / CLI Tool

| Criterion | Requirement |
| --- | --- |
| Runnable | Script executes without error in the project `.venv` |
| Help text | `--help` or usage message present |
| Exit codes | 0 = success, non-zero = failure (documented) |
| Lint/types | ruff + mypy strict pass |
| Security | No hardcoded credentials, no shell injection paths, no SSRF risks |
| Tested | At least one smoke test or documented manual verification run |

### DoD-G: Runbook / Operational Procedure

| Criterion | Requirement |
| --- | --- |
| Frontmatter | All mandatory fields including `domain`, `owner`, `status: approved` |
| Trigger | Clear description of when the runbook applies |
| Prerequisites | List of required access, tools, and context before starting |
| Steps | Numbered steps with expected outcomes per step |
| Rollback | At least one rollback/recovery path defined |
| Verification | Final verification step that confirms success |
| Validation | `metadata_validator.py` reports PASS |

---

## Section 3: Wave-1 Sequencing Gates

The following dependency rules govern the ordering of epics and work packages in wave-1. No work package may begin until its gate conditions are satisfied.

### Gate G-0: Epic-0 Exit Gate → Unlocks all other epics

**Conditions (all required):**

- [ ] ADR-001 through ADR-005 are present, pass metadata validation, and have `status: approved`
- [ ] `docs/ownership-matrix.md` has escalation model and approval authority sections
- [ ] `docs/governance/operating-rules.md` (this document) is approved
- [ ] All governance documents pass `metadata_validator.py`

**What G-0 unlocks:** Epic-1, Epic-2, Epic-3 (may run in parallel once G-0 is satisfied)

---

### Gate G-1: Epic-1 Exit Gate → Unlocks templated document authoring

**Conditions (all required):**

- [ ] `docs/governance/document-taxonomy.md` is approved
- [ ] `docs/governance/metadata-schema.md` is approved
- [ ] `docs/governance/operating-rules.md` is approved
- [ ] `src/internalcmdb/governance/metadata_validator.py` passes ruff + mypy strict; exit code 0 on real wave-1 docs
- [ ] Template pack at `docs/templates/` exists with at least `adr`, `runbook`, `service_dossier`, and `research_dossier` templates
- [ ] At least one document per class created from a template is validated by the validator without errors

**What G-1 unlocks:** Large-scale document authoring; agent retrieval contracts; indexing contracts

---

### Gate G-2: Epic-2 Exit Gate → Unlocks Epic-4, Epic-5

**Conditions (all required):**

- [ ] Registry schema Alembic migrations are committed and tested
- [ ] All 39+ registry tables have ORM models with type annotations
- [ ] At least one host record, one service record, and one application record exist in the live registry
- [ ] `ruff check` + `mypy --strict` pass on all registry models
- [ ] Schema is reviewed against the approved logical model from pt-007

**What G-2 unlocks:** Epic-4 (retrieval broker), Epic-5 (agent control plane)

---

### Gate G-3: Epic-3 Exit Gate → Unlocks Epic-4 semantic path

**Conditions (all required):**

- [ ] SSH discovery loader is operational and populates `registry.hosts` and `registry.services`
- [ ] At least one full discovery run has been executed and results are in the registry
- [ ] Discovery results have provenance records in `evidence` schema
- [ ] `ruff check` + `mypy --strict` pass on all discovery code
- [ ] Reconciliation report shows canonical vs observed state with no unclassified conflicts

**What G-3 unlocks:** Epic-4 deterministic retrieval path; Epic-8 enrichment loaders

---

### Gate G-4: Epic-4 Exit Gate → Unlocks Epic-5 write path

**Conditions (all required):**

- [ ] Retrieval broker resolves structured queries before any semantic fallback
- [ ] Evidence packs are produced with at least: source, timestamp, confidence, and binding reference
- [ ] Retrieval policy is documented and enforced (no start from semantic when structured data exists — ADR-003)
- [ ] Token budget policy is defined and enforced in the broker
- [ ] Integration tests verify: exact match → metadata → lexical → semantic pipeline order

**What G-4 unlocks:** Epic-5 (write approval and action broker)

---

### Gate G-5: Epic-5 Exit Gate → Unlocks pilot Epic-14

**Conditions (all required):**

- [ ] Action broker mediates all write operations (no direct write paths exist)
- [ ] All four risk classes (RC-1 through RC-4 per ADR-004) have defined approval handlers
- [ ] Deny-by-default enforced: all unsupported write paths return an explicit rejection
- [ ] Audit log entry produced for every action request (approved, denied, or pending)
- [ ] Integration test: a write attempt without approval is rejected and logged

**What G-5 unlocks:** Epic-14 (pilot validation)

---

### Sequencing Dependency Map (summary)

```text
Epic-0 (Governance) ──[G-0]──► Epic-1 (Documents)  ──[G-1]──► Authoring & Indexing
                     │
                     ├──[G-0]──► Epic-2 (Registry)   ──[G-2]──► Epic-4 (Retrieval)
                     │                                │
                     └──[G-0]──► Epic-3 (Discovery)  ──[G-3]──► Epic-4 semantic path
                                                                │
                                              Epic-4 ──[G-4]──► Epic-5 (Control)
                                                                │
                                              Epic-5 ──[G-5]──► Epic-14 (Pilot)
```

---

## Section 4: Handoff Format Requirements

Every task handoff to an agent must include the following minimum set of fields. Missing any field is grounds for the agent to reject the handoff and request a complete one.

### Minimum Handoff Format

```markdown
## Handoff: <task-id> — <task-name>

**Purpose**: What must change or be produced and why this task exists.

**In Scope**: What is explicitly within the agent's responsibility.

**Out of Scope**: What the agent must not extend or touch.

**Inputs**:
- Canonical documents: [list with doc IDs]
- Registry entities: [schema.table or entity type]
- Existing assets: [file paths to reuse/extend]
- Policy constraints: [ADR/policy references]

**Required Outputs**:
- [file path — artifact type — DoD reference]

**Constraints**:
- Truth model: [canonical / observed / desired]
- Approval needed: [RC class per ADR-004]
- Non-goals: [explicit scope exclusions]

**Verification**:
- [test / query / review check that confirms completion]

**Escalation Conditions**:
- [what ambiguity or conflict blocks and must be escalated]
```

### Mandatory Handoff Rules

1. If the task modifies the data model, the handoff must include the impact on retrieval, ingestion, and audit.
2. If the task modifies retrieval, the handoff must include affected task types and the token budget policy.
3. If the task modifies policy or approvals, the handoff must include deny paths, exceptions, and audit expectations.
4. If the task targets the pilot, the handoff must include all shared service dependencies and acceptance checks.
5. Every handoff must remind the agent that the plan is read-only and the only permitted change is `status: in-progress` → `status: completed` after verified completion.

---

## Section 5: Status Progression Rules

The following rules govern when and how execution object statuses may change in the implementation plan.

| Transition | Condition | Who may approve |
| --- | --- | --- |
| `in-progress` → `completed` | All DoD criteria for the artifact type are satisfied AND verification evidence exists | Implementing agent + owner review |
| `completed` → `in-progress` | A defect requiring rework is discovered after closure | Program Manager must approve regression |
| `in-progress` → `blocked` | A gate condition cannot be met or a conflict requires escalation | Implementing agent reports; Program Manager acknowledges |
| `blocked` → `in-progress` | Blocking condition resolved and documented | Owner of blocking artifact |

### Prohibited status transitions

- Marking a task `completed` before all DoD criteria are met
- Marking a task `completed` without verification evidence
- Modifying task descriptions, acceptance criteria, or scope definitions (any role)
- Skipping a gate without explicit written approval from the Architecture Board

---

## Relation to Other Documents

| Document | Relation |
| --- | --- |
| [[doc:ADR-001]] | Defines truth model — canonical/observed/desired separation |
| [[doc:ADR-002]] | PostgreSQL as system of record for all registry data |
| [[doc:ADR-003]] | Deterministic-first retrieval ordering (Rule 2, Rule 3) |
| [[doc:ADR-004]] | Write approval model (Rule 4) |
| [[doc:ADR-005]] | Rollout discipline (Gate verification requirements) |
| [[doc:GOV-001]] | Ownership matrix and escalation model (Rule 10, Rule 11) |
| [[doc:GOV-003]] | Document taxonomy (DoD-E, DoD-G artifact classification) |
| [[doc:GOV-004]] | Metadata schema (DoD-A, DoD-B, DoD-E frontmatter requirements) |
| [[doc:PLAN-001]] | Implementation plan referencing these rules as execution baseline |
