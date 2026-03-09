---
id: ADR-001
title: Truth Model — Five-State Separation for Canonical, Observed, Desired, Evidence and Working State
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
tags: [truth-model, state-separation, governance, wave-1]
---

# ADR-001 — Truth Model: Five-State Separation

## Status

**Accepted** — 2026-03-08, Alex Neacsu (Architecture Board)

---

## Context

The internalCMDB platform must support workflows for humans and AI agents that operate on
infrastructure facts, design decisions, policies, evidence and runtime context simultaneously.
Without explicit separation of these information types, systems and agents conflate approved
design with observed reality, desired targets with current state, and working assumptions with
verified evidence. This leads to incorrect automated actions, hidden drift, unauditable decisions
and agent hallucinations.

The platform must define a canonical model for what "truth" means in each context and enforce
strict separation between all five categories at ingestion, retrieval and agent execution time.

---

## Decision

**The platform adopts a five-state truth model as a non-negotiable architectural constraint.
All registry records, retrieval outputs, agent context packs and audit artifacts must carry an
explicit state tag. Mixing state types without reconciliation approval is forbidden.**

The five states are defined as follows:

### 1. Canonical State
- **Definition**: What is officially defined, approved and git-versioned.
- **Storage**: Git-versioned Markdown/YAML documents in the canonical sources layer.
- **Authority**: Approved by the Architecture Board. Changes require review + merge.
- **Registry binding**: `docs.document`, `docs.document_version` — linked to registry entities.
- **Rules**:
  - A canonical document is the source of truth for design decisions, contracts and policies.
  - Canonical state cannot be overwritten by observed state without explicit reconciliation.
  - If canonical state is absent for a critical claim, the claim is a specification gap.

### 2. Observed State
- **Definition**: What is detected from the real infrastructure through automated discovery.
- **Storage**: `discovery.observed_fact`, backed by `discovery.collection_run` and `discovery.discovery_source`.
- **Authority**: Trusted only when backed by a timestamped, identified collection run.
- **Rules**:
  - Observed state is always provisional until reconciled against canonical state.
  - Conflicting canonical vs observed states must surface as reconciliation findings.
  - No agent may treat observed state as approved canonical design.

### 3. Desired State
- **Definition**: How the infrastructure should look according to policies and target standards.
- **Storage**: Policy documents (`governance.policy_record`) + canonical ADR targets.
- **Authority**: Security & Policy Owner, with Architecture Board approval where architectural.
- **Rules**:
  - Desired state drives the comparison baseline for drift detection.
  - Desired state must be versioned and explicitly linked to the policy or ADR that defines it.

### 4. Evidence State
- **Definition**: Verified artifacts and provenance that prove observed or canonical claims.
- **Storage**: `discovery.evidence_artifact`, referenced from `retrieval.evidence_pack_item`.
- **Authority**: Discovery Owner for observed evidence; Architecture Board for canonical evidence.
- **Rules**:
  - Every material claim in an agent context pack must have an evidence reference.
  - Evidence without a timestamped source, collector and hash is not valid evidence.
  - Evidence state is immutable once recorded — corrections produce new evidence records.

### 5. Working State
- **Definition**: Temporary, bounded context assembled by an agent for a specific execution task.
- **Storage**: `agent_control.agent_run` + `agent_control.agent_evidence` (ephemeral, bound to run).
- **Authority**: The agent run scope and approval record.
- **Rules**:
  - Working state exists only within a bounded agent run and must not persist as canonical state.
  - Working state must be assembled from canonical, observed or evidence state — never invented.
  - When a required state element is missing, the agent must declare a specification gap.

---

## Alternatives Considered

### Alt A — Single unified state model
All facts stored in one table without state differentiation. **Rejected**: conflates design with
reality, breaks reconciliation, allows agents to treat runtime facts as approved decisions.

### Alt B — Two-state model (canonical vs observed only)
Simpler separation between design and reality. **Rejected**: loses evidence provenance, desired
state policy targets, and working state isolation — all critical for agent governance.

### Alt C — Three-state model (canonical / observed / desired)
Add desired state for drift detection. **Rejected**: without separate evidence and working state,
agent context packs lack audit-grade provenance and there is no clear isolation for ephemeral
agent execution context.

---

## Consequences

### Positive
- Agents cannot hallucinate by mixing state types.
- Drift detection has a clear model: observed vs canonical vs desired.
- Every audit record is traceable to a state type and authority.
- Retrieval results carry explicit state provenance.

### Negative / Tradeoffs
- More complex data model and retrieval contracts.
- Every loader and loader result must explicitly tag each record by state type.
- Reconciliation workflows are required before any write-path action.

---

## Implementation Bindings

| Constraint | Binding |
| --- | --- |
| Canonical state storage | `docs.document`, `docs.document_version`, git repo |
| Observed state storage | `discovery.observed_fact`, `discovery.collection_run` |
| Desired state storage | `governance.policy_record`, canonical ADR targets |
| Evidence state storage | `discovery.evidence_artifact`, `retrieval.evidence_pack_item` |
| Working state storage | `agent_control.agent_run`, `agent_control.agent_evidence` |
| Conflict resolution | Raise reconciliation finding → block write until resolved or override approved |

---

*Source: blueprint_platforma_interna.md §9.1, ADR review 2026-03-08*
