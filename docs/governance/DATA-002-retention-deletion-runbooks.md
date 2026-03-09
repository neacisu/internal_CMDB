---
id: DATA-002
title: "Data Retention and Deletion Runbooks"
doc_class: runbook
domain: governance
status: approved
version: "1.0"
created: 2025-07-01
updated: 2025-07-01
owner: security_and_policy_owner
tags: [data-governance, retention, deletion, runbook, m15-2]
---

## DATA-002 — Data Retention and Deletion Runbooks

## 1. Purpose

This runbook defines the per-data-class retention windows and the exact deletion
procedures for every table in the internalCMDB registry.  All DELETE operations
are executed by a member of the **platform_engineering** team after explicit
**security_and_policy_owner** approval.

## 2. Retention Schedule

| Table | Data Class | Retention Window | Trigger |
| --- | --- | --- | --- |
| `observed_fact` | B | 90 days from `collected_at` | Rolling daily job |
| `chunk_embedding` | B | 90 days from parent `observed_fact` deletion | Cascade |
| `document_chunk` | B | 90 days from parent `document_version` archival | Cascade |
| `evidence_pack` | B | 180 days from `created_at` unless linked to open task | Rolling weekly job |
| `evidence_pack_item` | B | Cascade from `evidence_pack` | Cascade |
| `agent_run` | B | 365 days from `started_at` | Rolling monthly job |
| `action_request` | B | 365 days from `created_at` | Rolling monthly job |
| `prompt_template_registry` | B | Retain while `is_active = true`; archive after 365 days inactive | Manual + monthly sweep |
| `change_log` | B | 730 days (2 years) from `changed_at` (regulatory) | Rolling annual job |
| `document_version` | B | 180 days from `archived_at` (or until all chunks deleted) | Cascade-aware job |
| `collection_run` | A | 90 days from `started_at` | Rolling daily job |
| `term` | A | Retained indefinitely while referenced | Manual de-listing |
| `resource_kind` | A | Retained indefinitely | Manual |
| `policy_record` | A | Retained indefinitely | Manual |
| `approval_record` | A | 730 days from `approved_at` | Rolling annual job |

## 3. FK Cascade Behaviour

The PostgreSQL schema uses `ON DELETE CASCADE` on the following paths:

```text
collection_run → observed_fact → chunk_embedding
document_version → document_chunk
evidence_pack → evidence_pack_item
```

**Important**: deletions of `collection_run` or `document_version` rows will
cascade silently.  Always check downstream row counts before deleting parent
rows.

```sql
-- Pre-deletion check: count children before removing a collection_run
SELECT COUNT(*) FROM discovery.observed_fact
WHERE collection_run_id = :'target_run_id';

SELECT COUNT(*) FROM registry.chunk_embedding ce
JOIN discovery.observed_fact of ON of.id = ce.observed_fact_id
WHERE of.collection_run_id = :'target_run_id';
```

## 4. Runbook: Daily Observed-Fact Purge

**Responsible**: platform_engineering
**Frequency**: daily, 02:00 UTC
**Approval gate**: standing approval granted in OPS-003 quarterly cadence review

```sql
-- Step 1: Identify expired rows
SELECT id, collected_at, fact_namespace, entity_kind_term_id
FROM discovery.observed_fact
WHERE collected_at < NOW() - INTERVAL '90 days'
LIMIT 1000;   -- process in batches of 1000

-- Step 2: Delete (cascades to chunk_embedding)
DELETE FROM discovery.observed_fact
WHERE id IN (
    SELECT id FROM discovery.observed_fact
    WHERE collected_at < NOW() - INTERVAL '90 days'
    ORDER BY collected_at
    LIMIT 1000
);

-- Step 3: Record deletion in change_log
INSERT INTO governance.change_log (
    change_code, entity_kind_term_id, entity_id,
    change_source_text, change_summary_text, changed_by, changed_at
) VALUES (
    'retention-purge-observed-fact-' || TO_CHAR(NOW(), 'YYYYMMDDHHMMSS'),
    '00000000-0000-0000-0000-000000000000',
    '00000000-0000-0000-0000-000000000000',
    'retention_job',
    'Purged observed_fact rows older than 90 days (batch 1000)',
    'platform_engineering',
    NOW()
);
```

## 5. Runbook: Evidence-Pack 180-Day Purge

**Responsible**: platform_engineering
**Frequency**: weekly, Sunday 03:00 UTC
**Approval gate**: standing approval from security_and_policy_owner

```sql
-- Step 1: Identify expired packs not linked to any open task
SELECT id, created_at
FROM retrieval.evidence_pack
WHERE created_at < NOW() - INTERVAL '180 days'
  AND id NOT IN (
      SELECT evidence_pack_id FROM registry.action_request
      WHERE status_term_id IS NOT NULL
  )
LIMIT 500;

-- Step 2: Delete (cascades to evidence_pack_item)
DELETE FROM retrieval.evidence_pack
WHERE id IN (
    SELECT id FROM retrieval.evidence_pack
    WHERE created_at < NOW() - INTERVAL '180 days'
      AND id NOT IN (
          SELECT evidence_pack_id FROM registry.action_request
          WHERE status_term_id IS NOT NULL
      )
    ORDER BY created_at
    LIMIT 500
);
```

## 6. Runbook: Agent-Run / Action-Request 365-Day Purge

**Responsible**: platform_engineering
**Frequency**: monthly, 1st of month 04:00 UTC
**Approval gate**: security_and_policy_owner confirmation per run

```sql
-- Agent runs
DELETE FROM registry.agent_run
WHERE started_at < NOW() - INTERVAL '365 days'
  AND id NOT IN (
      SELECT agent_run_id FROM registry.action_request WHERE status_term_id IS NOT NULL
  );

-- Action requests
DELETE FROM registry.action_request
WHERE created_at < NOW() - INTERVAL '365 days';
```

## 7. Runbook: Emergency / Ad-Hoc Deletion

Triggered by a GDPR removal request, security incident, or executive directive.

1. **Request**: logged in `governance.change_log` with `change_source_text = 'emergency_deletion_request'`.
2. **Approval**: security_and_policy_owner signs off within 4 hours.
3. **Execution**: platform_engineering runs targeted DELETE within a transaction.
4. **Verification**: run `SELECT COUNT(*) …` to confirm zero remaining rows.
5. **Closure**: second `change_log` entry with `change_source_text = 'emergency_deletion_confirmed'`.

```sql
BEGIN;

DELETE FROM discovery.observed_fact
WHERE entity_id = :'target_entity_id';

-- Verify
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM discovery.observed_fact WHERE entity_id = :'target_entity_id'
    ) THEN
        RAISE EXCEPTION 'Emergency deletion incomplete — rows still present';
    END IF;
END $$;

COMMIT;
```

## 8. Verification Checklist

After any purge job:

- [ ] Row-count deltas match job log.
- [ ] `change_log` entry recorded.
- [ ] No orphaned `chunk_embedding` rows without parent `observed_fact`.
- [ ] No orphaned `evidence_pack_item` rows without parent `evidence_pack`.
- [ ] Monitoring alert `retention_purge_job_succeeded` fired within the expected window.
