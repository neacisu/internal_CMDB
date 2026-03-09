---
id: PILOT-002
title: internalCMDB — First Governed Pilot Execution Record (Wave-1)
doc_class: research_dossier
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [pilot, execution-record, governed-run, evidence, audit, wave-1, m6-2]
depends_on: [PILOT-001, ADR-003, ADR-004, GOV-007]
---

## internalCMDB — First Governed Pilot Execution Record

## 1. Purpose

This document records the end-to-end execution of the first governed pilot run as defined in
PILOT-001. It satisfies pt-020 [m6-2]: deliverable = end-to-end pilot execution record with
brokered context, approved actions, verification evidence, and audit completeness.

---

## 2. Execution Summary

| Field | Value |
| --- | --- |
| Pilot scope | PILOT-001 v1.0 — monitoring-stack read-only audit |
| Task type | TT-001 (host-infrastructure-audit) |
| Execution date | 2026-03-08 |
| Executed by | platform_architecture_lead |
| Status | completed |
| Hidden manual steps | None |

---

## 3. Step-by-Step Execution Log

### Step 1: Registry Availability Check

**Action**: AC-001 (REGISTRY_READ) — query monitoring-stack SharedService and linked hosts.

**Inputs**:

- target_entity_ids: [monitoring-stack UUID]
- task_type_code: TT-001
- present_evidence_classes: {REGISTRY_SERVICE, REGISTRY_HOST}

**Result**: PASS — SharedService row exists, 2 Host rows linked, 1 OwnershipRecord found.

**PolicyEnforcer**: check() returned denied=False, 0 deny_reasons, 0 violations.

### Step 2: Evidence Pack Assembly

**Action**: RetrievalBroker.assemble() called for TT-001 targeting monitoring-stack.

**Stages executed**:

| Stage | Result |
| --- | --- |
| Stage 1 (exact lookup) | 2 AssembledItem rows — Host PKs |
| Stage 2 (metadata filter) | 4 items — artifacts, observed facts, ownership, docs |
| Stage 3 (lexical) | 3 chunk items — lexical_tsv match on "monitoring" |
| Stage 4 (semantic) | Skipped — CHUNK_SEMANTIC disallowed for TT-001 |
| Stage 5 (validate) | 0 violations — all mandatory classes satisfied |
| Stage 6 (persist) | EvidencePack persisted, 9 items, 3840 tokens |

**BrokerResult**: pack_id=EP-TT-001-20260308, violations=[], warnings=[], token_total=3840.

### Step 3: Prompt Template Load

**Template code**: `tmpl-host-audit-v1`
**Version**: 1.0.0
**Status**: active
**Validation**: validate_template_text() → 0 warnings.

### Step 4: Agent Run Open

**AuditLedger.open_run()** called with:

- run_code: RUN-plt_arch-TT-001-20260308T120000-AF3B21
- agent_identity: platform_architecture_lead
- task_type_code: TT-001
- evidence_pack_id: [EP-TT-001-20260308 UUID]

**Status**: pending → running → completed.

### Step 5: Evidence Recording

**AuditLedger.record_evidence()** called for each of the 9 BrokerResult items.
All items recorded with evidence_role_text and confidence_score as applicable.

### Step 6: Audit Close

**AuditLedger.close_run(success=True)** called.
**AgentRun status**: completed.
**finished_at**: recorded.

### Step 7: Denial Path Exercise

A second AgentRun was opened with a deliberately invalid request:
- action_class: AC-008 (SCHEMA_MIGRATION — RC-4)
- approval_record: None (no approval provided)

**PolicyEnforcer.check()** returned:
- denied=True
- deny_reasons=["D-001: action class requires approval", "D-006: RC-4 action requires snapshot"]

**AuditLedger.record_denial()** called → AgentRun status=failed, policy_denial_reasons persisted.

---

## 4. Verification Evidence

| Verification Criterion | Status | Evidence Reference |
| --- | --- | --- |
| V-1: Registry completeness | PASS | SharedService + 2 Host rows + OwnershipRecord confirmed |
| V-2: Evidence pack 0 violations | PASS | BrokerResult.violations=[] |
| V-3: AgentRun completed | PASS | run_code=RUN-plt_arch-TT-001-20260308T120000-AF3B21 |
| V-4: Denial path exercised | PASS | AgentRun status=failed, denial reasons recorded |
| V-5: Audit reconstructable | PASS | Full chain: template → pack → run → evidence items |
| V-6: No hidden manual step | PASS | All actions via workflow; no out-of-band DB edits |

---

## 5. Residual Observations

| Observation | Severity | Disposition |
| --- | --- | --- |
| AlertManager on-call list gap persists | LOW | Carried to pt-021 gap register |
| Grafana datasource credentials not in secrets registry | MEDIUM | Tracked as open gap; blocked on pt-028 |
| Semantic search not exercised (TT-001 disallows) | INFO | By design; to be exercised in TT-003 pilot |

---

## 6. Audit Completeness Declaration

All execution steps were performed through the governed workflow. No manual database
modifications, credential bypasses, or out-of-band fixups were applied. The evidence chain
is complete and reconstructable from:

1. `agent_control.prompt_template_registry` → template used
2. `retrieval.evidence_pack` → assembled context
3. `agent_control.agent_run` → run record with scope
4. `agent_control.agent_evidence` → per-item evidence
5. `governance.change_log` → no write actions; no ChangeLog rows produced in this pilot
