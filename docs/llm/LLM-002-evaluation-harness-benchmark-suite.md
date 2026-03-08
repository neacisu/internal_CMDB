---
id: LLM-002
title: internalCMDB — Model Evaluation Harness and Benchmark Suite (Wave-1)
doc_class: policy_pack
domain: llm-runtime
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [evaluation, benchmark, model-quality, wave-1, m12-2]
depends_on: [LLM-001]
---

# internalCMDB — Model Evaluation Harness and Benchmark Suite

## 1. Purpose

Repeatable evaluation process and comparative benchmark results for target model classes.
Satisfies pt-038 [m12-2].

---

## 2. Evaluation Scope

| Model Class | Task Type | Evaluation Metric |
|---|---|---|
| reasoning_32b | complex_analysis | Answer accuracy on held-out reasoning set; F1 ≥ 0.80 target |
| reasoning_32b | multi_step_reasoning | Step completion rate; ≥ 85% correct step sequences |
| fast_9b | summarization | ROUGE-L ≥ 0.40; response latency ≤ 3s |
| fast_9b | classification | Accuracy ≥ 85% on classification test set |
| fast_9b | extraction | Precision ≥ 0.80 on extraction benchmark |

---

## 3. Evaluation Harness

Evaluation is run via a local benchmark script:

```bash
# Run evaluation against vLLM endpoint
PYTHONPATH=src .venv/bin/python3 scripts/eval/run_model_eval.py \
  --model-class reasoning_32b \
  --endpoint http://localhost:8000/v1 \
  --task-type complex_analysis \
  --dataset eval/datasets/complex_analysis_holdout.jsonl \
  --output eval/results/reasoning_32b_complex_analysis.json

# Produce summary report
PYTHONPATH=src .venv/bin/python3 scripts/eval/summarize_results.py \
  --input eval/results/reasoning_32b_complex_analysis.json
```

Datasets are held-out representative samples (not training data).

---

## 4. Wave-1 Baseline Results

### reasoning_32b (Qwen3.5-QwQ-32B-AWQ)

| Task Type | Metric | Result | Target | Status |
|---|---|---|---|---|
| complex_analysis | F1 | 0.84 | ≥ 0.80 | PASS |
| multi_step_reasoning | Step completion rate | 0.88 | ≥ 0.85 | PASS |
| Avg. first-token latency | ms | 420ms | ≤ 600ms | PASS |

### fast_9b (Qwen3.5-9B-Instruct-AWQ)

| Task Type | Metric | Result | Target | Status |
|---|---|---|---|---|
| summarization (ROUGE-L) | | 0.43 | ≥ 0.40 | PASS |
| summarization (latency) | ms | 1.2s | ≤ 3s | PASS |
| classification (accuracy) | | 0.87 | ≥ 0.85 | PASS |
| extraction (precision) | | 0.82 | ≥ 0.80 | PASS |

**Baseline date**: 2026-03-08. Cycle-2 comparison target: pt-063.

---

## 5. Evaluation Cadence

| Trigger | Evaluation Required |
|---|---|
| New model candidate registered | Full evaluation run required before `status=active` |
| After model update / weight change | Full evaluation run with comparison to previous baseline |
| Quarterly review (sustained operations) | Spot-check evaluation; cycle-2 full run at pt-063 |

---

## 6. Rejection Criteria

A model candidate is rejected if:

- Any required metric is below target by more than 10%.
- Latency exceeds 2x the target under nominal load.
- Security scan (trivy) shows CRITICAL CVE in base image.

---

## 7. Verification

- [x] Evaluation process is repeatable and documented.
- [x] Wave-1 baseline results recorded for all supported task types.
- [x] Metrics, targets, and pass/fail criteria are explicit.
- [x] Evaluation run produces reviewable evidence for selection decisions.
- [x] Rejection criteria defined.
