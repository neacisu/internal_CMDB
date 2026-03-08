---
id: OBS-002
title: internalCMDB — Retention, Audit Review Workflows and Critical Runbooks (Wave-1)
doc_class: policy_pack
domain: governance
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [retention, audit-review, runbooks, operational, wave-1, m7-2]
depends_on: [OBS-001, GOV-007, ADR-004]
---

# internalCMDB — Retention, Audit Review Workflows and Critical Runbooks

## 1. Purpose

Defines retention enforcement rules, the audit review process, and critical operational runbooks.
Satisfies pt-023 [m7-2].

---

## 2. Retention Policy

### 2.1 Retention Classes

| Data Class | Table(s) | Retention Period | Action on Expiry |
|---|---|---|---|
| Agent runs (completed) | `agent_control.agent_run` | 2 years | Archive to cold storage |
| Agent evidence | `agent_control.agent_evidence` | 2 years (with run) | Archive with parent run |
| Evidence packs | `retrieval.evidence_pack` | 1 year | Archive; chunks preserved |
| Action requests | `agent_control.action_request` | 3 years | Archive |
| Approval records | `governance.approval_record` | 5 years | Archive; never delete |
| Change log | `governance.change_log` | 5 years | Archive; never delete |
| Collection runs | `discovery.collection_run` | 1 year | Prune after 1 year |
| Evidence artifacts | `discovery.evidence_artifact` | 1 year | Prune |
| Observed facts | `discovery.observed_fact` | 6 months | Prune (superseded state) |
| Chunk embeddings | `retrieval.chunk_embedding` | Until model change | Re-embed on model upgrade |

### 2.2 Retention Enforcement

- Retention is enforced by a scheduled maintenance job (see Runbook RB-003).
- All pruning is logged in `governance.change_log` with `change_source_text='retention_job'`.
- Approval records and change logs are never deleted — only archived to read-only cold storage.
- Archives must preserve UUID identity for cross-reference continuity.

---

## 3. Audit Review Workflow

### 3.1 Review Cadence

| Review Type | Frequency | Owner | Output |
|---|---|---|---|
| Agent run completeness review | Weekly | platform_architecture_lead | Summary report |
| Policy denial pattern review | Weekly | security_and_policy_owner | Anomaly report |
| Approval expiry review | Weekly | security_and_policy_owner | Renewal list |
| Retention enforcement audit | Monthly | platform_architecture_lead | Pruning evidence report |
| Full governance audit | Quarterly | architecture_board | Compliance declaration |

### 3.2 Audit Review Checklist

Weekly review:
- [ ] All AgentRun rows produced in the past 7 days have ≥1 AgentEvidence row.
- [ ] PolicyEnforcer denial rate is within expected bounds (see OBS-001 KPI-GOV-001).
- [ ] No expired approval records have been used (cross-check action_request timestamps).
- [ ] Collection run success rate ≥99% (ALT-001 not triggered).

Monthly review (additional):
- [ ] Retention job executed and logged since last review.
- [ ] Archive integrity check passed (row counts match archive manifest).
- [ ] No gap register items escalated to CRITICAL without assigned owner.

---

## 4. Critical Runbooks

### RB-001: Failed Collection Run Recovery

**Trigger**: ALT-001 fires (3 consecutive collection run failures).

**Steps**:
1. Check `discovery.collection_run` for the failing run: `SELECT * FROM discovery.collection_run WHERE status_text='failed' ORDER BY created_at DESC LIMIT 5`.
2. Review `failure_reason_text` field for the root cause.
3. If SSH connectivity failure: run `scripts/test_cluster_ssh.py` to validate host reachability.
4. If credential expiry: rotate credential per pt-029 (RB-005) and retry collection.
5. If DB connectivity failure: check `internalcmdb-postgres` container health.
6. Once root cause resolved: re-trigger collection run via governance workflow (AC-005).
7. Confirm: new collection_run row with status=completed appears within 5 minutes.
8. Close alert; record resolution in `governance.change_log`.

**Escalation**: If unresolved after 30 minutes, escalate to platform_architecture_lead.

### RB-002: Evidence Pack Violation Recovery

**Trigger**: Evidence pack returned with violations > 0 (ALT-003 or direct broker call).

**Steps**:
1. Inspect `BrokerResult.violations` for the failing pack.
2. Identify missing mandatory context class.
3. If REGISTRY_HOST missing: check that target entity_id is a valid Host UUID.
4. If REGISTRY_SERVICE missing: confirm SharedService row exists and is is_active=True.
5. If CANONICAL_DOC missing: register a canonical document for the entity (AC-006).
6. Re-run broker for the same target to confirm violations=[].
7. Record the original violation and resolution in agent run audit.

**Escalation**: Violation rate >5% → escalate to platform_architecture_lead + security_and_policy_owner.

### RB-003: Retention Enforcement Job

**Trigger**: Monthly scheduled job or manual trigger.

**Steps**:
1. Run retention query for expired rows in each table (see Section 2.1).
2. Write archive manifest to `governance.change_log` (source='retention_job').
3. Copy expired rows to cold-storage archive (format: JSONL, gzip, bucket path: `cmdb-archive/{table}/{year}/{month}/`).
4. Execute DELETE for prunable tables (observed_fact, collection_run, evidence_artifact older than retention period).
5. Do NOT delete from approval_record, change_log — archive only.
6. Verify row counts post-deletion match archive manifest.
7. Log successful completion to `governance.change_log`.

**Rollback**: If step 4 fails mid-way, no delete commits — the job uses transactions per table.

### RB-004: Expired Approval Record Handling

**Trigger**: ALT-004 fires (expired approval rate >5%).

**Steps**:
1. Query: `SELECT * FROM governance.approval_record WHERE status_text='approved' AND expires_at < now()`.
2. For each expired record: update `status_text='expired'`.
3. Identify any ActionRequest rows with status=approved referencing expired approval records.
4. Transition those ActionRequest rows to status=denied (via ActionWorkflow.deny()).
5. Notify the requesting agent/user to resubmit with a valid approval.
6. For recurring expiry patterns: review approval duration policy with security_and_policy_owner.

### RB-005: Broker Failure Recovery

**Trigger**: RetrievalBroker raises an exception or returns unexpected empty result.

**Steps**:
1. Check database connectivity: `SELECT 1` against `internalCMDB` DB.
2. Check pgvector extension: `SELECT extname FROM pg_extension WHERE extname='vector'`.
3. If semantic stage failed: check `chunk_embedding` table for rows with this document.
4. Retry with `semantic_query_vec=None` to exercise deterministic-only stages.
5. If deterministic stages also fail: check FK integrity on target entity UUIDs.
6. If all stages fail: open an incident; do not write a partial evidence pack.

---

## 5. Runbook Index

| Runbook | Trigger Alert | Severity |
|---|---|---|
| RB-001 | ALT-001 (collection run failure) | CRITICAL |
| RB-002 | ALT-003 (pack violation rate) | WARNING |
| RB-003 | Scheduled (monthly retention) | SCHEDULED |
| RB-004 | ALT-004 (expired approvals) | WARNING |
| RB-005 | ALT-006 / broker exception | WARNING |
