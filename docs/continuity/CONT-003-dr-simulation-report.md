---
id: CONT-003
title: internalCMDB — Disaster Recovery Simulation Report and Remediation Register (Wave-1)
doc_class: research_dossier
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [disaster-recovery, simulation, dr-exercise, remediation, wave-1, m8-3]
depends_on: [CONT-001, CONT-002]
---

## 1. Purpose

Disaster exercise report with findings, risk rating, and corrective action register.
Satisfies pt-027 [m8-3].

---

## 2. Exercise Summary

| Field | Value |
| --- | --- |
| Exercise date | 2026-03-08 |
| Scenario | Primary PostgreSQL node failure — full DB restore from backup |
| Executed by | platform_architecture_lead |
| Observed RTO | 12 minutes |
| Target RTO | 4 hours |
| Outcome | PASS — recovery completed within RTO |

---

## 3. Scenario Definition

**Scenario**: `DREX-001 — PostgreSQL Primary Node Loss`

Simulation steps:

1. Stop `internalcmdb-postgres` Docker container (simulating node failure).
2. Verify that application services detect DB unavailability.
3. Start a fresh PostgreSQL 17 container (clean state).
4. Execute restore procedure RB-DR-001 from last backup.
5. Verify post-restore validation checklist.
6. Restart application services.
7. Confirm evidence pack assembly works end-to-end.

---

## 4. Execution Log

| Step | Time | Result | Notes |
| --- | --- | --- | --- |
| Container stopped | 09:00 | PASS | All connections refused after 30s |
| Service unavailability detected | 09:00:35 | PASS | Application logs showed ConnectionError |
| Fresh container started | 09:02 | PASS | PostgreSQL 17 started, empty DB |
| pg_restore executed | 09:03 | PASS | 8 minutes to completion |
| Row count validation | 09:11 | PASS | Counts matched backup manifest |
| FK integrity validation | 09:11:30 | PASS | No violations |
| Application services restarted | 09:12 | PASS | All services healthy |
| Evidence pack validation | 09:12:30 | PASS | BrokerResult 0 violations |

**Total recovery time**: 12 minutes.

---

## 5. Findings

| Finding ID | Description | Severity | Recommendation |
| --- | --- | --- | --- |
| F-001 | Application services do not retry DB connection automatically on startup | MEDIUM | Add retry logic with exponential backoff to DB session factory |
| F-002 | No alert fired when DB container stopped (Prometheus not scraped during exercise) | LOW | Configure Prometheus alerting for DB connection pool exhaustion |
| F-003 | Backup manifest (row counts) must be manually verified — no automated diffing | LOW | Add automated post-restore diff script to RB-DR-001 |
| F-004 | Application restart requires manual Docker Compose `up` command | LOW | Add health-check restart policy to compose services |

---

## 6. Corrective Action Register

| Action ID | Finding | Action | Owner | Target |
| --- | --- | --- | --- | --- |
| CA-001 | F-001 | Add SQLAlchemy `pool_pre_ping` and startup retry loop | platform_architecture_lead | Next sprint |
| CA-002 | F-002 | Configure `pg_up` Prometheus alert bound to DB container | platform_architecture_lead | pt-050 (alerts) |
| CA-003 | F-003 | Script post-restore count diff vs. backup manifest | platform_architecture_lead | pt-026 update |
| CA-004 | F-004 | Add `restart: unless-stopped` + healthcheck to compose | platform_architecture_lead | Next sprint |

---

## 7. Overall Risk Rating

| Dimension | Rating | Basis |
| --- | --- | --- |
| Recovery Success | LOW RISK | Restore completed in 12 min vs. 4h RTO |
| Data Loss | LOW RISK | Backup was 2h old at exercise time; RPO=1h not tested with WAL |
| Service Continuity | MEDIUM RISK | Manual restart required (CA-004 pending) |
| Alerting Coverage | MEDIUM RISK | DB failure not auto-alerted (CA-002 pending) |

**Overall DR Posture**: ACCEPTABLE for Wave-1 single-node deployment.
Not acceptable for Wave-2 production write-path without CA-001..CA-004 resolved.

---

## 8. Next Scheduled Exercise

DR Exercise cycle-2 targeted at pt-061 (quarterly backup/restore drill).
Scope: include WAL archive recovery (if WAL archiving enabled) and application auto-restart validation.
