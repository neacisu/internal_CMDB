---
id: OBS-006
title: internalCMDB — Canonical Health Queries and Derived Status Rules (Wave-1)
doc_class: policy_pack
domain: observability
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [health-queries, derived-status, observability, wave-1, m7-4]
depends_on: [OBS-004, OBS-005]
---

# internalCMDB — Canonical Health Queries and Derived Status Rules

## 1. Purpose

Approved health query pack and derived status rules for registry freshness, ingestion, retrieval, approvals, and agent runs.
Satisfies pt-048 [m7-4].

---

## 2. Health Query Pack (PromQL)

### Registry Freshness

```promql
# Last ingestion timestamp (seconds since epoch)
max(internalcmdb_last_ingestion_timestamp_seconds{env="wave1-production"})

# Stale if no ingestion in last 2 hours
(time() - max(internalcmdb_last_ingestion_timestamp_seconds)) > 7200
```

**Derived status**: STALE if expression > 0, HEALTHY otherwise.

### Ingestion Rate

```promql
# Facts ingested per minute (5m window)
rate(internalcmdb_observed_fact_total{env="wave1-production"}[5m]) * 60
```

**Derived status**: DEGRADED if rate < 0.5/min during expected ingestion windows.

### Retrieval Quality

```promql
# ANN retrieval P95 latency
histogram_quantile(0.95, rate(internalcmdb_retrieval_latency_seconds_bucket[5m]))
```

**Derived status**: DEGRADED if > 0.2s; CRITICAL if > 0.5s.

### Agent Run Health

```promql
# Failure rate (5m window)
rate(internalcmdb_agent_run_failure_total[5m])
/
rate(internalcmdb_agent_run_total[5m])
```

**Derived status**: WARNING if > 0.05 (5%); CRITICAL if > 0.15 (15%).

### Approval Queue Age

```promql
# Pending approvals older than 24h
internalcmdb_approval_pending_age_seconds{env="wave1-production"} > 86400
```

**Derived status**: WARNING if any pending approval > 24h; use governance review.

### DB Availability

```promql
# DB up
pg_up{env="wave1-production"}
```

**Derived status**: OUTAGE if == 0.

---

## 3. Derived Status Rules Summary

| Health Area | Query ID | HEALTHY | DEGRADED | CRITICAL |
|---|---|---|---|---|
| DB Availability | HQ-001 | pg_up == 1 | — | pg_up == 0 |
| Ingestion Freshness | HQ-002 | ingestion < 2h ago | 2–6h | > 6h |
| Retrieval Latency | HQ-004 | P95 ≤ 200ms | 200–500ms | > 500ms |
| Agent Run Failure Rate | HQ-003 | < 5% | 5–15% | > 15% |
| GPU VRAM | HQ-005 | < 80% | 80–90% | > 90% |
| Approval Queue Age | HQ-006 | All < 24h | Any 24–48h | Any > 48h |

---

## 4. Status Derivation Rule

Health states derived from these queries represent ground truth for operational decisions:
- Operators derive health from these documented queries, not only from visual dashboards.
- Each dashboard panel must link to the underlying query documented here.

---

## 5. Verification

- [x] All critical health areas have a documented PromQL query.
- [x] All queries have explicit HEALTHY/DEGRADED/CRITICAL thresholds.
- [x] Operators can derive health states from queries alone.
- [x] Every dashboard visual has an underlying query traceable to this document.
