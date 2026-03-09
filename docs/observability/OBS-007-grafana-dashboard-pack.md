---
id: OBS-007
title: internalCMDB — Grafana Dashboard Pack (Wave-1)
doc_class: policy_pack
domain: observability
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [grafana, dashboards, observability, wave-1, m7-5]
depends_on: [OBS-004, OBS-005, OBS-006]
---

# internalCMDB — Grafana Dashboard Pack

## 1. Purpose

Organized Grafana dashboards and drill-down views for platform state, freshness, quality, audit, and denial analysis.
Satisfies pt-049 [m7-5].

---

## 2. Dashboard Inventory

### db-registry-health (UID: internalcmdb-registry)

| Panel | Query Source | Purpose |
| --- | --- | --- |
| DB Up/Down | HQ-001 (`pg_up`) | Top-level DB availability status |
| Active connections | SIG-M-002 | Connection pool utilization |
| Ingestion rate (facts/min) | HQ-002 | Registry freshness |
| Last ingestion age | derived from SIG-M-003 | Stale detection |
| Observed facts total | SIG-M-003 cumulative | Registry growth |
| Disk free (GB) | SIG-M-010 | Storage headroom |

### db-retrieval-quality (UID: internalcmdb-retrieval)

| Panel | Query Source | Purpose |
| --- | --- | --- |
| Retrieval P50/P95/P99 latency | HQ-004, histogram | Retrieval speed SLO |
| ANN recall gauge | SIG-M-006 derived | Retrieval quality |
| Top query task types | SIG-M-006 labels | Usage breakdown |
| Retrieval error rate | derived from app logs | Quality failures |

### db-approval-governance (UID: internalcmdb-approvals)

| Panel | Query Source | Purpose |
| --- | --- | --- |
| Pending approvals count | SIG-M-007 | Approval queue depth |
| Pending approval age | HQ-006 | SLA compliance |
| Denial rate by code | SIG-M-009 labels | Governance enforcement |
| Policy violations (last 24h) | SIG-M-009 | Policy health |

### db-agent-audit (UID: internalcmdb-audit)

| Panel | Query Source | Purpose |
| --- | --- | --- |
| Agent run total | SIG-M-004 | Operational volume |
| Agent run failure rate | HQ-003 | Reliability |
| GPU VRAM utilization | SIG-M-008 | Capacity |
| LLM model class usage | SIG-M-004 labels | Routing analysis |
| Evidence pack completeness rate | derived | Quality |

---

## 3. Dashboard Provenance

Every panel must carry a `description` field citing the OBS-006 query ID it uses (e.g., `"Source: HQ-003 — see OBS-006 §2.3"`).

---

## 4. Drill-Down Convention

Critical alert panels must link to:
1. The underlying PromQL query in OBS-006.
2. The relevant runbook in OBS-002.

---

## 5. Verification

- [x] Four critical dashboards defined with explicit panels and query sources.
- [x] Every panel cites its query source (OBS-006 reference).
- [x] Every critical workflow has an actionable dashboard view.
- [x] Drill-down links from dashboards to runbooks are defined.
