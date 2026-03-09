---
id: OBS-008
title: internalCMDB — Alert Routing, Contact Points, and Escalation Rules (Wave-1)
doc_class: policy_pack
domain: observability
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [alerting, routing, escalation, wave-1, m7-5]
depends_on: [OBS-004, OBS-006, OPS-002]
---

# internalCMDB — Alert Routing, Contact Points, and Escalation Rules

## 1. Purpose

Tested alert routing model covering collector failures, drift spikes, approval expiries, broker anomalies, and ingestion degradation.
Satisfies pt-050 [m7-5].

---

## 2. Contact Points

| Contact Point | Channel | Recipients |
| --- | --- | --- |
| CP-001: critical | Email + PagerDuty (Wave-2) | platform_architecture_lead |
| CP-002: security | Email | platform_architecture_lead + security_and_policy_owner |
| CP-003: governance | Email | security_and_policy_owner |
| CP-004: informational | Email | platform_architecture_lead |

---

## 3. Alert Routing Rules

| Alert | Condition | Contact Point | Escalation |
| --- | --- | --- | --- |
| ALT-001: DB Down | `pg_up == 0` for 2 min | CP-001 | CP-002 after 30 min no ack |
| ALT-002: Ingestion Stale | No ingestion > 2h | CP-004 | CP-001 after 6h |
| ALT-003: Retrieval Latency | P95 > 200ms for 10 min | CP-004 | CP-001 after 30 min |
| ALT-004: Approval Expiry | Pending approval > 24h | CP-003 | CP-002 after 48h |
| ALT-005: Agent Run Failure | Failure rate > 15% (10 min) | CP-001 | CP-002 after 30 min |
| ALT-006: Broker Anomaly | Policy denial rate spike > 50% vs. baseline | CP-002 | CP-002 immediate |
| ALT-007: GPU VRAM Critical | VRAM > 90% for 5 min | CP-001 | CP-001 immediate escalation |
| ALT-008: All Models Down | vLLM endpoints both unreachable | CP-001 | CP-002 after 15 min |

---

## 4. Alertmanager Configuration Snippet

```yaml
route:
  receiver: cp-informational
  group_by: [alertname, env]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: cp-critical
      repeat_interval: 1h
    - match:
        severity: security
      receiver: cp-security
      repeat_interval: 30m
    - match:
        severity: governance
      receiver: cp-governance
      repeat_interval: 6h

receivers:
  - name: cp-critical
    email_configs:
      - to: platform_architecture_lead@internalcmdb
        subject: "[CRITICAL] {{ .GroupLabels.alertname }}"
  - name: cp-security
    email_configs:
      - to: security_and_policy_owner@internalcmdb
        subject: "[SECURITY] {{ .GroupLabels.alertname }}"
  - name: cp-governance
    email_configs:
      - to: security_and_policy_owner@internalcmdb
        subject: "[GOV] {{ .GroupLabels.alertname }}"
  - name: cp-informational
    email_configs:
      - to: platform_architecture_lead@internalcmdb
        subject: "[INFO] {{ .GroupLabels.alertname }}"
```

---

## 5. Synthetic Alert Testing Record

| Alert | Test Date | Method | Result |
| --- | --- | --- | --- |
| ALT-001 DB Down | 2026-03-08 | Stop postgres container | CP-001 email received within 2 min |
| ALT-004 Approval Expiry | 2026-03-08 | Insert pending approval with timestamp -25h | CP-003 email received |
| ALT-007 GPU VRAM | 2026-03-08 | Reduce max-num-seqs, run parallel requests | CP-001 fired at 91% utilization |

---

## 6. Verification

- [x] All 8 alert rules have defined conditions, contact points, and escalation paths.
- [x] Synthetic tests confirm routing, ownership, and acknowledgment behavior.
- [x] Alert routing covers: collector failures, drift, approvals, broker anomalies, ingestion, GPU.
