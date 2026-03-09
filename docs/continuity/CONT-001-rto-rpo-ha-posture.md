---
id: CONT-001
title: internalCMDB — RTO/RPO, HA Posture and Continuity Scope (Wave-1)
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [rto, rpo, ha, continuity, disaster-recovery, wave-1, m8-1]
depends_on: [OBS-001, OBS-003, ADR-001]
---

## internalCMDB — RTO/RPO, HA Posture and Continuity Scope

## 1. Purpose

Approved continuity baseline defining availability posture, recovery expectations, and
HA scope for internalCMDB. Satisfies pt-025 [m8-1].

---

## 2. Availability Posture

### 2.1 Service Criticality Classification

| Service | Criticality | Justification |
| --- | --- | --- |
| PostgreSQL DB (`internalcmdb-postgres`) | CRITICAL | Single source of truth for all registry/retrieval/governance data |
| Retrieval broker (Python app) | HIGH | Required for evidence assembly; stateless, restartable |
| Agent control workflow (Python app) | HIGH | Required for governed writes; stateless, restartable |
| LLM inference (self-hosted) | MEDIUM | Optional path; semantic retrieval degrades to lexical gracefully |
| Grafana dashboards | LOW | Observability only; no operational blocking |
| Prometheus/Loki | LOW | Telemetry sink; non-blocking for registry operations |

### 2.2 Single-Node Acceptance (Wave-1)

Wave-1 runs on a single PostgreSQL node (orchestrator). This is **accepted** for Wave-1 with
the following conditions:

- Regular WAL streaming or pg_dump backup (see CONT-002).
- No production write-path actions executed on live customer or infrastructure data.
- HA upgrade (Patroni or pg_auto_failover) is PLANNED for Wave-3.

---

## 3. RTO and RPO Targets

| Component | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) | Notes |
| --- | --- | --- | --- |
| PostgreSQL DB | 4 hours | 1 hour | pg_dump + WAL; tested in pt-026 |
| Python application stack | 30 minutes | N/A (stateless) | re-deploy from git tag |
| Prompt template registry | 30 minutes | 0 (DB-backed) | recovers with DB |
| Evidence packs | 4 hours | 1 hour (with DB) | packs are DB rows |
| LLM inference | 8 hours | N/A (stateless models) | model weights on disk |
| Grafana config | 2 hours | N/A (config-as-code) | restore from repo |

---

## 4. Continuity Scope

### 4.1 In Scope

- Loss of single PostgreSQL node (primary failure, disk failure, OS failure).
- Loss of single application host running Python services.
- Partial data corruption (detected via constraint violations or audit discrepancies).

### 4.2 Out of Scope (Wave-1)

- Multi-region failover.
- Active-active database replication.
- Real-time failover with <1 minute RTO (Patroni required — Wave-3).
- Loss of entire data center or cloud region.

---

## 5. Recovery Priority Order

1. Restore PostgreSQL DB from last backup (CONT-002, RB-DR-001).
2. Validate DB integrity: check PK/FK constraints, row counts vs. backup manifest.
3. Restart Python application stack (governance, retrieval, broker services).
4. Run post-recovery evidence pack validation (AC-002 on critical entities).
5. Restore Grafana/Prometheus from config-as-code; reconnect to DB datasource.
6. Notify stakeholders and record recovery event in `governance.change_log`.

---

## 6. Open Continuity Gaps

| Gap ID | Description | Target |
| --- | --- | --- |
| GAP-HA-001 | No streaming replication or automatic failover | Wave-3 (Patroni) |
| GAP-HA-002 | Backup/restore not yet tested from cold | pt-026 |
| GAP-HA-003 | DR simulation not yet conducted | pt-027 |
| GAP-HA-004 | No documented runbook index for DR scenarios | pt-027 output |
