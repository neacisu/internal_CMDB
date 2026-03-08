---
id: OPS-004
title: "Backup and Restore Drill Cycle-2 Comparison Report"
doc_class: research_dossier
domain: platform-foundations
status: approved
version: "1.0"
created: 2025-10-01
updated: 2025-10-01
owner: platform_architecture_lead
tags: [backup, restore, drill, cycle-2, comparison, m16-1]
---

# OPS-004 — Backup and Restore Drill Cycle-2 Comparison Report

## 1. Purpose

This dossier records the results of the Cycle-2 backup and restore drill for the
internalCMDB PostgreSQL cluster, compares them against the Cycle-1 baseline, and
identifies regressions, improvements, and open actions.

**Drill date**: 2025-10-01
**Drill scope**: Full-cluster logical backup (pg_dump) + point-in-time restore (WAL replay)
**Coordinator**: platform_architecture_lead
**Observer**: security_and_policy_owner

---

## 2. Cycle-1 Baseline (Reference)

| Metric | Cycle-1 (Q3 2025-07-01) |
|---|---|
| Backup duration | 4 min 12 s |
| Backup size (compressed) | 1.2 GiB |
| Restore duration (logical) | 8 min 45 s |
| PITR replay window available | 7 days |
| Data loss (RPO) | < 5 min |
| Service restoration (RTO) | < 15 min |
| Verification pass | ✅ rowcount match |
| Issues found | None |

---

## 3. Cycle-2 Results

| Metric | Cycle-2 (Q4 2025-10-01) | Δ vs Cycle-1 |
|---|---|---|
| Backup duration | 4 min 08 s | −4 s (−1.6%) |
| Backup size (compressed) | 1.4 GiB | +0.2 GiB (+16.7%) |
| Restore duration (logical) | 9 min 02 s | +17 s (+3.2%) |
| PITR replay window available | 7 days | No change |
| Data loss (RPO) | < 5 min | No change |
| Service restoration (RTO) | < 14 min 30 s | −30 s (−3.3%) |
| Verification pass | ✅ rowcount match | No change |
| Issues found | 1 (see §4) | +1 |

---

## 4. Issues and Observations

### Issue C2-001 — Restore Duration Regression

**Severity**: Low
**Description**: Logical restore took 17 s longer than Cycle-1.  Root cause is
data growth: `observed_fact` table grew from ~120k rows to ~210k rows between
cycles.  This is expected and proportional.

**Remediation**: No action required.  Set a threshold alert for restore duration
> 12 min to detect non-linear regressions earlier.

### Observation C2-O1 — Backup Size Growth

Backup size increased from 1.2 GiB to 1.4 GiB (+16.7%), consistent with
observed data growth rate.  Compress ratio unchanged (3.2:1 on average).

---

## 5. RPO / RTO Compliance

| SLA | Target | Cycle-2 Result | Status |
|---|---|---|---|
| RPO | < 5 min | < 5 min | ✅ PASS |
| RTO | < 15 min | < 14 min 30 s | ✅ PASS |

Both SLAs met.

---

## 6. PITR Verification

A WAL replay to a point-in-time 3 hours before the drill was performed on the
non-production replica.  Verification:

```sql
-- Confirmed row counts after PITR restore match expected historical state
SELECT COUNT(*) FROM discovery.observed_fact;
-- Result: 198,441 rows (expected: 198,437–198,450 range accounting for in-flight writes)
-- ✅ PASS
```

---

## 7. Action Items

| ID | Description | Owner | Due |
|---|---|---|---|
| C2-ACT-001 | Add Prometheus alert for restore duration > 12 min | platform_engineering | 2025-10-15 |
| C2-ACT-002 | Review backup storage budget for Q1 2026 (current trajectory: ~2 GiB by Q1) | platform_architecture_lead | 2025-11-01 |

---

## 8. Sign-off

**Drill verdict**: PASS — all SLAs met; no data loss; one low-severity action item raised.
**Signed**: platform_architecture_lead
**Date**: 2025-10-01
**Next drill**: Cycle-3, Q1 2026-01-01
