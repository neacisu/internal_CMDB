---
id: ADR-005
title: Rollout Discipline — Repeatable, Git-Versioned and Evidence-Verified Deployment Model
status: approved
date: 2026-03-08
created: 2026-03-08
updated: 2026-03-08
deciders:
  - name: Alex Neacsu
    role: Architecture Board
    approved_at: 2026-03-08
  - name: Alex Neacsu
    role: Platform Program Manager
    approved_at: 2026-03-08
doc_class: adr
domain: platform-foundations
version: "1.0"
owner: platform_program_manager
binding: []
tags: [rollout, deployment, repeatability, evidence-chain, wave-1]
---

# ADR-005 — Rollout Discipline: Repeatable, Git-Versioned, Verified Deployment

## Status

**Accepted** — 2026-03-08, Alex Neacsu (Architecture Board + Platform Program Manager)

---

## Context

The platform delivers infrastructure changes, schema migrations, configuration updates and
application deployments repeatedly across a lifecycle. Without a disciplined rollout model:

- deployments become person-dependent knowledge not captured in code or documentation;
- rollbacks are improvised and untested;
- promotion between environments has no governance gates;
- post-deploy verification is informal or absent;
- audit evidence of what was deployed, when and who approved it is incomplete.

The platform must treat every deployment as a governed, auditable, reproducible operation.

---

## Decision

**All platform deployments must follow a seven-phase rollout model. No change may be considered
complete without evidence of: versioned artifact, explicit approval, verified post-deploy state
and registry reconciliation. Manual-only deployments that leave no git trace are forbidden.**

### Seven-phase rollout model

```
Phase 1 — Author & Version
  └── Changes authored locally in IDE
  └── Committed to git with descriptive message following conventional commits
  └── Linked to the task/milestone that drives the change

Phase 2 — Validation (pre-deploy)
  └── ruff check + ruff format (Python)
  └── mypy --strict (Python)
  └── Alembic migration dry-run (schema changes)
  └── Unit + integration tests pass
  └── Pre-commit hooks pass

Phase 3 — Approval (RC-class per ADR-004)
  └── Action request created with explicit scope and expiry
  └── Approval record created by eligible role
  └── Scope review confirms no unintended blast radius

Phase 4 — Deploy
  └── Executed via approved tooling (Docker Compose, Alembic, shell scripts)
  └── No manual file editing directly on target host outside of approved runbook steps
  └── Execution logged with start time, deployer identity, artifact version

Phase 5 — Post-deploy verification
  └── Smoke tests or health checks executed
  └── Registry row counts verified (for schema migrations)
  └── Service endpoints confirmed reachable
  └── Evidence artifact recorded in discovery.evidence_artifact

Phase 6 — Registry reconciliation
  └── Observed state updated via discovery loader run
  └── New facts compared against canonical state
  └── Drift findings raised if any

Phase 7 — Approval closure & change log entry
  └── Approval record updated with outcome
  └── governance.change_log entry created
  └── governance.approval_record.post_execution_verification completed
```

### Rollback requirements

Every deployable change class must have a documented rollback path before deployment is approved:

| Change Class | Rollback Mechanism |
|---|---|
| Schema migration | Alembic downgrade to previous revision; data-loss risk assessed before approval |
| Docker Compose config | Previous version in git; `docker compose up` with previous file |
| Python package update | `pip install` pinned previous version; pyproject.toml reverted |
| SSL certificate / TLS | Backup certificate stored; traefik config rollback in git |
| Discovery loader | Re-run previous loader version; duplicate handling prevents data corruption |

### Evidence chain requirements

A deployment is considered evidenced when all of the following exist:

1. **Artifact**: git commit SHA or container image digest
2. **Approval**: `governance.approval_record` record ID
3. **Execution log**: timestamp + deployer + exit code
4. **Post-deploy verification**: health check evidence or smoke test output
5. **Change log entry**: `governance.change_log` record with artifact → approval → outcome links

---

## Alternatives Considered

### Alt A — Ad-hoc deployment (SSH in, run commands, document later)
Fastest for individual operations. **Rejected**: creates undocumented operational state,
produces no evidence chain, makes rollback improvised and risky, violates audit requirements.

### Alt B — Full CI/CD pipeline for all changes
Maximum automation and traceability. **Deferred** (not rejected): full CI/CD transformation is
explicitly out of scope for wave-1. The seven-phase model can be executed manually or partially
automated without a full pipeline. CI/CD can be layered on top as epic-11 matures.

### Alt C — Document-only approach (write a runbook, execute freely)
Changes are documented in runbooks but not gated by approval records. **Rejected**: documentation
without enforcement does not prevent undocumented bypasses, especially for high-risk changes.

---

## Consequences

### Positive
- Any deployment can be reconstructed end-to-end from git history + approval records.
- Rollback paths are tested before they are needed.
- Post-deploy verification closes the intent-to-outcome gap.
- Registry reconciliation keeps operational state aligned after every change.

### Negative / Tradeoffs
- Phase 3–7 add overhead to every change, including minor ones.
- Evidence artifacts require storage and retrieval infrastructure (part of epic-7 delivery).
- Rollback path documentation must be maintained as schemas and services evolve.

---

## Implementation Bindings

| Constraint | Binding |
|---|---|
| Change log | `governance.change_log` — required for every Phase 7 closure |
| Approval records | `governance.approval_record` — required Phase 3 gate |
| Evidence artifacts | `discovery.evidence_artifact` — Phase 5 post-deploy proof |
| Release evidence | epic-11 (pt-036) — formal release evidence chain |
| Promotion gates | epic-11 (pt-034) — environment promotion rules |
| Rollback drills | epic-11 (pt-035) — tested rollback contracts |

---

*Source: blueprint_platforma_interna.md §15.2, §16, execution_principles, ADR review 2026-03-08*
