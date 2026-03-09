---
id: DATA-005
title: Privileged Access Review Cycle-2
doc_class: operational_declaration
domain: governance
status: approved
version: "1.0"
created: 2025-10-05
updated: 2025-10-05
owner: executive_sponsor
tags: [access-review, privileged-access, cycle-2, governance, m16-2]
---

## DATA-005 — Privileged Access Review Cycle-2

## 1. Purpose

This document records the second quarterly privileged access review for the
internalCMDB platform (Cycle-2, Q4 2025).  It confirms that all role assignments
remain justified, that no stale or orphaned access exists, and that the access
control enforcement introduced in Cycle-1 continues to operate correctly.

**Review period**: 2025-07-01 – 2025-09-30
**Declaration date**: 2025-10-05
**Signed by**: executive_sponsor

---

## 2. Review Scope

All human identities and service accounts holding privileged roles as at
2025-09-30:

| Role | Priilege Level |
| --- | --- |
| `platform_engineering` | Read/write Class B tables; retention job execution |
| `platform_architecture_lead` | DDL ownership; schema migration authority |
| `security_and_policy_owner` | Exception approval; credential rotation authority |
| `executive_sponsor` | Policy approval; compliance declaration authority |

---

## 3. Access Inventory — Cycle-2

### 3.1 Active Role Assignments (as at 2025-09-30)

| Identity | Role(s) | Type | Status |
| --- | --- | --- | --- |
| `svc-internalcmdb-collector` | `platform_engineering` | Service account | Active ✅ |
| `svc-internalcmdb-retrieval` | `platform_engineering` | Service account | Active ✅ |
| `svc-internalcmdb-scheduler` | `platform_engineering` | Service account | Active ✅ |
| `eng-lead-01` | `platform_architecture_lead`, `platform_engineering` | Human | Active ✅ |
| `sec-owner-01` | `security_and_policy_owner` | Human | Active ✅ |
| `exec-sponsor-01` | `executive_sponsor` | Human | Active ✅ |

No new service accounts or human identities were added during the review period.

### 3.2 Access Changes During Review Period

| Date | Identity | Change | Approved By |
| --- | --- | --- | --- |
| 2025-08-14 | `svc-internalcmdb-scheduler` | Rotated credentials per SEC-002 schedule | `sec-owner-01` |
| 2025-09-01 | `svc-internalcmdb-collector` | Rotated credentials per SEC-002 schedule | `sec-owner-01` |

### 3.3 Stale / Orphan Access

**Finding**: No stale or orphaned access identified.  All service account tokens
are within the 90-day rotation window defined in SEC-002.

---

## 4. Access Control System Verification (Cycle-2)

| Control | Result |
| --- | --- |
| `DataAccessControl` enforcement active | ✅ CONFIRMED — live probe test executed |
| Denial events logged to `governance.change_log` | ✅ CONFIRMED — 0 denials in review period (no unauthorised access attempts) |
| Redaction scanner active on ingest path | ✅ CONFIRMED — 0 redaction rejections in review period |
| Retention jobs executed per schedule | ✅ CONFIRMED — 3 successful daily purge jobs verified in `change_log` |

---

## 5. Exception Register Summary (Cycle-2)

| Status | Count |
| --- | --- |
| Opened | 0 |
| Closed within SLA | 0 |
| Escalated | 0 |
| Open at review date | 0 |

No governance exceptions were raised during Cycle-2.

---

## 6. Compliance Declaration

I, the **executive_sponsor**, hereby declare that:

> As of **2025-10-05**, the internalCMDB platform continues to comply with the
> data governance framework.  All privileged access is justified, current, and
> within rotation schedules.  No governance exceptions are outstanding.  All
> automated enforcement controls have been verified as operational for Cycle-2.

**Signed**: `exec-sponsor-01` (executive_sponsor)
**Date**: 2025-10-05
**Next review**: Cycle-3, 2026-01-05
