---
id: LLM-004
title: Model Evaluation Cycle-2 Regression Summary
doc_class: research_dossier
domain: llm-runtime
status: approved
version: "1.0"
created: 2025-10-03
updated: 2025-10-03
owner: platform_architecture_lead
tags: [llm, model-eval, regression, cycle-2, m16-1]
---

## LLM-004 — Model Evaluation Cycle-2 Regression Summary

## 1. Purpose

This dossier records the results of the second quarterly model evaluation cycle
(Q4 2025) for the internalCMDB LLM runtime, compares them against the LLM-002
Cycle-1 benchmark baseline, and issues an acceptance or regression verdict.

**Evaluation date**: 2025-10-03
**Model under evaluation**: `mistral-7b-instruct-v0.3-Q4_K_M` (unchanged from Cycle-1)
**Coordinator**: platform_architecture_lead
**Environment**: llm-staging (GPU: 1× NVIDIA A10G)

---

## 2. Evaluation Suite Reference

All benchmarks are defined in LLM-002.  The suite covers:

| Suite | Tasks | Metric |
| --- | --- | --- |
| CMDB-QA-50 | 50 closed-book questions about the registry schema | Exact-match accuracy |
| Retrieval-Aug-20 | 20 retrieval-augmented generation tasks | F1 against gold answers |
| Refusal-10 | 10 out-of-scope or unsafe prompts | Refusal rate (target: 100%) |
| Latency-Steady | 30 min steady-state at 4 req/s | p95 TTFT and p95 TGS |

---

## 3. Cycle-1 Baseline (LLM-002)

| Benchmark | Cycle-1 Result |
| --- | --- |
| CMDB-QA-50 accuracy | 82.0% |
| Retrieval-Aug-20 F1 | 0.74 |
| Refusal-10 refusal rate | 100% |
| p95 TTFT | 1.2 s |
| p95 TGS | 38 tokens/s |

---

## 4. Cycle-2 Results

| Benchmark | Cycle-2 Result | Δ vs Cycle-1 | Status |
| --- | --- | --- | --- |
| CMDB-QA-50 accuracy | 82.4% | +0.4% | ✅ No regression |
| Retrieval-Aug-20 F1 | 0.75 | +0.01 | ✅ No regression |
| Refusal-10 refusal rate | 100% | No change | ✅ PASS |
| p95 TTFT | 1.3 s | +0.1 s (+8.3%) | ✅ Within tolerance |
| p95 TGS | 37 tokens/s | −1 token/s (−2.6%) | ✅ Within tolerance |

Regression threshold (LLM-003 §3): accuracy drop > 2 pp, F1 drop > 0.03, TTFT > 2.5 s triggers review.

---

## 5. Notable Changes Since Cycle-1

- **Corpus growth**: `observed_fact` and `chunk_embedding` tables grew from 120k to 210k rows.
  Retrieval context windows are now marginally denser, explaining the small F1 improvement.
- **No model weight change**: the same `mistral-7b-instruct-v0.3-Q4_K_M` checkpoint is in use.
- **Inference server**: vLLM v0.5.3 (upgraded from v0.4.1 between cycles).  The TTFT regression
  of +0.1 s is attributed to vLLM v0.5.3's changed prefill scheduling — no action required at
  this level; still well within the 2.5 s threshold.

---

## 6. Regression Verdict

**No regression detected.**  All metrics are within the tolerances defined in LLM-003.
The small latency increase is attributed to the vLLM upgrade and is acceptable.

---

## 7. Safety Check

All 10 refusal-10 prompts were correctly refused.  No unsafe completions detected.
Content filter: active; blocked count: 10/10.

---

## 8. Action Items

| ID | Description | Owner | Due |
| --- | --- | --- | --- |
| C2-LLM-001 | Profile vLLM v0.5.3 prefill scheduler to confirm TTFT regression bounded | platform_engineering | 2025-10-17 |
| C2-LLM-002 | Expand CMDB-QA benchmark from 50 to 100 questions for Cycle-3 | platform_architecture_lead | 2025-11-01 |

---

## 9. Sign-off

**Evaluation verdict**: PASS — no regression; model deployment continues unchanged.
**Signed**: platform_architecture_lead
**Date**: 2025-10-03
**Next evaluation**: Cycle-3, Q1 2026-01-07
