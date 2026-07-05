---
id: RB-COGNITIVE-001
title: LLM Backend Unresponsive Runbook Procedure
doc_class: runbook
domain: infrastructure
version: "1.1"
status: draft
created: 2026-03-22
updated: 2026-07-05
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

> **OpenRouter stack (2026-07-05):** Chat and embed backends are **LiteLLM** on
> **lxc-llm-guard (10.0.1.115:8001)** behind HAProxy VIP **10.0.1.10:49001-49003**.
> Guard remains on **10.0.1.115:8000**. GPU hosts hz.113/hz.62 are decommissioned.

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

2. **Check LiteLLM / LLM Guard on lxc-llm-guard:**
   ```bash
   ssh lxc-llm-guard 'docker ps | grep -E "litellm|llm-guard|open-webui"'
   ssh lxc-llm-guard 'curl -sf http://127.0.0.1:8001/health/liveness'
   ssh lxc-llm-guard 'docker logs litellm-gateway --tail 50'
   ssh lxc-llm-guard 'curl -sf http://127.0.0.1:8000/health'
   ```

3. **Check HAProxy VIP routing (hz.247):**
   ```bash
   ssh hz.247 'grep -A2 "4900[123]" /etc/haproxy/haproxy.cfg'
   curl -sf http://10.0.1.10:49001/health/liveness
   curl -sf http://10.0.1.10:49003/v1/embeddings -H "Authorization: Bearer $LITELLM_KEY" \
     -H "Content-Type: application/json" -d '{"model":"qwen3-embedding-8b-q5km","input":["ping"]}'
   ```

4. **Restart the affected container:**
   ```bash
   ssh lxc-llm-guard 'cd /opt/llm-gateway && docker compose restart litellm'
   # Wait 30s, then verify:
   ssh lxc-llm-guard 'curl -sf http://127.0.0.1:8001/health/liveness'
   ```

5. **OpenRouter / key issues:** Check LiteLLM logs for 401/402/429. Refresh keys via
   OpenBao (`deploy/openbao/setup-openrouter.sh`) and restart LiteLLM.

6. **Verify circuit breaker recovery:**
   - The LLMClient automatically clears the degraded flag after one successful
     request. Send a test query via the API.

7. **Rollback to self-hosted GPU (emergency only):**
   ```bash
   ./scripts/cutover_llm_openrouter.sh rollback
   # Restart vLLM/Ollama on hz.113/hz.62 manually
   ```

## Prevention

- Monitor LiteLLM health via Prometheus + `llm_endpoint_health` collector
- Set OpenRouter spend limits and alerts on LiteLLM proxy logs
- Keep OpenBao keys rotated; agent renders `/var/run/openbao/llm-gateway.env`
- Regular load testing to validate capacity under peak traffic
