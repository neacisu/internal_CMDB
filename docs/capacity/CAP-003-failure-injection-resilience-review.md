---
id: CAP-003
title: internalCMDB — Failure Injection Exercises and Fail-Open vs Fail-Closed Behavior (Wave-1)
doc_class: research_dossier
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [failure-injection, resilience, fail-safe, wave-1, m13-3]
depends_on: [CAP-001, CAP-002, LLM-003]
---

## internalCMDB — Failure Injection Exercises and Fail-Closed Behavior

## 1. Purpose

Resilience review pack describing tested failure behavior and remediation priorities.
Satisfies pt-042 [m13-3].

---

## 2. Fail-Open vs Fail-Closed Policy

internalCMDB follows a **fail-closed** policy for all security and governance surfaces:

| Surface | Failure Behavior | Policy | Rationale |
| --- | --- | --- | --- |
| Policy enforcement | DENY by default if enforcement context unavailable | Fail-Closed | Safety-critical; unknown state = deny |
| Approval workflow | DENY if quorum cannot be determined | Fail-Closed | Prevents unauthorized actions |
| Retrieval broker | Return empty result set; never return unvalidated data | Fail-Closed | Data integrity |
| Collection pipeline | Reject fact if redaction scanner fails | Fail-Closed | Security |
| LLM inference | Return error to caller; do not retry silently | Fail-Closed | Auditability |
| Service discovery | Return last-known state (stale allowed for 1h) | Fail-Open (bounded) | Availability; stale data clearly labeled |

---

## 3. Failure Injection Scenarios

### FI-001 — PostgreSQL Primary Container Stopped

| Step | Outcome |
| --- | --- |
| DB container stopped | Application returns 503 on all DB-dependent endpoints |
| Policy enforcement request during outage | Returns HTTP 503 (fail-closed) |
| Collection ingestion during outage | Returns DB unavailable error; fact NOT silently dropped |
| DB restarted | Application recovers without manual intervention (pool_pre_ping) |

**Status**: PASS. CA-001 (SQLAlchemy pool_pre_ping) verified effective.

### FI-002 — vLLM reasoning_32b Endpoint Killed

| Step | Outcome |
| --- | --- |
| vLLM primary container stopped | complex_analysis + multi_step_reasoning requests fail with LLM-ERR-002 |
| fast_9b routing for summarization | Unaffected; continues on port 8001 |
| Agent run record created for failed run | YES — failure_reason=LLM-ERR-002 recorded |
| No silent fallback to external API | CONFIRMED |

**Status**: PASS. Fail-closed behavior verified.

### FI-003 — Redaction Scanner Injection Attempt

| Step | Outcome |
| --- | --- |
| ObservedFact containing `password=secret123` submitted | Rejected at ingest time |
| Rejection logged in collection_run record | YES |
| Fact NOT present in observed_fact table | CONFIRMED |

**Status**: PASS. Inject attempt correctly denied.

### FI-004 — Approval Workflow — Missing Approver Role

| Step | Outcome |
| --- | --- |
| approve() called without required role in approval_record | Rejected with G-DENY-002 code |
| ActionRequest remains in PENDING status | CONFIRMED |
| No partial state transition | CONFIRMED |

**Status**: PASS. Fail-closed enforced.

### FI-005 — GPU VRAM Spike (Simulated via max-num-seqs reduction)

| Step | Outcome |
| --- | --- |
| vLLM max-num-seqs reduced to 1 (simulates near-OOM) | Queue backs up; new requests receive 429 |
| ALT-007 alert fires | YES (Prometheus scrape confirmed) |
| Existing requests complete normally | CONFIRMED |

**Status**: PASS. Degradation is bounded and alerting works.

---

## 4. Residual Risk Register

| Risk | Severity | Status | Mitigation |
| --- | --- | --- | --- |
| Manual service restart required after crash | MEDIUM | OPEN | CA-004 (restart policy) pending |
| No PostgreSQL WAL archiving for point-in-time recovery | MEDIUM | Accepted (Wave-1) | CONT-001 §3 — accepted for Wave-1 |
| single-node; DB host is also app host | MEDIUM | Accepted (Wave-1) | CONT-001 §3 — Wave-1 constraint |

---

## 5. Verification

- [x] Fail-closed policy is explicit for all security and governance surfaces.
- [x] Five failure injection scenarios have been exercised and documented.
- [x] Each injection test shows evidence-backed bounded behavior.
- [x] Residual risks are listed with acceptance or remediation status.
