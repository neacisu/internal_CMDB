---
id: OBS-011
title: internalCMDB — Runbook Linkage Index (Alerts to Runbooks) (Wave-1)
doc_class: policy_pack
domain: observability
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [runbooks, linkage, alerts, wave-1, m7-6]
depends_on: [OBS-002, OBS-008]
---

# internalCMDB — Runbook Linkage Index

## 1. Purpose

Indexed linkage from alert rules and dashboard panels to runbooks, owners, escalation paths, and recovery procedures.
Satisfies pt-053 [m7-6].

---

## 2. Alert → Runbook Linkage

| Alert ID | Alert Name | Runbook | Owner | Escalation |
| --- | --- | --- | --- | --- |
| ALT-001 | DB Down | OBS-002 RB-001 (collection failure response) | platform_architecture_lead | CP-002 after 30 min |
| ALT-002 | Ingestion Stale | OBS-002 RB-001 | platform_architecture_lead | CP-001 after 6h |
| ALT-003 | Retrieval Latency | OBS-002 RB-005 (broker failure) | platform_architecture_lead | CP-001 after 30 min |
| ALT-004 | Approval Expiry | OBS-002 RB-004 (expired approvals) | security_and_policy_owner | CP-002 after 48h |
| ALT-005 | Agent Run Failure | OBS-002 RB-002 (pack violation) | platform_architecture_lead | CP-002 after 30 min |
| ALT-006 | Broker Anomaly | OBS-002 RB-005 | security_and_policy_owner | Immediate CP-002 |
| ALT-007 | GPU VRAM Critical | LLM-003 §5 (Degradation Handling) | platform_architecture_lead | Immediate CP-001 |
| ALT-008 | All Models Down | LLM-003 §3 (Fallback Policy) | platform_architecture_lead | CP-002 after 15 min |

---

## 3. Dashboard Panel → Runbook Linkage

| Dashboard | Panel | Runbook |
| --- | --- | --- |
| db-registry-health | DB Up/Down | OBS-002 RB-001 |
| db-registry-health | Ingestion rate | OBS-002 RB-001 |
| db-retrieval-quality | Retrieval P95 latency | OBS-002 RB-005 |
| db-approval-governance | Pending approval age | OBS-002 RB-004 |
| db-approval-governance | Policy denial rate spike | OBS-002 RB-002 |
| db-agent-audit | Agent run failure rate | OBS-002 RB-002 |
| db-agent-audit | GPU VRAM | LLM-003 §5 |

---

## 4. Runbook Inventory

| Runbook ID | Source Document | Title | Available |
| --- | --- | --- | --- |
| RB-001 | OBS-002 §4 | Collection failure response | YES |
| RB-002 | OBS-002 §4 | Policy pack violation response | YES |
| RB-003 | OBS-002 §4 | Retention job failure | YES |
| RB-004 | OBS-002 §4 | Expired approvals cleanup | YES |
| RB-005 | OBS-002 §4 | Broker failure response | YES |
| RB-DR-001 | CONT-002 §3 | PostgreSQL restore procedure | YES |

---

## 5. Verification

- [x] Every critical alert path links to a runbook.
- [x] Every runbook has a named owner.
- [x] No critical alert path requires institutional memory (all runbooks documented).
- [x] Dashboard panels are linked to relevant runbooks.
- [x] Runbook inventory is complete and all runbooks are marked Available.
