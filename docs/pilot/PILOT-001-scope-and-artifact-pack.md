---
id: PILOT-001
title: internalCMDB — Bounded Pilot Scope Selection and Mandatory Artifact Pack (Wave-1)
doc_class: research_dossier
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [pilot, bounded-scope, research-dossier, artifact-pack, wave-1, m6-1]
depends_on: [ADR-001, ADR-002, ADR-004, ADR-005, GOV-007]
---

# internalCMDB — Bounded Pilot Scope Selection and Mandatory Artifact Pack

## 1. Purpose

This document records the selection rationale, approval criteria, and mandatory artifact pack
for the first governance-controlled pilot execution of the internalCMDB platform. It satisfies
pt-019 [m6-1]: deliverable = approved pilot scope + research dossier + application definition
pack + verification specification + evidence map.

---

## 2. Pilot Scope Definition

### 2.1 Bounding Criteria

The pilot must satisfy all of the following constraints:

| Constraint | Requirement |
|---|---|
| Entity class | At most one SharedService and its directly connected Host set |
| Action class | AC-001 (REGISTRY_READ) and AC-002 (DOCUMENT_VALIDATION_RUN) only — RC-1, no write path |
| Evidence pack | TT-001 (host-infrastructure-audit) task type, token budget ≤ 8000 |
| Approval requirement | None required for RC-1 actions; all denial scenarios must be exercised |
| Audit completeness | Every step must produce an AgentRun row with linked evidence |

### 2.2 Selected Pilot Entity

**Target**: `shared-service/monitoring-stack` — the cluster monitoring shared service operating
on the internal infrastructure as identified during the Wave-1 discovery collection runs.

**Rationale**:
- Monitoring stack is observable, bounded, and its dependencies are already recorded in the
  registry from the Bootstrap phase.
- It is a read-only audit target (AC-001/AC-002 only) so no approval gate is required.
- Its host set is small (2–4 hosts) and well-understood, providing a tractable first pilot.
- Failure modes are low-impact and reversible.

### 2.3 Out-of-Scope Boundaries

The following are explicitly **excluded** from this pilot:

- Any write-path action class (AC-003 through AC-010).
- Any entity outside the monitoring-stack dependency graph.
- Production credential rotation or network topology changes.
- Any LLM inference or agent-generated output beyond evidence pack assembly.

---

## 3. Research Dossier

### 3.1 Infrastructure Observations (from Wave-1 collection)

| Entity | Kind | Discovery Source |
|---|---|---|
| monitoring-stack | SharedService | agent_control collection run #1 |
| host-monitoring-01 | Host | SSH discovery, Wave-1 |
| host-monitoring-02 | Host | SSH discovery, Wave-1 |

### 3.2 Known Dependencies

- Prometheus (scrape targets: all cluster hosts)
- Grafana (dashboards: llm-machines, cluster health)
- Loki (log aggregation from Docker compose stacks)
- AlertManager (routing: on-call list, escalation rules TBD)

### 3.3 Open Gaps at Pilot Selection

| Gap | Risk | Mitigation |
|---|---|---|
| AlertManager on-call list not yet recorded | LOW | Out of pilot scope; record as gap in pt-021 |
| Grafana datasource credentials not in secrets registry | MEDIUM | AC-028 (secrets) blocked; pilot uses read-only |
| Host OS versions not canonical | LOW | Will be verified during pilot evidence assembly |

---

## 4. Application Definition Pack

| Field | Value |
|---|---|
| Application code | `PILOT-monitoring-stack-v1` |
| Task type | TT-001 (host-infrastructure-audit) |
| Template code | `tmpl-host-audit-v1` |
| Evidence budget | 8000 tokens |
| Mandatory evidence | REGISTRY_HOST, REGISTRY_SERVICE, REGISTRY_OWNERSHIP |
| Recommended evidence | EVIDENCE_ARTIFACT, OBSERVED_FACT |
| Disallowed evidence | CHUNK_SEMANTIC (not allowed for TT-001) |
| Approval class | AC-001 — no approval required |
| Snapshot required | No (RC-1) |

---

## 5. Verification Specification

The pilot is considered successfully verified when ALL of the following are true:

1. **Registry completeness**: `monitoring-stack` SharedService row exists in the registry with
   at least one linked Host and one OwnershipRecord.
2. **Evidence pack assembled**: A BrokerResult with 0 violations is produced for TT-001
   targeting `monitoring-stack`.
3. **AgentRun record**: An AgentRun row with status=completed exists, linked to the evidence
   pack and the prompt template used.
4. **Denial path exercised**: At least one AgentRun with status=failed exists for a
   deliberately invalid request, with policy_denial_reasons recorded in the JSONB scope.
5. **Audit reconstructable**: For every completed or failed run, the evidence chain (prompt →
   evidence pack → run → change log if any) can be traversed without gaps.
6. **No hidden manual step**: No action was taken outside the governed workflow to achieve
   the declared pilot outcome.

---

## 6. Evidence Map

| Evidence Item | Source | Required For Verification |
|---|---|---|
| monitoring-stack registry row | registry.shared_service | V-1 |
| host-monitoring-01 row linking | registry.host | V-1 |
| OwnershipRecord for monitoring-stack | registry.ownership_record | V-1 |
| BrokerResult (TT-001, 0 violations) | retrieval.evidence_pack | V-2 |
| AgentRun (completed) | agent_control.agent_run | V-3 |
| AgentRun (failed, policy denial) | agent_control.agent_run | V-4 |
| ChangeLog (if any write exercised) | governance.change_log | V-5 |

---

## 7. Approval Record

| Field | Value |
|---|---|
| Approved by | platform_architecture_lead |
| Approval date | 2026-03-08 |
| Approval scope | Read-only pilot of monitoring-stack per PILOT-001 v1.0 |
| Expiry | End of sprint-9 (2026-03-22) |
| Conditions | No write-path actions permitted; gap register must be updated in pt-021 |
