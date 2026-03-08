---
id: POL-001
title: internalCMDB — RTO / RPO & Business Continuity Policy
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: sre_observability_owner
tags: [policy, rto, rpo, business-continuity, wave-1]
---

# internalCMDB — RTO / RPO & Business Continuity Policy

**Version**: 1.0
**Date**: 2026-03-08
**Owner**: Alex Neacsu (SRE / Observability Owner + Executive Sponsor)
**Status**: Approved (single-operator sign-off, Wave-1 posture)

---

## 1. Scope

This policy covers the **internalCMDB** platform: the PostgreSQL database
(`internalcmdb-postgres` on orchestrator), its discovery audit loaders, and
the Traefik TCP routing layer. It does NOT cover upstream cluster hosts that
are _observed_ by the CMDB.

---

## 2. Recovery Objectives

| Metric | Target | Basis |
|--------|--------|-------|
| **RTO** (Recovery Time Objective) | **4 hours** | Time to restore a fully functional CMDB from the last backup, including Alembic state, taxonomy seed, and connection routing |
| **RPO** (Recovery Point Objective) | **24 hours** | Maximum acceptable data loss window; one full day of discovery audit runs |
| **MTTR** (Mean Time to Recover) | < 2 hours | Operational target; subject to quarterly review |

These targets are explicitly accepted as **Wave-1 single-instance posture** and
must be revisited before the platform is used for time-critical automated
decisions.

---

## 3. Backup Policy

### 3.1 Database Backup

| Aspect | Detail |
|--------|--------|
| Method | `pg_dump` (plain SQL or custom format) piped to compressed archive |
| Frequency | Daily at 02:00 UTC (cron on orchestrator) |
| Retention | 7 days local, 30 days off-site (Hetzner storage box or S3-compatible) |
| Location | `/mnt/HC_Volume_105014654/postgresql/internalcmdb/backups/` |
| Verification | `pg_restore --list` dry-run after each dump; alert on non-zero exit |

### 3.2 Schema State

Alembic migration history is tracked in `governance.alembic_version`. Upon
restore, run `alembic upgrade head` to verify head is at `0001`. If the dump
pre-dates a migration, re-apply from version table.

### 3.3 Audit Evidence Files

Discovery results in `subprojects/*/results/*/current.json` are source-of-truth
for re-seeding. These files must be committed to version control or backed up
alongside the database.

---

## 4. Restore Procedure

1. Stop any in-flight loaders on the local machine.
2. SSH to orchestrator: `ssh orchestrator`
3. Stop the container: `docker stop internalcmdb-postgres`
4. Restore data volume from backup:
   ```bash
   pg_restore -U internalcmdb -d internalCMDB \
     /mnt/HC_Volume_105014654/postgresql/internalcmdb/backups/latest.dump
   ```
5. Restart the container: `docker start internalcmdb-postgres`
6. Verify: `pg_isready && psql -U internalcmdb -d internalCMDB -c "SELECT COUNT(*) FROM registry.host"`
7. From local machine, verify Traefik routing:
   `psql "postgresql://internalcmdb:<pw>@postgres.orchestrator.neanelu.ro:5432/internalCMDB?sslmode=require"`
8. Run `alembic upgrade head` to confirm schema is at head.
9. If host count < 9: re-run `ssh_audit_loader`, `runtime_posture_loader`, `trust_surface_loader`.

**Expected restore time:** ≤ 30 minutes for a 500 MB database.

---

## 5. HA Posture (Wave-1 Accepted Limitations)

| Aspect | Current State | Accepted Risk |
|--------|---------------|---------------|
| Database redundancy | Single instance, no replica | Accepted; single-operator platform |
| Failover | Manual; operator must intervene | RTO ≤ 4h covers this |
| Volume resilience | HC Volume (RAID at provider level) | Accepted; provider SLA applies |
| Container restart | `restart: unless-stopped` | Auto-restarts on crash |
| Traefik SPOF | Single Traefik instance | Accepted; same node as PG |
| Network path | `postgres.orchestrator.neanelu.ro` → Traefik TCP :5432 | DNS + TLS via Cloudflare |

**Wave-2 HA requirement:** Before any external team depends on internalCMDB for
automated approvals, a read replica and automated failover mechanism (Patroni or
pg_auto_failover) must be implemented. This is tracked as an exit criterion
for epic-8 (`rto-rpo-and-ha-posture-approved`).

---

## 6. Disaster Recovery Exercise

A DR exercise must be performed within 30 days of this document's approval date,
documenting:
- Actual RTO achieved
- Any gaps found in the restore procedure
- Schema drift, if any

Results must be appended to this document as `## DR Exercise Log`.

---

## DR Exercise Log

*(To be completed after first exercise.)*

---

*Generated: 2026-03-08 | Approved: Alex Neacsu | Review date: 2026-06-08*
