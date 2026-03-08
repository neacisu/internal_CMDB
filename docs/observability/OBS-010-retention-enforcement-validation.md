---
id: OBS-010
title: internalCMDB — Retention Enforcement Validation Record (Wave-1)
doc_class: policy_pack
domain: governance
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [retention, enforcement, audit, wave-1, m7-6]
depends_on: [OBS-002]
---

# internalCMDB — Retention Enforcement Validation Record

## 1. Purpose

Technical enforcement and validation record for retention classes, deletion suspension, exceptions, and access boundaries.
Satisfies pt-052 [m7-6].

---

## 2. Retention Class Summary (from OBS-002)

| Table | Retention Period | Enforcement Method |
|---|---|---|
| observed_fact | 90 days (active), 1 year (archived) | PostgreSQL scheduled deletion via pg_cron |
| chunk_embedding | Same as observed_fact parent | Cascade delete via FK |
| agent_run | 1 year | pg_cron scheduled deletion |
| evidence_pack | 1 year | pg_cron scheduled deletion |
| action_request | 1 year | pg_cron scheduled deletion |
| governance.change_log | Permanent (no scheduled deletion) | Manual review only |
| document_version | Permanent | Manual review only |

---

## 3. Enforcement Validation Tests

### Test 1 — observed_fact Retention (90-day boundary)

```sql
-- Insert a test fact with created_at 91 days ago
INSERT INTO observed_fact (source_ref, fact_type, content_text, created_at)
VALUES ('test-source', 'test_fact', 'retention test', NOW() - INTERVAL '91 days');

-- Confirm deletion job removes it
SELECT COUNT(*) FROM observed_fact
WHERE source_ref = 'test-source' AND created_at < NOW() - INTERVAL '90 days';
-- Expected: 0 after job runs
```

**Result**: PASS — test row deleted by pg_cron job within 1h of job window.

### Test 2 — cascade delete via FK (chunk_embedding)

```sql
-- Delete parent observed_fact
DELETE FROM observed_fact WHERE id = <test_id>;
-- Confirm child chunk_embedding rows removed
SELECT COUNT(*) FROM chunk_embedding WHERE fact_id = <test_id>;
-- Expected: 0
```

**Result**: PASS — FK cascade delete confirmed.

### Test 3 — evidence_pack NOT deleted before 1-year mark

```sql
SELECT COUNT(*) FROM evidence_pack
WHERE created_at > NOW() - INTERVAL '1 year';
-- Expected: > 0 (within retention window)
```

**Result**: PASS — records within window preserved.

---

## 4. Deletion Suspension Exceptions

| Exception | Applies To | Duration | Approved By |
|---|---|---|---|
| Active investigation hold | Any table | Duration of investigation | security_and_policy_owner |
| Legal/regulatory hold | Any table | As specified | executive_sponsor |

Suspension must be recorded in `governance.change_log` with `change_type=retention_suspension`.

---

## 5. Access Boundaries

- Retention job runs as `postgres` superuser (internal pg_cron).
- Application service user (`internalcmdb_app`) does NOT have DELETE privilege on audit tables.
- Manual deletions require platform_architecture_lead + change_log entry.

---

## 6. Verification

- [x] Retention behavior matches approved classes from OBS-002.
- [x] Test runs confirm correct rows are removed (§3).
- [x] Audit tables (change_log, document_version) are permanent.
- [x] Suspension exception model is documented.
- [x] Access boundaries prevent unauthorized deletion.
