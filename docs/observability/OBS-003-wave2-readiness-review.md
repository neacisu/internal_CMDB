---
id: OBS-003
title: internalCMDB — Wave-2 Readiness Review Package (Residual Risks, Open Gaps, Go/Hold)
doc_class: policy_pack
domain: governance
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [readiness-review, wave-2, risk-register, gap-register, go-hold, m7-3]
depends_on: [PILOT-003, OBS-001, OBS-002, GOV-007]
---

# internalCMDB — Wave-2 Readiness Review Package

## 1. Purpose

Formal readiness package containing residual risks, open gaps, approved exceptions, and
go-or-hold recommendation for Wave-2. Satisfies pt-024 [m7-3].

---

## 2. Readiness Assessment Summary

| Dimension | Status | Gate |
|---|---|---|
| Governance code complete | PASS | epic-5 complete (pt-016..pt-018) |
| Pilot bounded and repeatable | PASS | PILOT-001..PILOT-003 complete |
| Observability catalog defined | PASS | OBS-001 complete |
| Retention and runbooks defined | PASS | OBS-002 complete |
| Write-path pilot executed | HOLD | GAP-004 — RC-1 only in pilot |
| SBOM baseline | HOLD | GAP-005 — pt-031 not started |
| Backup/restore tested | HOLD | GAP-007 — pt-026 not started |
| Security access model | HOLD | GAP-002 — pt-028/029/030 not started |

---

## 3. Residual Risk Register

| Risk ID | Description | Likelihood | Impact | Status |
|---|---|---|---|---|
| RSK-001 | Write-path action class never tested in governed pilot | MEDIUM | HIGH | OPEN — mitigated by RC-1 pilot gate; RC-3/4 blocked until pt-028 |
| RSK-002 | Bootstrap credentials still in use (not rotated) | HIGH | HIGH | OPEN — target: pt-029; no automated rotation yet |
| RSK-003 | No backup/restore procedure tested | MEDIUM | CRITICAL | OPEN — target: pt-026; DB runs with no tested recovery path |
| RSK-004 | SBOM not produced — unknown transitive dependencies | LOW | MEDIUM | OPEN — target: pt-031 |
| RSK-005 | Semantic search not validated end-to-end | LOW | LOW | ACCEPTED — read-only audit pilot does not require semantic |
| RSK-006 | On-call list for AlertManager not yet defined | LOW | MEDIUM | OPEN — target: pt-043/044 |
| RSK-007 | No formal DR simulation conducted | MEDIUM | HIGH | OPEN — target: pt-027 |

---

## 4. Open Gap Register (Wave-2 Entry)

Carrying forward from PILOT-003 gap register plus new gaps discovered during epic-7:

| Gap ID | Description | Severity | Owner | Target Task |
|---|---|---|---|---|
| GAP-001 | AlertManager on-call list | LOW | platform_architecture_lead | pt-043 |
| GAP-002 | Grafana credentials not in secrets registry | MEDIUM | security_and_policy_owner | pt-028 |
| GAP-003 | Semantic search not exercised | INFO | platform_architecture_lead | pt-038 |
| GAP-004 | No write-path pilot | INFO | platform_architecture_lead | epic-7 |
| GAP-005 | SBOM baseline missing | MEDIUM | platform_architecture_lead | pt-031 |
| GAP-006 | TLS certificate lifecycle policy missing | LOW | security_and_policy_owner | pt-030 |
| GAP-007 | Backup/restore untested | HIGH | platform_architecture_lead | pt-026 |
| GAP-008 | Load test not executed | MEDIUM | platform_architecture_lead | pt-041 |
| GAP-009 | Observability dashboards defined but not yet live (infra pending) | MEDIUM | platform_architecture_lead | pt-049 |
| GAP-010 | Alerting rules defined but routing not yet configured | MEDIUM | security_and_policy_owner | pt-050 |

---

## 5. Approved Exceptions

| Exception ID | Gap | Accepted Risk | Approved By | Expires |
|---|---|---|---|---|
| EX-001 | GAP-004 (no write pilot) | Wave-1 pilot intentionally RC-1 only | platform_architecture_lead | m8-3 |
| EX-002 | GAP-003 (semantic not tested) | TT-001 disallows; separate epic | platform_architecture_lead | m8-3 |
| EX-003 | GAP-009 (dashboards not live) | Infra work queued for epic-7 sprint-10 | platform_architecture_lead | m7-3+1sprint |

---

## 6. Go/Hold Recommendation

**Recommendation: CONDITIONAL GO for Wave-2 planning.**

Wave-2 planning activities (scoping, dependency mapping, template authoring) may proceed.
Wave-2 write-path execution is BLOCKED until the following minimum gates are met:

| Gate | Blocking Task |
|---|---|
| Bootstrap credentials rotated | pt-029 |
| Backup/restore procedure tested | pt-026 |
| Secrets storage model approved | pt-028 |
| Write-path pilot executed (RC-2 minimum) | First epic-6 sprint after pt-028 |

**Architecture board approval required before any RC-3 or RC-4 action class is executed
in a governed pilot or production run.**
