---
id: OBS-004
title: internalCMDB — Observability Signal Inventory and Ownership (Wave-1)
doc_class: policy_pack
domain: observability
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [observability, signals, inventory, ownership, wave-1, m7-4]
depends_on: [OBS-001]
---

# internalCMDB — Observability Signal Inventory and Ownership

## 1. Purpose

Approved inventory of critical metrics, logs, traces, events, and derived health queries with named owners.
Satisfies pt-046 [m7-4].

---

## 2. Metrics Inventory

| Signal ID | Name | Source | Owner | Purpose |
|---|---|---|---|---|
| SIG-M-001 | `pg_up` | Prometheus postgres_exporter | platform_architecture_lead | DB availability |
| SIG-M-002 | `pg_stat_activity_count` | Prometheus postgres_exporter | platform_architecture_lead | Connection pool health |
| SIG-M-003 | `internalcmdb_observed_fact_total` | App Prometheus metrics | platform_architecture_lead | Ingestion volume |
| SIG-M-004 | `internalcmdb_agent_run_total` | App Prometheus metrics | platform_architecture_lead | Agent run volume |
| SIG-M-005 | `internalcmdb_agent_run_failure_total` | App Prometheus metrics | platform_architecture_lead | Agent run failure rate |
| SIG-M-006 | `internalcmdb_retrieval_latency_p95` | App Prometheus metrics | platform_architecture_lead | Retrieval quality |
| SIG-M-007 | `internalcmdb_approval_pending_total` | App Prometheus metrics | platform_architecture_lead | Approval queue health |
| SIG-M-008 | `nvidia_gpu_memory_used_bytes` | Prometheus dcgm-exporter | platform_architecture_lead | GPU VRAM usage |
| SIG-M-009 | `internalcmdb_policy_denial_total` | App Prometheus metrics | security_and_policy_owner | Governance enforcement |
| SIG-M-010 | `disk_free_bytes` | node_exporter | platform_architecture_lead | Storage capacity |

---

## 3. Logs Inventory

| Signal ID | Name | Source | Owner | Purpose |
|---|---|---|---|---|
| SIG-L-001 | Application structured logs | Docker stdout (Loki) | platform_architecture_lead | Debugging, audit trail |
| SIG-L-002 | PostgreSQL slow query log | pg logs (Loki) | platform_architecture_lead | Query performance |
| SIG-L-003 | vLLM access logs | Docker stdout (Loki) | platform_architecture_lead | LLM request audit |
| SIG-L-004 | SSH auth log | `/var/log/auth.log` | security_and_policy_owner | Access audit |
| SIG-L-005 | governance.change_log (DB table) | PostgreSQL | security_and_policy_owner | Governance audit |

---

## 4. Derived Health Queries

| Query ID | Signal Sources | Derived Metric | Alert Condition |
|---|---|---|---|
| HQ-001 | SIG-M-001 | DB up/down | `pg_up == 0` |
| HQ-002 | SIG-M-003 | Ingestion rate (last 1h) | `rate < 1/h` (stale) |
| HQ-003 | SIG-M-005, SIG-M-004 | Agent run failure rate | `> 10%` |
| HQ-004 | SIG-M-006 | Retrieval P95 latency | `> 200ms` |
| HQ-005 | SIG-M-008 | GPU VRAM utilization | `> 90%` |
| HQ-006 | SIG-M-007 | Approval queue age | `pending > 24h` |

---

## 5. No Alert Without Named Owner

Every alert-worthy condition (HQ-001..HQ-006) maps to a named owner. No alert fires without a corresponding entry in this table.

---

## 6. Verification

- [x] All critical platform surfaces have named signals.
- [x] Every signal has a named owner.
- [x] Every alert-worthy condition derives from a documented signal.
- [x] No alert-worthy condition depends on unnamed or undefined telemetry.
