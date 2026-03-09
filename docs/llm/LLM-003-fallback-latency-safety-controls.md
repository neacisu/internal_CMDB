---
id: LLM-003
title: internalCMDB — Fallback, Latency, Cost, and Safety Controls for Model Runtime (Wave-1)
doc_class: policy_pack
domain: llm-runtime
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [fallback, safety, guardrails, latency, wave-1, m12-3]
depends_on: [LLM-001, LLM-002]
---

## internalCMDB — Fallback, Latency, Cost, and Safety Controls

## 1. Purpose

Fallback and guardrail policy with tested safety and runtime degradation handling.
Satisfies pt-039 [m12-3].

---

## 2. Latency Budgets

| Model Class | Task Type | P50 Target | P95 Target | Hard Timeout |
| --- | --- | --- | --- | --- |
| reasoning_32b | complex_analysis | 800ms | 2s | 30s |
| reasoning_32b | multi_step_reasoning | 1s | 4s | 60s |
| fast_9b | summarization | 500ms | 1.5s | 10s |
| fast_9b | classification | 200ms | 800ms | 5s |
| fast_9b | extraction | 300ms | 1s | 8s |

Hard timeout == vLLM request timeout setting. Requests exceeding hard timeout return `503`.

---

## 3. Fallback Policy

| Failure Condition | Action | Logged In |
| --- | --- | --- |
| vLLM endpoint returns 5xx | Retry once after 500ms; fail with error code LLM-ERR-001 | agent_run.failure_reason |
| vLLM endpoint unreachable (connection refused) | Fail immediately; no retry; error LLM-ERR-002 | agent_run.failure_reason |
| Request exceeds hard timeout | Fail with error LLM-ERR-003; log prompt token count | agent_run |
| fast_9b unavailable | Route summarization/classification/extraction to reasoning_32b | agent_run.model_class_used |
| reasoning_32b unavailable | No fallback; return error LLM-ERR-004 to caller | agent_run |
| GPU OOM (CUDA out of memory) | vLLM returns 503; fail with LLM-ERR-005; alert fired (ALT-007) | agent_run + alert |

**No silent fallback to external API is permitted in Wave-1.**

---

## 4. Safety Controls

### 4.1 Input Guardrails

| Check | Implementation | Block Condition |
| --- | --- | --- |
| Prompt length | max_model_len enforced by vLLM (32768 tokens) | Truncation or rejection |
| Secret pattern detection | Ingest-time redaction scanner (DATA-002) | Reject observed_fact containing credential patterns |
| Injection pattern check | Heuristic scan in retrieval broker (pt-057) | Flag + deny; log in agent_run |

### 4.2 Output Controls

| Check | Implementation | Action |
| --- | --- | --- |
| Response length | max_tokens set per task type in prompt template | Enforced by vLLM |
| Hallucination risk flag | Evidence completeness check before run (GOV-007 enforcement) | Deny run if evidence below minimum |
| Unsafe content patterns | Post-generation heuristic check (Wave-2 full implementation) | Log warning; no auto-block in Wave-1 |

---

## 5. Degradation Handling

| Condition | Degradation Level | Automatic Actions |
| --- | --- | --- |
| fast_9b latency > P95 target | DEGRADED | Alert ALT-006; route to reasoning_32b if possible |
| reasoning_32b latency > P95 target | DEGRADED | Alert ALT-007; restrict to critical task types only |
| VRAM utilization > 90% | CRITICAL | Alert ALT-007; reject new requests with 429 |
| All models unavailable | OUTAGE | Alert ALT-008; all agent runs fail with LLM-ERR-999 |

---

## 6. Cost Controls (Wave-1)

In Wave-1, compute is self-hosted. Cost controls focus on resource protection:

- `--gpu-memory-utilization` caps set per model (0.55 for reasoning_32b, 0.25 for fast_9b).
- Concurrent request limits: max 4 concurrent for reasoning_32b, max 8 for fast_9b (vLLM default).
- Long-running requests (> 60s) killed automatically by hard timeout.

---

## 7. Verification

- [x] Latency budgets defined for all task types with P50/P95/hard timeout.
- [x] Fallback policy covers all failure conditions with documented behavior.
- [x] No silent external API fallback permitted.
- [x] Input and output safety controls are specified.
- [x] Degradation levels and automatic actions are explicit.
- [x] Failure conditions trigger documented bounded behaviors, not operator improvisation.
