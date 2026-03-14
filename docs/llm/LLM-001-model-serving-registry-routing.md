---
id: LLM-001
title: internalCMDB — Model Serving Stack, Registry Contract, and Routing Rules (Wave-1)
doc_class: policy_pack
domain: llm-runtime
version: "1.1"
status: approved
created: 2026-03-08
updated: 2026-03-14
owner: platform_architecture_lead
tags: [model-registry, routing, vllm, ollama, embedding, wave-1, m12-1]
---

## internalCMDB — Model Serving Stack and Registry Contract

## 1. Purpose

Governed runtime and model registry contract for supported self-hosted model classes.
Satisfies pt-037 [m12-1].

---

## 2. Supported Model Classes

| Model Class | Task Types | Serving Stack | VRAM Budget | Host |
| --- | --- | --- | --- | --- |
| reasoning_32b | complex_analysis, multi_step_reasoning | vLLM + Qwen/QwQ-32B-AWQ | ≈31 GB (65%) | 10.0.1.13 (RTX 6000 Ada 48 GB) |
| fast_14b | summarization, classification, extraction | vLLM + Qwen/Qwen2.5-14B-Instruct-AWQ | ≈13 GB (28%) | 10.0.1.13 (RTX 6000 Ada 48 GB) |
| embedding_8b | embedding | Ollama + Qwen3-Embedding-8B-Q5_K_M | ≈5.1 GB | hz.62 (GTX 1080 8 GB) |

**Generation VRAM budget**: 48 GB (RTX 6000 Ada). Ceiling: reasoning_32b ≤ 65%, fast_14b ≤ 28%, KV cache ≥ 7%.

**Embedding VRAM budget**: 8 GB (GTX 1080). Qwen3-Embedding-8B Q5_K_M uses 5.1 GB (64%).

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

| Task Type | Model Class | Port | Fallback |
| --- | --- | --- | --- |
| complex_analysis | reasoning_32b | 10.0.1.13:8000 | Return error; no fallback in Wave-1 |
| multi_step_reasoning | reasoning_32b | 10.0.1.13:8000 | Return error; no fallback in Wave-1 |
| summarization | fast_14b | 10.0.1.13:8001 | reasoning_32b if fast_14b unavailable |
| classification | fast_14b | 10.0.1.13:8001 | reasoning_32b if fast_14b unavailable |
| extraction | fast_14b | 10.0.1.13:8001 | reasoning_32b if fast_14b unavailable |
| embedding | embedding_8b | 10.0.1.62:11434 | HAProxy VIP 10.0.1.10:49003 |

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

---

## Changelog

| Version | Date | Changes |
| --- | --- | --- |
| 1.1 | 2026-03-14 | Fixed model references to match production: reasoning_32b → Qwen/QwQ-32B-AWQ (65% VRAM, max_len 24576); renamed fast_9b → fast_14b (Qwen/Qwen2.5-14B-Instruct-AWQ, 28% VRAM, max_len 12288); added embedding_8b model class (Ollama + Qwen3-Embedding-8B-Q5_K_M on hz.62); added host column to model classes table; updated VRAM ceiling percentages. |
| 1.0 | 2026-03-08 | Initial release — Wave-1 model registry contract, routing rules, retirement policy. |
