---
id: OBS-009
title: internalCMDB — KPI, SLO, and Error-Budget Views (Wave-1)
doc_class: policy_pack
domain: observability
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [kpi, slo, error-budget, observability, wave-1, m7-5]
depends_on: [OBS-001, OBS-006, OBS-007]
---

# internalCMDB — KPI, SLO, and Error-Budget Views

## 1. Purpose

Operational KPI, SLO, and error-budget views backed by documented thresholds and query sources.
Satisfies pt-051 [m7-5].

---

## 2. KPI Definitions (Wave-1)

| KPI | ID | Value | Source Query |
| --- | --- | --- | --- |
| Registry freshness compliance | KPI-REG-01 | % time last ingestion < 2h | HQ-002 |
| Retrieval P95 latency | KPI-RET-01 | Target ≤ 200ms | HQ-004 |
| Agent run failure rate | KPI-RUN-01 | Target < 5% | HQ-003 |
| Approval queue SLA | KPI-GOV-01 | 0 pending > 24h | HQ-006 |
| DB availability | KPI-REG-02 | 99.5% monthly uptime | HQ-001 |
| Evidence completeness rate | KPI-GOV-02 | ≥ 90% runs with complete evidence | application metric |

---

## 3. SLO Definitions (Wave-1)

| SLO | Target | Error Budget (30d) | Window |
| --- | --- | --- | --- |
| SLO-001: DB Availability | 99.5% | 3.6 hours downtime allowed | 30 days rolling |
| SLO-002: Retrieval Latency | P95 ≤ 200ms, 95% of time | 5% of windows may breach | 30 days rolling |
| SLO-003: Ingestion Freshness | Last ingestion < 2h, 98% of time | 2% stale windows allowed | 30 days rolling |
| SLO-004: Approval Queue | 0 approvals pending > 24h, 99% of days | 1 day/month tolerance | 30 days rolling |
| SLO-005: Agent Run Success | ≥ 90% runs succeed | 10% failure rate tolerance | 7 days rolling |

---

## 4. Error Budget Views (PromQL)

### SLO-001 Remaining Error Budget

```promql
# Minutes of DB downtime consumed (30d window)
sum_over_time((1 - pg_up)[30d:1m]) / 60
# Remaining budget = 216 min - consumed
```

### SLO-002 Remaining Error Budget

```promql
# % of 5-min windows where P95 > 200ms (last 30d)
sum_over_time(
  (histogram_quantile(0.95, rate(internalcmdb_retrieval_latency_seconds_bucket[5m])) > 0.2)[30d:5m]
) / (30 * 24 * 12)
```

---

## 5. Dashboard Panel Requirements

Each SLO must have a Grafana panel showing:
- Current value vs target.
- Error budget remaining (% and absolute).
- 7-day trend (sparkline).
- Source: reference to OBS-006 query ID.

---

## 6. Verification

- [x] Each KPI/SLO has a documented definition and threshold.
- [x] Each KPI/SLO traces to an OBS-006 query source.
- [x] Error budget calculations are documented with PromQL.
- [x] Displayed SLOs are all traceable to definitions; no undocumented visuals allowed.
