---
id: RB-COGNITIVE-001
title: LLM Backend Unresponsive Runbook Procedure
doc_class: runbook
domain: infrastructure
version: "1.0"
status: draft
created: 2026-03-22
updated: 2026-03-23
owner: sre_observability_owner
binding:
  - entity_type: registry.service
    entity_id: llm-backend
    relation: describes
---

# RB-COGNITIVE-001 — LLM Backend Unresponsive

## Problem

One or more LLM backends (reasoning, fast, embed, guard) are not responding
to requests.  The LLMClient circuit breaker has tripped and marked the model
as degraded.

## Symptoms

- Cognitive `/query` endpoint returns 503 or times out
- `llm_endpoint_health` collector reports unhealthy for one or more backends
- Prometheus alert `LLMEndpointDown` firing
- Agent logs: `"Model <name> marked DEGRADED after 5 consecutive failures"`
- Grafana dashboard shows latency spike followed by zero throughput

## Impact

- **High** — Cognitive queries, HITL LLM suggestions, and embedding generation
  are impaired or unavailable.
- Auto-fallback: reasoning → fast is automatic, but if fast is also down,
  all NL queries fail.
- Embeddings (embed backend) have no fallback — vector search degrades.

## Steps to Resolve

1. **Identify the affected backend:**
   ```bash
   curl -s https://infraq.app/api/v1/metrics/fleet/matrix | jq '.llm_backends'
   ```

2. **Check vLLM / Ollama process on the GPU host:**
   ```bash
   # For reasoning/fast (hz.113):
   ssh hz.113 'docker ps | grep vllm'
   ssh hz.113 'docker logs vllm-reasoning --tail 50'

   # For embed (hz.62):
   ssh hz.62 'docker ps | grep ollama'
   ssh hz.62 'docker logs ollama --tail 50'
   ```

3. **Check GPU utilisation:**
   ```bash
   ssh hz.113 'nvidia-smi'
   ssh hz.62 'nvidia-smi'
   ```

4. **Restart the affected container:**
   ```bash
   ssh hz.113 'docker restart vllm-reasoning'
   # Wait 60s for model load, then verify:
   ssh hz.113 'curl -s http://localhost:49001/health'
   ```

5. **Verify circuit breaker recovery:**
   - The LLMClient automatically clears the degraded flag after one successful
     request. Send a test query via the API.

6. **If OOM (out-of-memory):**
   ```bash
   ssh hz.113 'dmesg | tail -20'
   # May need to reduce max_model_len or batch_size in vLLM config.
   ```

## Prevention

- Monitor GPU memory with `nvidia_exporter` + Prometheus alerts
- Set `gpu-memory-utilization=0.85` in vLLM config to leave headroom
- Ensure swap is disabled on GPU nodes (prevents thrashing)
- Regular load testing to validate capacity under peak traffic
