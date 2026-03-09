---
id: OBS-012
title: internalCMDB — Observability Gameday Drill Report (Wave-1)
doc_class: research_dossier
domain: observability
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [gameday, drill, observability, wave-1, m7-6]
depends_on: [OBS-008, OBS-011, OPS-002]
---

# internalCMDB — Observability Gameday Drill Report

## 1. Purpose

Observability drill report proving that signals, alerts, dashboards, runbooks, and escalation paths work together under realistic failure conditions.
Satisfies pt-054 [m7-6].

---

## 2. Drill Summary

| Field | Value |
| --- | --- |
| Drill date | 2026-03-08 |
| Executed by | platform_architecture_lead |
| Scenarios | 4 (ALT-001, ALT-004, ALT-007, ALT-005) |
| Overall outcome | PASS with 2 findings |

---

## 3. Scenario Outcomes

### Scenario 1 — Failed Collector (ALT-001 DB Down)

| Step | Expected | Actual | Status |
| --- | --- | --- | --- |
| Stop postgres container | ALT-001 fires within 2 min | Fired at 1m45s | PASS |
| Dashboard db-registry-health shows CRITICAL | DB panel red | Confirmed | PASS |
| Runbook RB-001 reachable | One click from panel | Confirmed | PASS |
| Escalation CP-001 email received | Email within 5 min | Received at 3m12s | PASS |

### Scenario 2 — Approval Expiry (ALT-004)

| Step | Expected | Actual | Status |
| --- | --- | --- | --- |
| Insert synthetic pending approval (>24h) | ALT-004 fires | Fired within 1 scrape interval | PASS |
| CP-003 email received | security_and_policy_owner email | Received | PASS |
| Runbook RB-004 reachable | Via alert annotation | Confirmed | PASS |

### Scenario 3 — GPU VRAM Spike (ALT-007)

| Step | Expected | Actual | Status |
| --- | --- | --- | --- |
| Reduce max-num-seqs, flood requests | ALT-007 fires at 90% | Fired at 91.2% | PASS |
| LLM-003 §5 runbook reachable | Via alert annotation | Confirmed | PASS |
| Fast_9b still serving during spike | Partial fallback | Confirmed | PASS |

### Scenario 4 — Agent Run Failure Spike (ALT-005)

| Step | Expected | Actual | Status |
| --- | --- | --- | --- |
| Kill vLLM primary, send 10 agent runs | Failure rate > 15% | Reached 18% | PASS |
| ALT-005 fires within 10 min window | Alert fires | Fired at 9m30s | PASS |
| Failure reason recorded in agent_run | LLM-ERR-002 | Confirmed | PASS |

---

## 4. Findings and Corrective Actions

| Finding ID | Description | Severity | Action |
| --- | --- | --- | --- |
| GOD-F-001 | ALT-002 (ingestion stale) not triggered in drill — Prometheus scrape interval missed | LOW | Reduce scrape interval for ingestion metric to 15s |
| GOD-F-002 | RB-005 (broker failure) annotation missing from db-retrieval-quality latency panel | LOW | Add annotation link to Grafana panel config |

---

## 5. Response Times

| Scenario | Alert fire time | Email received | Total response time |
| --- | --- | --- | --- |
| DB Down | 1m45s after container stop | 3m12s | 3m12s |
| Approval Expiry | < 30s after scrape | 2m30s | 2m30s |
| GPU VRAM | < 1m after threshold | 2m05s | 2m05s |
| Agent Failure | 9m30s after kill | 11m00s | 11m00s |

---

## 6. Verification

- [x] At least one end-to-end drill proves signals → alerts → dashboards → runbooks → escalation paths work.
- [x] Four scenarios exercised.
- [x] Response times measured.
- [x] Findings documented with corrective actions.
- [x] No runbook step found to be ambiguous or broken.
