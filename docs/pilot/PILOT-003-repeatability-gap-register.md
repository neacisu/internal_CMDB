---
id: PILOT-003
title: internalCMDB — Pilot Repeatability Delta Report and Residual Gap Register (Wave-1)
doc_class: research_dossier
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [pilot, repeatability, gap-register, residual-gaps, wave-1, m6-3]
depends_on: [PILOT-001, PILOT-002, GOV-007]
---

# internalCMDB — Pilot Repeatability Delta Report and Residual Gap Register

## 1. Purpose

This document records the second governed pilot run delta and produces an honest residual gap
register. It satisfies pt-021 [m6-3]: deliverable = repeatability delta report and honest
residual gap register derived from the second governed run.

---

## 2. Second Run Summary

| Field | Value |
| --- | --- |
| Pilot scope | PILOT-001 v1.0 — monitoring-stack read-only audit (repeat) |
| Run date | 2026-03-09 |
| Executed by | platform_architecture_lead |
| Status | completed |
| Delta from first run | 1 new observed fact, no structural changes |

---

## 3. Repeatability Delta

### 3.1 Identical Outcomes

The following aspects of the execution were identical between run 1 and run 2:

- PolicyEnforcer outcomes for AC-001 and AC-002: denied=False in both runs.
- Evidence pack violations: 0 in both runs.
- AgentRun terminal status: completed in both runs.
- Denial path: policy_denial_reasons identical for the forced-failure scenario.
- Prompt template: same version (1.0.0) used in both runs.

### 3.2 Observed Delta

| Item | Run 1 | Run 2 | Delta Classification |
| --- | --- | --- | --- |
| Token total | 3840 | 3912 | MINOR — 1 new observed_fact row added between runs |
| Evidence items | 9 | 10 | MINOR — 1 new OBSERVED_FACT item |
| Semantic stage | Skipped | Skipped | Identical (TT-001 policy) |

**Conclusion**: The delta is fully explained by a legitimate registry state change (one new
observed fact row added by a collection run between the two executions). No platform bug or
repeatability failure is present.

---

## 4. Residual Gap Register

### 4.1 Open Platform Gaps

| Gap ID | Description | Severity | Blocking | Target Task |
| --- | --- | --- | --- | --- |
| GAP-001 | AlertManager on-call list not in registry | LOW | No | pt-043 (RACI/service boundaries) |
| GAP-002 | Grafana datasource credentials not in secrets registry | MEDIUM | No (pilot is read-only) | pt-028 (secrets storage model) |
| GAP-003 | Semantic search not exercised for any task type in pilot | INFO | No | pt-038 (evaluation harness) |
| GAP-004 | No write-path pilot executed (only RC-1) | INFO | No | pt-020 scope constraint |
| GAP-005 | SBOM baseline not yet produced for platform components | MEDIUM | No | pt-031 (inventory/SBOM) |
| GAP-006 | Certificate lifecycle policy not yet authored | LOW | No | pt-030 (TLS lifecycle) |
| GAP-007 | Backup/restore procedure not yet tested against live data | HIGH | No (read-only pilot) | pt-026 (backup/restore) |
| GAP-008 | Load test harness not yet executed against retrieval surface | MEDIUM | No | pt-041 (load/stress test) |

### 4.2 Accepted Exceptions (Wave-1)

| Exception ID | Gap | Rationale | Accepted By | Expires |
| --- | --- | --- | --- | --- |
| EX-001 | GAP-004 (no write pilot) | Wave-1 pilot intentionally bounded to read-only | platform_architecture_lead | m7-3 review |
| EX-002 | GAP-003 (semantic not exercised) | TT-001 explicitly disallows semantic; different TT required | platform_architecture_lead | m7-3 review |

### 4.3 Gaps Closed During Pilot

All gaps from PILOT-001 Section 3.3 that were within pilot scope are now closed:

- ~~Host OS versions not canonical~~ → CLOSED: verified during evidence assembly in PILOT-002.

---

## 5. Repeatability Assessment

**Assessment**: PASS — The platform is repeatable within Wave-1 scope.

Conditions:
- Registry state changes between runs produce proportional, explainable evidence pack deltas.
- PolicyEnforcer outcomes are deterministic for identical inputs.
- No hidden manual dependency was discovered across two consecutive runs.
- Evidence chain is fully reconstructable for both runs.

**Limitation acknowledged**: Only RC-1 actions were tested. Repeatability for write-path
actions (RC-2 through RC-4) remains untested and must be addressed before Wave-2.

---

## 6. Go/No-Go Recommendation for Wave-2

| Criterion | Status | Notes |
| --- | --- | --- |
| Platform governance code complete (epic-5) | GO | pt-016, pt-017, pt-018 complete |
| Pilot bounded and realistic | GO | monitoring-stack fully documented |
| Two governed runs without hidden manual steps | GO | PILOT-002 + this document |
| Residual gaps registered and triaged | GO | Section 4 above |
| Write-path pilot executed | HOLD | Blocked by GAP-004; targeted for epic-7 |
| SBOM baseline produced | HOLD | GAP-005; targeted for pt-031 |

**Recommendation**: PROCEED to Wave-2 readiness activities (epic-7 onward) with the explicit
understanding that write-path and security gaps (GAP-004, GAP-005, GAP-007) are tracked and
triaged, and no bulk structural actions (AC-008, AC-010) may be executed until pt-028..pt-030
are complete.
