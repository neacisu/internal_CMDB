---
id: LLM-001
title: internalCMDB — Model Serving Stack, Registry Contract, and Routing Rules (Wave-1)
doc_class: policy_pack
domain: llm-runtime
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [model-registry, routing, vllm, wave-1, m12-1]
---

## internalCMDB — Model Serving Stack and Registry Contract

## 1. Purpose

Governed runtime and model registry contract for supported self-hosted model classes.
Satisfies pt-037 [m12-1].

---

## 2. Supported Model Classes

| Model Class | Task Types | Serving Stack | VRAM Budget |
| --- | --- | --- | --- |
| reasoning_32b | complex_analysis, multi_step_reasoning | vLLM + Qwen3.5-QwQ-32B-AWQ | 20–24 GB |
| fast_9b | summarization, classification, extraction | vLLM + Qwen3.5-9B-Instruct-AWQ | 8–10 GB |

**Total VRAM budget**: 48 GB (RTX 6000 Ada). Ceiling: reasoning_32b ≤ 55%, fast_9b ≤ 25%, KV cache ≥ 20%.

---

## 3. Model Registry Contract

Each supported model must have a registered entry with:

| Field | Required | Description |
| --- | --- | --- |
| model_id | YES | Unique identifier (e.g., `qwq-32b-awq-v1`) |
| model_class | YES | Maps to task type routing (see §2) |
| hf_repo | YES | HuggingFace repository ID |
| vram_utilization | YES | GPU memory utilization cap (0.0–1.0) |
| max_model_len | YES | Maximum context length |
| serving_port | YES | Docker host port for vLLM endpoint |
| status | YES | `active`, `deprecated`, `candidate` |
| approved_by | YES | platform_architecture_lead |
| evaluation_ref | YES | Reference to evaluation result record (LLM-002) |

Models with `status=candidate` must not receive production traffic.

---

## 4. Routing Rules

| Task Type | Model Class | Priority | Fallback |
| --- | --- | --- | --- |
| complex_analysis | reasoning_32b (port 8000) | 1 | Return error; no fallback in Wave-1 |
| multi_step_reasoning | reasoning_32b (port 8000) | 1 | Return error; no fallback in Wave-1 |
| summarization | fast_9b (port 8001) | 1 | reasoning_32b (port 8000) if fast_9b unavailable |
| classification | fast_9b (port 8001) | 1 | reasoning_32b (port 8000) if fast_9b unavailable |
| extraction | fast_9b (port 8001) | 1 | reasoning_32b (port 8000) if fast_9b unavailable |

Routing decisions must be logged in agent_run records with the model_class selected.

---

## 5. Model Retirement Policy

A model may be deprecated only after:

1. A replacement model is registered and has `status=active`.
2. Evaluation evidence (LLM-002) shows the replacement meets all task type benchmarks.
3. approval_record from platform_architecture_lead is created.
4. Change logged in `governance.change_log` with `change_type=model_retirement`.

---

## 6. Verification

- [x] Model classes map to task types and routing rules.
- [x] Model registry contract fields are fully specified.
- [x] VRAM budget constraints are explicit.
- [x] Routing decisions are auditable in agent_run records.
- [x] Model retirement requires explicit approval and evaluation evidence.
