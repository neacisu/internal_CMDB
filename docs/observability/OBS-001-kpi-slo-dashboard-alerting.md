---
id: OBS-001
title: internalCMDB — KPIs, SLOs, Dashboards and Alerting Catalog (Wave-1)
doc_class: policy_pack
domain: observability
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [observability, kpi, slo, dashboard, alerting, wave-1, m7-1]
depends_on: [ADR-001, ADR-002, GOV-007, PILOT-003]
---

# internalCMDB — KPIs, SLOs, Dashboards and Alerting Catalog (Wave-1)

## 1. Purpose

Defines measurable KPIs, SLO targets, required dashboards, and critical alerting rules for all
core Wave-1 platform surfaces. Satisfies pt-022 [m7-1].

---

## 2. Surfaces in Scope

| Surface | Schema / Component | Owner |
|---|---|---|
| Registry | `registry.*` (host, shared_service, application, ownership) | platform_architecture_lead |
| Discovery | `discovery.*` (collection_run, evidence_artifact, reconciliation) | platform_architecture_lead |
| Retrieval | `retrieval.*` (evidence_pack, document_chunk, chunk_embedding) | platform_architecture_lead |
| Approvals | `governance.approval_record`, `agent_control.action_request` | security_and_policy_owner |
| Agent Control | `agent_control.agent_run`, `agent_control.agent_evidence` | platform_architecture_lead |

---

## 3. KPI Catalog

### 3.1 Registry Completeness

| KPI | Definition | Target |
|---|---|---|
| KPI-REG-001 | % entities with ≥1 OwnershipRecord | ≥95% |
| KPI-REG-002 | % entities with canonical_document linked | ≥80% |
| KPI-REG-003 | Active collection_run success rate (24h) | ≥99% |

### 3.2 Retrieval Quality

| KPI | Definition | Target |
|---|---|---|
| KPI-RET-001 | Evidence pack violation rate (violations > 0 / total packs) | <1% |
| KPI-RET-002 | Mandatory class satisfaction rate | ≥99% |
| KPI-RET-003 | Broker p95 latency (ms) | <3000ms |

### 3.3 Approval Governance

| KPI | Definition | Target |
|---|---|---|
| KPI-GOV-001 | Denial rate for RC-2+ actions (deny/total) | Tracked; alerting >50% |
| KPI-GOV-002 | Expired approval record rate | <5% of active records |
| KPI-GOV-003 | Quorum satisfaction rate for RC-4 | ≥100% (hard gate) |

### 3.4 Agent Runs

| KPI | Definition | Target |
|---|---|---|
| KPI-RUN-001 | Agent run completion rate (completed / total started) | ≥90% |
| KPI-RUN-002 | Audit evidence completeness (runs with ≥1 evidence item) | ≥99% |
| KPI-RUN-003 | p95 run duration | <60s (TT-001/002); <120s (TT-003/006) |

---

## 4. SLO Definitions

| SLO ID | Surface | Objective | Error Budget Window |
|---|---|---|---|
| SLO-001 | Registry read availability | p999 query success ≥99.5% | 30-day rolling |
| SLO-002 | Collection run success | ≥99% in any 24h window | 7-day rolling |
| SLO-003 | Retrieval broker latency | p95 <3000ms | 7-day rolling |
| SLO-004 | Approval governance | 0 RC-3/RC-4 write executions without valid approval | N/A (hard gate) |
| SLO-005 | Audit completeness | 100% of completed agent runs have ≥1 AgentEvidence row | 30-day rolling |

---

## 5. Dashboard Requirements

### Dashboard 1: Registry Health (`db-registry-health`)

**Required panels**:
- Entity count by kind (Host, SharedService, Application) — time series
- Entities without OwnershipRecord — gauge
- Collection run success/failure — time series
- Last successful collection run age — stat

**Datasource**: Prometheus (postgresql_exporter) + Grafana table panel (direct PG query).

### Dashboard 2: Retrieval and Evidence Quality (`db-retrieval-quality`)

**Required panels**:
- Evidence pack violation rate — gauge + threshold
- Mandatory class satisfaction rate — gauge
- Broker p95 latency — histogram panel
- Token budget utilisation distribution — histogram

### Dashboard 3: Approval and Governance (`db-approval-governance`)

**Required panels**:
- Denial rate by action class — bar chart
- Expired approvals count — alert-linked stat
- Pending action requests by status — table
- RC-4 quorum failure count (should be 0) — alert-linked gauge

### Dashboard 4: Agent Run Audit (`db-agent-audit`)

**Required panels**:
- Run completion rate — time series
- Runs by status (pending/running/completed/failed) — stacked bar
- Evidence completeness rate (runs with ≥1 evidence) — gauge
- Policy denials per run — bar chart

---

## 6. Alert Rules

| Alert ID | Condition | Severity | Routing |
|---|---|---|---|
| ALT-001 | Collection run failure (3 consecutive) | CRITICAL | on_call_primary |
| ALT-002 | Registry KPI-REG-001 drops below 90% | WARNING | platform_review_channel |
| ALT-003 | Evidence pack violation rate >1% | WARNING | platform_review_channel |
| ALT-004 | Expired approval rate >5% | WARNING | security_and_policy_owner |
| ALT-005 | RC-4 quorum failure detected | CRITICAL | security_and_policy_owner + on_call |
| ALT-006 | Agent run p95 duration >2x target | WARNING | platform_review_channel |
| ALT-007 | Audit completeness rate <99% | CRITICAL | platform_architecture_lead |
| ALT-008 | PolicyEnforcer denial rate >50% past 1h | WARNING | security_and_policy_owner |
