---
id: LLM-003
title: internalCMDB — Fallback, Latency, Cost, and Safety Controls for Model Runtime (Wave-1)
doc_class: policy_pack
domain: llm-runtime
version: "1.1"
status: approved
created: 2026-03-08
updated: 2026-07-05
owner: platform_architecture_lead
tags: [fallback, safety, guardrails, latency, haproxy, tool-calling, wave-1, m12-3]
depends_on: [LLM-001, LLM-002]
---

## internalCMDB — Fallback, Latency, Cost, and Safety Controls

> **OpenRouter migration (2026-07-05):** Latency budgets in §2 remain targets; upstream is now OpenRouter via LiteLLM. GPU OOM (LLM-ERR-005) no longer applies to chat/embed paths. **No silent fallback to external API** policy is satisfied — OpenRouter *is* the Wave-1 external provider behind the same internal gateway contract. Cross-model fallback (fast → reasoning) still applies via alias routing in LiteLLM config.

## 1. Purpose

Fallback and guardrail policy with tested safety and runtime degradation handling.
Satisfies pt-039 [m12-3].

---

## 2. Latency Budgets

| Model Class | Task Type | P50 Target | P95 Target | Hard Timeout |
| --- | --- | --- | --- | --- |
| reasoning_32b | complex_analysis | 1s | 3s | 30s |
| reasoning_32b | multi_step_reasoning | 1.5s | 5s | 60s |
| reasoning_32b | tool_use | 1s | 3s | 30s |
| fast_14b | summarization | 500ms | 1.5s | 10s |
| fast_14b | classification | 200ms | 800ms | 5s |
| fast_14b | extraction | 300ms | 1s | 8s |
| fast_14b | tool_use | 300ms | 1s | 10s |

Hard timeout == vLLM request timeout setting. Requests exceeding hard timeout return `503`.

> **Nota reasoning_32b**: P50 target actualizat la 1s (de la 800ms) deoarece `--enforce-eager`
> este activ. CUDA graphs sunt dezactivate din cauza VRAM redus disponibil (~754 MiB liber
> după ncărcarea ambelor modele). TTFT în interval 600-800ms este comportament normal.

---

## 3. Fallback Policy

| Failure Condition | Action | Logged In |
| --- | --- | --- |
| vLLM endpoint returns 5xx | Retry once after 500ms; fail with error code LLM-ERR-001 | agent_run.failure_reason |
| vLLM endpoint unreachable (connection refused) | Fail immediately; no retry; error LLM-ERR-002 | agent_run.failure_reason |
| Request exceeds hard timeout | Fail with error LLM-ERR-003; log prompt token count | agent_run |
| fast_14b unavailable | Route summarization/classification/extraction/tool_use to reasoning_32b | agent_run.model_class_used |
| reasoning_32b unavailable | No fallback; return error LLM-ERR-004 to caller | agent_run |
| GPU OOM (CUDA out of memory) | vLLM returns 503; fail with LLM-ERR-005; alert fired (ALT-007) | agent_run + alert |
| HAProxy maxconn saturat | HAProxy returns 503 imediat; client primeşte LLM-ERR-006 | proxy logs |

**No silent fallback to external API is permitted in Wave-1.**

> **HAProxy**: maxconn setat la 20,000 (crescut de la 2,000 în 2026-04-14 — era saturat de
> conexiuni Redis Cerniq cu timeout 60s). Redis timeout redus la 8s pe frontend/backend `cerniq_redis_in/out`.

---

## 4. Safety Controls

### 4.1 Input Guardrails

| Check | Implementation | Block Condition |
| --- | --- | --- |
| Prompt length | max_model_len enforced by vLLM (24576 tokens reasoning_32b; 12288 fast_14b) | Truncation or rejection |
| Secret pattern detection | Ingest-time redaction scanner (DATA-002) | Reject observed_fact containing credential patterns |
| Injection pattern check | Heuristic scan in retrieval broker (pt-057) | Flag + deny; log in agent_run |
| Tool schema validation | Validare JSON schema tools[] înainte de trimitere la model | Reject dacă schema invalidă sau funcție nedeclarată |

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
| fast_14b latency > P95 target | DEGRADED | Alert ALT-006; route to reasoning_32b if possible |
| reasoning_32b latency > P95 target | DEGRADED | Alert ALT-007; restrict to critical task types only |
| VRAM utilization > 90% | CRITICAL | Alert ALT-007; reject new requests with 429 |
| VRAM liber < 500 MiB pe RTX 6000 Ada | WARNING | Nu porni containere noi; nu modifica `gpu_memory_utilization` fără oprire `--enforce-eager` |
| All models unavailable | OUTAGE | Alert ALT-008; all agent runs fail with LLM-ERR-999 |

---

## 6. Cost Controls (Wave-1)

In Wave-1, compute is self-hosted. Cost controls focus on resource protection:

- `--gpu-memory-utilization` caps set per model: **0.65** for reasoning_32b, **0.28** for fast_14b. Total: 93% — doar ~754 MiB VRAM rămâne liber.
- Concurrent request limits: max 4 concurrent for reasoning_32b, max 8 for fast_14b (vLLM default).
- Long-running requests (> 60s) killed automatically by hard timeout.
- **Avertisment**: nu creşte `gpu_memory_utilization` fără să evaluezi VRAM disponibil. La 0.65+0.28=0.93, orice creştere poate cauza OOM la startup.

---

## 7. Verification

- [x] Latency budgets defined for all task types with P50/P95/hard timeout.
- [x] Fallback policy covers all failure conditions with documented behavior.
- [x] No silent external API fallback permitted.
- [x] Input and output safety controls are specified.
- [x] Degradation levels and automatic actions are explicit.
- [x] Failure conditions trigger documented bounded behaviors, not operator improvisation.
