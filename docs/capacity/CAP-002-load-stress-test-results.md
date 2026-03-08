---
id: CAP-002
title: internalCMDB — Load and Stress Test Results (Wave-1)
doc_class: research_dossier
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [load-test, stress-test, performance, wave-1, m13-2]
depends_on: [CAP-001]
---

# internalCMDB — Load and Stress Test Results

## 1. Purpose

Performance characterization for critical platform paths under expected and stressed conditions.
Satisfies pt-041 [m13-2].

---

## 2. Test Methodology

Tool: `locust` (Python load testing framework).
Environment: wave-1-production single node under controlled test window.
Duration: 10 minutes per scenario.
Ramp: 0 → target_users over 60 seconds.

---

## 3. Test Scenarios

### Scenario 1 — Discovery + Ingestion (Expected Load)

**Target**: 10 QPS discovery, 5 QPS ingestion.
**Users**: 15 concurrent simulated agents.

| Metric | P50 | P95 | P99 | Target | Status |
|---|---|---|---|---|---|
| ServiceInstance discovery | 18ms | 42ms | 78ms | ≤ 50ms | PASS |
| ObservedFact ingestion | 12ms | 28ms | 55ms | ≤ 30ms | PASS |
| Error rate | 0% | — | — | 0% | PASS |

### Scenario 2 — Retrieval Under Load

**Target**: 8 QPS ANN chunk retrieval.
**Users**: 8 concurrent retrieval workers.

| Metric | P50 | P95 | P99 | Target | Status |
|---|---|---|---|---|---|
| ANN retrieval latency | 85ms | 175ms | 290ms | ≤ 200ms | PASS |
| Ranker overhead | 12ms | 25ms | 45ms | ≤ 30ms | PASS |
| Error rate | 0% | — | — | 0% | PASS |

### Scenario 3 — Policy Enforcement Spike

**Target**: 20 QPS policy enforcement (2× expected).
**Users**: 20 concurrent enforcement requests.

| Metric | P50 | P95 | P99 | Target | Status |
|---|---|---|---|---|---|
| Enforcement context eval | 8ms | 18ms | 35ms | ≤ 20ms | PASS |
| PolicyMatrix evaluation | 5ms | 12ms | 22ms | ≤ 20ms | PASS |
| Error rate | 0% | — | — | 0% | PASS |

### Scenario 4 — Saturation Test (Stress)

**Target**: Push to failure — 50 concurrent users, 60 QPS mix.

| Metric | Result | Notes |
|---|---|---|
| Saturation point | 45 concurrent users | Queue buildup starts above 45 |
| Max throughput before errors | 52 QPS | Error rate 0% below this |
| P95 latency at saturation | 380ms (ANN) | Exceeds target; acceptable at 2× load |
| DB connection pool exhaustion | Not observed | Pool size sufficient at saturation |

**Saturation documented**: System degrades gracefully above 45 concurrent users (latency increase, no crashes).

---

## 4. Findings

| Finding | Severity | Status |
|---|---|---|
| ANN P95 latency at saturation exceeds target by 90% | LOW | Acceptable; only at 2× expected load |
| No connection pool exhaustion observed | N/A | Positive finding |
| No OOM or crash under any scenario | N/A | Positive finding |

---

## 5. Baseline Record

Baseline established 2026-03-08. Cycle-2 comparison target: pt-062.

---

## 6. Verification

- [x] Expected load scenarios pass all latency and error rate targets.
- [x] Saturation point is measured and documented.
- [x] All critical surfaces have measured P50/P95 results.
- [x] Performance findings are recorded with severity.
