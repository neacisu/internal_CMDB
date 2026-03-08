---
id: DATA-003
title: "Data Governance Exception Register and Escalation Model"
doc_class: policy_pack
domain: governance
status: approved
version: "1.0"
created: 2025-07-01
updated: 2025-07-01
owner: security_and_policy_owner
tags: [data-governance, exceptions, escalation, policy, m15-2]
---

# DATA-003 — Data Governance Exception Register and Escalation Model

## 1. Purpose

This document defines the exception register baseline for the internalCMDB data
governance framework, the 30-day escalation rule, and the end-to-end trace of a
synthetic exception entry.  All exceptions are persisted in
`governance.change_log` and governed by the escalation procedures below.

## 2. What Qualifies as a Governance Exception

An exception is raised when any of the following occurs:

| Category | Example | Severity |
|---|---|---|
| **Classification mismatch** | Class A table found to hold Class B data | High |
| **Access control bypass** | Query executed without `platform_engineering` role check | Critical |
| **Retention overrun** | Rows exceed defined retention window by > 7 days | Medium |
| **Redaction miss** | Credential pattern detected in persisted `fact_value_jsonb` | Critical |
| **Approval gap** | Policy change applied without `approval_record` | High |
| **Audit gap** | `change_log` entries missing for a known mutation event | High |

## 3. Exception Register Storage

All exceptions are stored in `governance.change_log` using the following convention:

| Field | Value |
|---|---|
| `change_source_text` | `governance_exception` |
| `change_summary_text` | Free text description of the exception (prefix with `[EXCEPTION]`) |
| `entity_kind_term_id` | `00000000-0000-0000-0000-000000000000` if no specific entity |
| `changed_by` | Identity of the reporter |
| `changed_at` | ISO-8601 timestamp at time of discovery |

The `change_code` must follow the pattern:
`exc-<YYYYMMDD>-<category_slug>-<3-char-random>`

Example: `exc-20250701-access-control-bypass-k7q`

## 4. The 30-Day Escalation Rule

- **Day 0**: Exception discovered and logged in `governance.change_log`.
- **Day 0–3**: Reporter assigns a remediation owner (platform_engineering or security_and_policy_owner).
- **Day 3–14**: Remediation plan documented as a follow-up `change_log` entry with `change_source_text = 'exception_remediation_plan'`.
- **Day 14–30**: Remediation implemented; closure entry logged with `change_source_text = 'exception_closed'`.
- **Day 30 (if still open)**: Auto-escalation to **security_and_policy_owner** review within 24 hours.  If unresolved after review, escalates to **executive_sponsor**.

```
Day 0 ──► exception_logged
Day 3 ──► remediation_plan (if missing: first warning)
Day 14 ──► remediation_implemented (if missing: second warning)
Day 30 ──► ESCALATION: security_and_policy_owner
Day 31+ ──► ESCALATION: executive_sponsor
```

## 5. Exception Severity and SLA

| Severity | Initial Response | Remediation Plan | Closure |
|---|---|---|---|
| Critical | 2 hours | 24 hours | 7 days |
| High | 8 hours | 3 days | 21 days |
| Medium | 24 hours | 7 days | 30 days |

## 6. Synthetic Exception Entry — End-to-End Trace

### Scenario

During a routine retention audit (see DATA-002), the platform_engineering team
discovers that `discovery.observed_fact` rows from 95 days ago (5 days past the
90-day window) are still present — a **Retention overrun** exception of severity
**Medium**.

### Step 1: Log the Exception

```sql
INSERT INTO governance.change_log (
    change_code,
    entity_kind_term_id,
    entity_id,
    change_source_text,
    change_summary_text,
    changed_by,
    changed_at
) VALUES (
    'exc-20250701-retention-overrun-r3t',
    '00000000-0000-0000-0000-000000000000',
    '00000000-0000-0000-0000-000000000000',
    'governance_exception',
    '[EXCEPTION] Retention overrun: observed_fact rows from 95+ days ago still present (expected ≤90 days). Daily purge job appears to have skipped 2 cycles due to scheduler downtime 2025-06-26–2025-06-27.',
    'platform_engineering',
    '2025-07-01T08:00:00Z'
);
```

### Step 2: Log the Remediation Plan (Day 1)

```sql
INSERT INTO governance.change_log (
    change_code, entity_kind_term_id, entity_id,
    change_source_text, change_summary_text, changed_by, changed_at
) VALUES (
    'exc-20250701-retention-overrun-r3t-plan',
    '00000000-0000-0000-0000-000000000000',
    '00000000-0000-0000-0000-000000000000',
    'exception_remediation_plan',
    'Plan: run one-time backfill DELETE for rows >90 days old; investigate and repair scheduler; add alert for missed purge cycles.',
    'platform_engineering',
    '2025-07-01T16:00:00Z'
);
```

### Step 3: Execute Remediation (Day 2)

Purge executed per DATA-002 §4 runbook.  Verification checklist completed.

### Step 4: Log Closure (Day 2)

```sql
INSERT INTO governance.change_log (
    change_code, entity_kind_term_id, entity_id,
    change_source_text, change_summary_text, changed_by, changed_at
) VALUES (
    'exc-20250701-retention-overrun-r3t-closed',
    '00000000-0000-0000-0000-000000000000',
    '00000000-0000-0000-0000-000000000000',
    'exception_closed',
    'Closure: 427 overdue rows deleted; scheduler repair confirmed; monitoring alert added. Exception resolved within 30-day SLA. Reviewed by security_and_policy_owner.',
    'security_and_policy_owner',
    '2025-07-03T10:00:00Z'
);
```

### Trace Summary

| Entry | `change_code` | `change_source_text` | Day |
|---|---|---|---|
| Discovery | `exc-20250701-retention-overrun-r3t` | `governance_exception` | 0 |
| Remediation plan | `exc-20250701-retention-overrun-r3t-plan` | `exception_remediation_plan` | 1 |
| Closure | `exc-20250701-retention-overrun-r3t-closed` | `exception_closed` | 2 |

## 7. Open Exception Baseline at Activation

At the time of DATA governance framework activation (2025-07-01), the exception
register contains **zero open exceptions**.  This document and the synthetic
entry above serve as the baseline record demonstrating that the exception
tracking mechanism functions end-to-end.

## 8. Review and Reporting

- security_and_policy_owner reviews the exception register monthly.
- A summary of open and closed exceptions is included in the quarterly access review (DATA-004).
- Closure rates and escalation events are reported to executive_sponsor annually.
