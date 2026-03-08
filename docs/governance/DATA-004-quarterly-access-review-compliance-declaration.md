---
id: DATA-004
title: "Quarterly Access Review Cycle-1 and Compliance Declaration"
doc_class: operational_declaration
domain: governance
status: approved
version: "1.0"
created: 2025-07-01
updated: 2025-07-01
owner: executive_sponsor
tags: [data-governance, access-review, compliance, quarterly, m15-3]
---

# DATA-004 — Quarterly Access Review Cycle-1 and Compliance Declaration

## 1. Purpose

This document records the first quarterly privileged access review for the
internalCMDB platform (Cycle-1, Q3 2025) and issues a formal compliance
declaration confirming that all data governance controls — classification,
redaction, access enforcement, and retention — are active and tested.

**Review period**: 2025-04-01 – 2025-06-30
**Declaration date**: 2025-07-01
**Signed by**: executive_sponsor

---

## 2. Scope of Privileged Access Review

All human identities and service accounts that hold or have held any of the
following roles during the review period:

| Role | Description |
|---|---|
| `platform_engineering` | Read/write access to Class B tables; runs retention jobs |
| `platform_architecture_lead` | Schema ownership; can execute DDL changes |
| `security_and_policy_owner` | Exception review; credential rotation authority |
| `executive_sponsor` | Final approval on policy and compliance declarations |

---

## 3. Access Inventory — Cycle-1

### 3.1 Active Role Assignments

| Identity | Role(s) Held | Access Type | Justification |
|---|---|---|---|
| `svc-internalcmdb-collector` | `platform_engineering` | Service account | Automated fact collection |
| `svc-internalcmdb-retrieval` | `platform_engineering` | Service account | Retrieval broker reads Class B |
| `svc-internalcmdb-scheduler` | `platform_engineering` | Service account | Retention job executor |
| `eng-lead-01` | `platform_architecture_lead`, `platform_engineering` | Human | Schema lead |
| `sec-owner-01` | `security_and_policy_owner` | Human | Policy authority |
| `exec-sponsor-01` | `executive_sponsor` | Human | Final approvals |

### 3.2 Access Changes During Review Period

| Date | Identity | Change Type | Approved By |
|---|---|---|---|
| 2025-04-15 | `svc-internalcmdb-retrieval` | **Added** `platform_engineering` | `sec-owner-01` |
| 2025-05-01 | `svc-old-collector` | **Revoked** all roles | `sec-owner-01` |

### 3.3 Stale / Orphan Access

No stale or orphan role assignments were identified in Cycle-1.  All service
accounts are in active use.  All human identities are employed staff.

---

## 4. Access Control System Verification

The following controls were verified as operational:

| Control | Module | Verification Method | Result |
|---|---|---|---|
| Class B query enforcement | `governance.access_control.DataAccessControl` | Unit test + live request probe | **PASS** |
| Denial logging to `change_log` | `DataAccessControl._record_denial()` | Injected test probe; confirmed row in `governance.change_log` | **PASS** |
| Ingest redaction scanning | `governance.redaction_scanner.RedactionScanner` | Pattern-match unit tests on 7 credential patterns | **PASS** |
| Retention job execution | DATA-002 runbooks | Dry-run of purge SQL on non-production snapshot | **PASS** |
| Exception register | DATA-003 model + `governance.change_log` | Synthetic exception end-to-end trace recorded | **PASS** |

---

## 5. Data Classification Compliance

All 14 registry tables have been assigned a DATA-001 data class and the
assignment is enforced at the retrieval broker layer:

| Classification | Tables | Count |
|---|---|---|
| Class A (PUBLIC/INTERNAL) | `term`, `resource_kind`, `collection_run`, `policy_record`, `approval_record` | 5 |
| Class B (CONFIDENTIAL) | `observed_fact`, `chunk_embedding`, `document_chunk`, `evidence_pack`, `evidence_pack_item`, `agent_run`, `action_request`, `prompt_template_registry`, `change_log`, `document_version` | 10 |
| Class C / D | Not applicable to internalCMDB v1 | 0 |

No table classification mismatches were found.

---

## 6. Redaction Scanner Summary

During the review period:

- **Total `observed_fact` rows ingested**: 0 (system not yet in production at review cut-off)
- **Redaction rejections triggered**: 0
- **False positives investigated**: 0

The scanner is confirmed active and configured with 7 credential patterns
(see `governance.redaction_scanner._CREDENTIAL_PATTERNS`).

---

## 7. Retention Compliance Summary

| Table | Expired Rows at Review Date | Action Taken |
|---|---|---|
| `observed_fact` | 0 | N/A — system pre-production |
| `agent_run` | 0 | N/A |
| `evidence_pack` | 0 | N/A |
| `change_log` | 0 | N/A |

Retention jobs are configured and standing approvals recorded in OPS-003.

---

## 8. Exception Register Summary (Cycle-1)

| Status | Count |
|---|---|
| Opened | 0 |
| Closed within SLA | 0 |
| Escalated | 0 |
| Open at review date | 0 |

**Finding**: No governance exceptions were raised during Cycle-1.  The exception
tracking mechanism was validated via the synthetic trace in DATA-003.

---

## 9. Recommendations for Cycle-2

1. Once the system enters production, establish a baseline of monthly redaction rejection counts.
2. Validate retention job execution logs against scheduler records after each nightly run.
3. Review `svc-internalcmdb-collector` permissions against the principle of least privilege as data volume grows.

---

## 10. Compliance Declaration

I, the **executive_sponsor**, hereby declare that:

> As of **2025-07-01**, the internalCMDB data governance framework is fully
> activated and all controls listed in this document have been independently
> verified as operational.  Specifically:
>
> — Data classification (DATA-001) is complete and enforced.
> — Redaction scanning (pt-056) is active on all ingest paths.
> — Access control enforcement (pt-057) is applied at the retrieval broker.
> — Retention and deletion runbooks (DATA-002) are documented and tested.
> — The exception register (DATA-003) is operational and the 30-day escalation rule is in force.
> — This Cycle-1 access review confirms all role assignments are justified and current.
>
> This platform is compliant with the internalCMDB data governance policy as of
> the date above.

**Signed**: `exec-sponsor-01` (executive_sponsor)
**Date**: 2025-07-01
**Next review**: 2025-10-01 (Cycle-2)
