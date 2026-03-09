---
id: CAP-004
title: Load Test v2 Regression Comparison Report
doc_class: research_dossier
domain: platform-foundations
status: approved
version: "1.0"
created: 2025-10-01
updated: 2025-10-01
owner: platform_architecture_lead
tags: [load-test, regression, performance, cycle-2, m16-1]
---

## CAP-004 — Load Test v2 Regression Comparison Report

## 1. Purpose

This dossier compares the results of the Load Test v2 (Cycle-2, Q4 2025) against
the CAP-002 Cycle-1 baseline, identifies performance regressions, and records
acceptance decisions for continued operations.

**Test date**: 2025-10-02
**Environment**: staging (mirrors production cluster spec)
**Coordinator**: platform_architecture_lead
**Tool**: k6 v0.52 (same as Cycle-1)

---

## 2. Test Configuration

| Parameter | Cycle-1 (CAP-002) | Cycle-2 (this doc) |
| --- | --- | --- |
| Scenario | Ramp 0→50 VU over 2 min; hold 50 VU for 5 min; ramp down | Ramp 0→50 VU over 2 min; hold 50 VU for 5 min; ramp down |
| Target endpoint | `/api/v1/facts/search` | `/api/v1/facts/search` |
| Data volume | 120k `observed_fact` rows | 210k `observed_fact` rows |
| Think time | 500 ms | 500 ms |

---

## 3. Results Comparison

### 3.1 Throughput and Latency

| Metric | Cycle-1 | Cycle-2 | Δ | Status |
| --- | --- | --- | --- | --- |
| Requests/s (steady state) | 312 | 298 | −14 (−4.5%) | ✅ Within tolerance |
| p50 latency | 42 ms | 47 ms | +5 ms (+11.9%) | ✅ Within tolerance |
| p95 latency | 118 ms | 131 ms | +13 ms (+11%) | ✅ Within tolerance |
| p99 latency | 204 ms | 228 ms | +24 ms (+11.8%) | ✅ Within tolerance |
| Error rate | 0.02% | 0.03% | +0.01% | ✅ Within tolerance |

Tolerance thresholds (from CAP-001 §4): p95 ≤ 200 ms; p99 ≤ 400 ms; error rate < 0.1%.

### 3.2 Resource Utilisation

| Resource | Cycle-1 | Cycle-2 | Δ |
| --- | --- | --- | --- |
| CPU (PostgreSQL, peak) | 38% | 43% | +5% |
| Memory (PostgreSQL, peak) | 2.1 GiB | 2.4 GiB | +0.3 GiB |
| Connections at peak | 48 / 100 max | 49 / 100 max | +1 |
| pgvector query time (p95) | 62 ms | 71 ms | +9 ms (+14.5%) |

---

## 4. Regression Analysis

### Finding R-001 — Latency Increase Proportional to Data Growth

All latency metrics increased by ~11–12%, consistent with the data volume growth
from 120k to 210k rows (+75%).  The increase is sub-linear, indicating that
existing indexes are effective.

**Root cause**: larger table scan for similarity search as corpus grows.
**Remediation**: No action required at this scale.  Monitor p95 latency threshold
alert (currently set at 200 ms — projected to be reached at ~600k rows; see CAP-001).

### Finding R-002 — pgvector Query Time Regression

pgvector similarity search p95 increased from 62 ms to 71 ms (+14.5%).

**Root cause**: HNSW index not yet rebuilt after data growth pass; index was
created at 100k rows.
**Remediation**: Schedule index rebuild (`REINDEX INDEX CONCURRENTLY`) during
the next maintenance window.  Expected to bring pgvector p95 back to ≤65 ms.

---

## 5. SLA Compliance

| SLA | Target | Cycle-2 Result | Status |
| --- | --- | --- | --- |
| p95 latency | ≤ 200 ms | 131 ms | ✅ PASS |
| p99 latency | ≤ 400 ms | 228 ms | ✅ PASS |
| Error rate | < 0.1% | 0.03% | ✅ PASS |
| Throughput degradation | ≤ 20% vs baseline | −4.5% | ✅ PASS |

---

## 6. Action Items

| ID | Description | Owner | Due |
| --- | --- | --- | --- |
| C2-LT-001 | Rebuild HNSW index concurrently next maintenance window | platform_engineering | 2025-10-10 |
| C2-LT-002 | Lower p95 latency alert threshold from 200 ms to 150 ms as early warning | platform_engineering | 2025-10-15 |

---

## 7. Sign-off

**Test verdict**: PASS — all SLAs met; two low-severity action items raised.
**Signed**: platform_architecture_lead
**Date**: 2025-10-02
**Next test**: Cycle-3, Q1 2026-01-06
