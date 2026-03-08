---
id: OPS-002
title: internalCMDB — Support Tiers, On-Call Rules, and Incident Command Baseline (Wave-1)
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [on-call, support-tiers, incident-command, wave-1, m14-2]
depends_on: [OPS-001]
---

# internalCMDB — Support Tiers, On-Call, and Incident Command

## 1. Purpose

Support and escalation operating model for critical services and incidents.
Satisfies pt-044 [m14-2].

---

## 2. Support Tiers

| Tier | Scope | Response Time | Responsible |
|---|---|---|---|
| L1 — Self-service | Non-urgent requests; dashboard access; query help | Next business day | on_call_engineer |
| L2 — Operations | Service degradation; performance alerts; non-critical failures | 4 hours | platform_architecture_lead |
| L3 — Critical Incident | Service outage; data loss risk; security event | 1 hour | platform_architecture_lead + security_and_policy_owner |
| L4 — Executive Escalation | Unresolvable L3; regulatory concern; major data breach risk | 2 hours | executive_sponsor |

---

## 3. On-Call Rules

| Rule | Detail |
|---|---|
| Coverage | Business hours (09:00–18:00 CET, Mon–Fri) in Wave-1 |
| After-hours | Alerts logged; L3 incidents page on_call_engineer via email |
| On-call rotation | Single engineer (platform_architecture_lead) in Wave-1 |
| Escalation timeout | No response within 30 min → escalate to next tier |
| Incident log | All incidents logged in governance.change_log with change_type=incident |

---

## 4. Incident Command Baseline

### Incident Levels

| Level | Criteria | Command | Duration Limit |
|---|---|---|---|
| P1 — Critical | Service outage; data unavailable | platform_architecture_lead commands; executive_sponsor informed | 4 hours to resolution or escalation |
| P2 — High | Significant degradation; SLO breach | platform_architecture_lead commands | 8 hours |
| P3 — Medium | Non-critical component failure; alert firing | on_call_engineer handles | 24 hours |
| P4 — Low | Advisory; non-urgent | Logged; resolved asynchronously | 1 week |

### Incident Response Steps

```
1. Detect — Alert fires or user reports incident.
2. Classify — Determine P1/P2/P3/P4.
3. Assign — Named incident commander per table above.
4. Communicate — Notify stakeholders per tier.
5. Investigate — Use runbooks from OBS-002; start with relevant dashboard.
6. Mitigate — Apply documented fix or rollback procedure.
7. Resolve — Confirm service restored.
8. Post-incident — Log in governance.change_log; schedule post-mortem if P1/P2.
```

---

## 5. Escalation Paths

| Trigger | Escalation Action |
|---|---|
| L2 response timeout (4h) | Escalate to L3; page platform_architecture_lead + security_and_policy_owner |
| L3 not resolved in 4h | Escalate to L4; page executive_sponsor |
| Data loss confirmed | Immediate L4; executive_sponsor alerted immediately |
| Security breach suspected | Immediate L3+L4; security_and_policy_owner takes command |

---

## 6. Verification

- [x] Support tiers are defined with response times and responsible roles.
- [x] On-call rules cover coverage hours, escalation, and logging.
- [x] Incident levels are defined with named commanders.
- [x] Incident response steps are explicit and executable.
- [x] Escalation paths are named and time-bounded.
