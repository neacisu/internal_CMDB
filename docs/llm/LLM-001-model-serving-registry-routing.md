---
id: LLM-001
title: internalCMDB — Model Serving Stack, Registry Contract, and Routing Rules (Wave-1)
doc_class: policy_pack
domain: llm-runtime
version: "1.3"
status: approved
created: 2026-03-08
updated: 2026-07-05
owner: platform_architecture_lead
tags: [model-registry, routing, vllm, ollama, embedding, tool-calling, wave-1, m12-1]
---

## internalCMDB — Model Serving Stack and Registry Contract

> **OpenRouter migration (2026-07-05):** Production traffic no longer uses self-hosted vLLM/Ollama on hz.113/hz.62. All reasoning, fast, and embedding requests route through **LiteLLM** on **lxc-llm-guard (10.0.1.115:8001)** → **OpenRouter**. Public contract unchanged (`infraq.app/llm/v1/*`). Model aliases preserve legacy IDs (`Qwen/QwQ-32B-AWQ`, `Qwen/Qwen2.5-14B-Instruct-AWQ`, `qwen3-embedding-8b-q5km`). LLM Guard remains local on :8000. See `docs/rollout/llm-openrouter-status.md`.

## 1. Purpose

Governed runtime and model registry contract for supported self-hosted model classes.
Satisfies pt-037 [m12-1].

---

## 2. Supported Model Classes

| Model Class | Task Types | Serving Stack | VRAM Budget | Host | Tool Calling |
| --- | --- | --- | --- | --- | --- |
| reasoning_32b | complex_analysis, multi_step_reasoning | vLLM 0.16.0 + Qwen/QwQ-32B-AWQ | ≈31 GB (65%) | 10.0.1.13 (RTX 6000 Ada 49 GB ECC) | ✅ hermes parser |
| fast_14b | summarization, classification, extraction | vLLM 0.16.0 + Qwen/Qwen2.5-14B-Instruct-AWQ | ≈13.7 GB (28%) | 10.0.1.13 (RTX 6000 Ada 49 GB ECC) | ✅ hermes parser |
| embedding_8b | embedding | Ollama 0.17.7 + Qwen3-Embedding-8B-Q5_K_M | ≈5.1 GB | hz.62 (GTX 1080 8 GB) | N/A |

**Generation VRAM budget**: 49,140 MiB (RTX 6000 Ada Generation). Ceiling: reasoning_32b ≤ 65%, fast_14b ≤ 28%, KV cache ≥ 7%.

**Tool calling**: ambele modele vLLM au `--enable-auto-tool-choice --tool-call-parser hermes` activ din 2026-04-14. Parserul `hermes` traduce formatul nativ Qwen (`<tool_call>...</tool_call>`) în `tool_calls[]` standard OpenAI.

**Embedding VRAM budget**: 8,192 MiB (GTX 1080). Qwen3-Embedding-8B Q5_K_M ocupă ~5.1 GB (64%).

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

| Task Type | Model Class | Port intern | HAProxy VIP | Fallback |
| --- | --- | --- | --- | --- |
| complex_analysis | reasoning_32b | 10.0.1.13:8001 | 10.0.1.10:49001 | Return error; no fallback in Wave-1 |
| multi_step_reasoning | reasoning_32b | 10.0.1.13:8001 | 10.0.1.10:49001 | Return error; no fallback in Wave-1 |
| tool_use | reasoning_32b / fast_14b | 10.0.1.13:8001/8002 | 10.0.1.10:49001/49002 | Cross-model fallback permis |
| summarization | fast_14b | 10.0.1.13:8002 | 10.0.1.10:49002 | reasoning_32b dacă fast_14b indisponibil |
| classification | fast_14b | 10.0.1.13:8002 | 10.0.1.10:49002 | reasoning_32b dacă fast_14b indisponibil |
| extraction | fast_14b | 10.0.1.13:8002 | 10.0.1.10:49002 | reasoning_32b dacă fast_14b indisponibil |
| embedding | embedding_8b | 10.0.1.62:8003 | 10.0.1.10:49003 | Fără fallback |

Traefik gateway public: `https://infraq.app/llm/v1/{reasoning|fast|embeddings|guard}`

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
| 1.3 | 2026-04-14 | Audit live complet (LLM-006). Actualizat VRAM total la 49,140 MiB real. Adăugat coloană tool calling în tabelul model classes — ambele vLLM au `--enable-auto-tool-choice --tool-call-parser hermes` activ. Adăugat task type `tool_use` în routing rules. Adăugat coloana HAProxy VIP în routing. Adăugat prefixele publice Traefik. vLLM confirmat 0.16.0, Ollama 0.17.7. |
| 1.2 | 2026-03-16 | Corrected runtime port mappings to match production reality: reasoning_32b host bind is 10.0.1.13:8001, fast_14b host bind is 10.0.1.13:8002, and embedding_8b host bind is 10.0.1.62:8003 behind HAProxy VIP 10.0.1.10:49003. |
| 1.1 | 2026-03-14 | Fixed model references to match production: reasoning_32b → Qwen/QwQ-32B-AWQ (65% VRAM, max_len 24576); renamed fast_9b → fast_14b (Qwen/Qwen2.5-14B-Instruct-AWQ, 28% VRAM, max_len 12288); added embedding_8b model class (Ollama + Qwen3-Embedding-8B-Q5_K_M on hz.62); added host column to model classes table; updated VRAM ceiling percentages. |
| 1.0 | 2026-03-08 | Initial release — Wave-1 model registry contract, routing rules, retirement policy. |
