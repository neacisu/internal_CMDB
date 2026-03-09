---
id: OPS-003
title: internalCMDB — Recurring Service Access and Incident Review Cadences (Wave-1)
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [review-cadence, governance-rituals, access-review, wave-1, m14-3]
depends_on: [OPS-001, OPS-002]
---

# internalCMDB — Recurring Review Cadences

## 1. Purpose

Operational review calendar and recurring governance rituals for service health and privileged access.
Satisfies pt-045 [m14-3].

---

## 2. Review Calendar

| Cadence | Review Type | Owner | Deliverable |
| --- | --- | --- | --- |
| Weekly | Service health review | platform_architecture_lead | Health summary in governance.change_log |
| Weekly | Alert triage | platform_architecture_lead | Unacknowledged alerts cleared or triaged |
| Monthly | Service review meeting | platform_architecture_lead + security_and_policy_owner | Meeting minutes in governance.change_log |
| Monthly | Incident review | platform_architecture_lead | Incident log review; postmortems completed |
| Quarterly | Access review | security_and_policy_owner | Privileged access review record |
| Quarterly | Backup/restore drill | platform_architecture_lead | Drill record (see CONT-003 format) |
| Quarterly | Dependency scan | security_and_policy_owner | pip-audit + trivy results |
| Bi-annual | API key rotation | security_and_policy_owner | Rotation record in governance.change_log |
| Annual | SSH key rotation | platform_architecture_lead | Rotation record in governance.change_log |

---

## 3. Service Health Review (Weekly)

Checklist:

- [ ] Grafana dashboards reviewed: db-registry-health, db-retrieval-quality, db-approval-governance
- [ ] No unacknowledged P2+ alerts open > 24h
- [ ] DB connection pool wait time < 10ms (P95)
- [ ] ANN retrieval recall ≥ 0.87
- [ ] Agent run failure rate < 5%
- [ ] Last backup age < 24h

Output: Single entry in governance.change_log with `change_type=service_health_review`.

---

## 4. Monthly Service Review Meeting

Agenda:

1. Review open incidents from previous month.
2. Review open corrective actions (from CONT-003 or earlier DR exercises).
3. Review any SLO breaches (OBS-001).
4. Review access and credential status.
5. Review dependency scan results.
6. Confirm backup drill schedule.

Output: Meeting minutes in governance.change_log.

---

## 5. Quarterly Access Review

Checklist:

- [ ] All privileged credentials (DB, SSH, API keys) listed and verified.
- [ ] No undocumented access exists on DB or host.
- [ ] Any departed engineers' access confirmed revoked.
- [ ] Bootstrap credentials reviewed (SEC-002 §2).
- [ ] Service accounts reviewed and confirmed active.

Output: access_review record in governance.change_log. Signed by security_and_policy_owner.

---

## 6. Governance Drift Detection

Any of the following triggers an immediate unscheduled review:

- A privileged access event with no corresponding change_log entry.
- An SLO breach sustained > 7 days without a remediation record.
- A DB schema migration with no rollback verification record.
- An alert firing for > 48 hours without acknowledgment.

---

## 7. Verification

- [x] Review calendar covers weekly, monthly, quarterly, and annual cadences.
- [x] Each review type has a named owner and a deliverable.
- [x] Governance drift detection triggers are defined.
- [x] Recurring reviews are scheduled, owned, and capable of catching drift over time.
