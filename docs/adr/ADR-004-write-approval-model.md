---
id: ADR-004
title: Write Approval Model — All Agent Writes Mediated via Action Broker with Explicit Approval
status: approved
date: 2026-03-08
created: 2026-03-08
updated: 2026-03-08
deciders:
  - name: Alex Neacsu
    role: Architecture Board
    approved_at: 2026-03-08
  - name: Alex Neacsu
    role: Security & Policy Owner
    approved_at: 2026-03-08
doc_class: adr
domain: platform-foundations
version: "1.0"
owner: security_and_policy_owner
binding: []
tags: [write-approval, action-broker, governance, deny-by-default, wave-1]
---

# ADR-004 — Write Approval Model: All Agent Writes via Action Broker

## Status

**Accepted** — 2026-03-08, Alex Neacsu (Architecture Board + Security & Policy Owner)

---

## Context

AI agents executing platform tasks may need to write to the registry, modify configuration,
deploy services or mutate infrastructure state. Without a mediated write model, agents can:

- execute unreviewed changes directly on production infrastructure;
- bypass ownership and audit controls;
- perform irreversible operations without human confirmation;
- leave no traceable record of what was done, why and who approved it.

The platform's core safety model requires that agents are controlled participants in the SDLC,
not autonomous actors with unrestricted write access.

---

## Decision

**All agent write actions must be mediated by an action broker. No agent may write to
infrastructure, registry tables or deployment targets without an explicit, persisted approval
record. Deny-by-default is the enforced posture for all unsupported or unapproved write paths.**

### Action risk classification

Every write action is classified into one of four risk classes:

| Risk Class | Examples | Approval Requirement |
|---|---|---|
| **RC-1 Read-only analysis** | Registry reads, document retrieval, evidence pack assembly | No approval required. Fully automated. |
| **RC-2 Repository writes** | Git commits, doc authoring, migration authoring | Self-approval by Platform Engineering Lead. Logged. |
| **RC-3 Bounded runtime changes** | Registry upsert (discovery loaders), schema migration in staging | Data Registry Owner approval. Time-bounded scope. |
| **RC-4 High-risk infrastructure actions** | Production schema migration, service restart, network change | Architecture Board + Executive Sponsor. Dual approval. Expiry-bounded. |

### Approval record requirements

Every approval record (`governance.approval_record`) must include:

- `action_class`: RC-1 through RC-4
- `requested_by`: agent run ID or human role
- `approved_by`: role(s) sufficient for the risk class
- `scope`: explicit description of what is allowed (target system, operation, entity range)
- `approved_at` and `expires_at`: all approvals expire; no standing unlimited approval
- `rationale`: why the action is necessary
- `post_execution_verification`: what must be verified after the action completes

### Action broker enforcement rules

1. **No supported write path may execute without an eligible, non-expired approval record.**
2. **Approval records are immutable once created.** Corrections require a new record.
3. **Scope must be explicit**: "write to registry.host for orchestrator hostname resolution
   update" is valid; "write anywhere in registry" is not.
4. **Expiry is mandatory**: default 24h for RC-3, 4h for RC-4. Shorter is always permitted.
5. **Post-execution verification is mandatory for RC-3 and RC-4**: the broker must record
   what was verified after the action completed.
6. **Denied actions produce audit records** equal in completeness to approved actions.

### Prohibited patterns

- Direct database writes from agent code without action broker mediation.
- Approval records with unbounded scope (`scope: any`).
- Approvals granted in the same agent run that requests them (no self-approval for RC-4).
- Standing approvals that do not expire.
- Silent failures: if an action cannot be approved, the broker must record the denial.

---

## Alternatives Considered

### Alt A — Trust-based model (agents write freely, review after)
Agents execute writes and humans review logs periodically. **Rejected**: irreversible actions
(schema migrations, config changes) cannot be undone after the fact; post-hoc review does not
prevent damage; audit records are insufficient without pre-action approval context.

### Alt B — Human-in-the-loop for every write (manual approval only)
All write actions pause and wait for a human to click approve. **Rejected**: operationally
impractical for RC-2 and RC-3 automated pipeline steps; blocks legitimate automation while not
materially reducing risk for lower-risk operations.

### Alt C — Policy-based automated approval (no human required)
Approval granted automatically when a policy rule matches. **Rejected for RC-4**: high-risk
infrastructure actions must have explicit human confirmation with scope review. Policy-based
auto-approval is acceptable for RC-2 only.

---

## Consequences

### Positive
- Every material agent action leaves an auditable approval record.
- Deny-by-default prevents unknown write paths from silently succeeding.
- Scope and expiry constraints bound the blast radius of any approved action.
- Post-execution verification closes the loop between intent and outcome.

### Negative / Tradeoffs
- Action broker must be implemented before any agent write path can be enabled (epic-5 blocker).
- RC-3 and RC-4 operations have latency overhead from approval workflow.
- All agent implementations must be written against the action broker API, not direct DB/SSH.

---

## Implementation Bindings

| Constraint | Binding |
|---|---|
| Approval storage | `governance.approval_record` |
| Action request storage | `agent_control.action_request` |
| Action broker | epic-5 / impl-epic-8 delivery (pt-017) |
| Policy matrix | pt-016 deliverable (sprint-7) |
| Audit ledger | `agent_control.agent_run` + `governance.change_log` |
| Deny-by-default verification | pt-017 exit criterion: no governed write succeeds without approval |

---

*Source: blueprint_platforma_interna.md §14.4, explicit_decisions.approval_model, ADR review 2026-03-08*
