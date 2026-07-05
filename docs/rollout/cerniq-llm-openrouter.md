# Cerniq.app — LLM configuration (post OpenRouter migration)

**Date:** 2026-07-05  
**Status:** no Cerniq code changes required

## Public endpoints (unchanged)

Cerniq.app continues to call the same Traefik URLs:

| Purpose | URL |
|---|---|
| Reasoning | `https://infraq.app/llm/v1/reasoning/v1/chat/completions` |
| Fast | `https://infraq.app/llm/v1/fast/v1/chat/completions` |
| Embeddings | `https://infraq.app/llm/v1/embeddings/v1/embeddings` |

Model IDs in request bodies remain unchanged:

- `Qwen/QwQ-32B-AWQ` (reasoning)
- `Qwen/Qwen2.5-14B-Instruct-AWQ` (fast)
- `qwen3-embedding-8b-q5km` (embeddings)

LiteLLM on lxc-llm-guard aliases these to OpenRouter models upstream.

## Authentication

- **Traefik / HAProxy:** no auth on model routes (same as before).
- **OpenRouter billing key:** `CERNIQ_APP_KEY` stored in OpenBao at `kv-llm/openrouter`.
  Used by LiteLLM when Cerniq-specific virtual keys are configured; infra traffic uses `INFRA_APP_KEY`.

## Manual verification checklist

1. Send a chat completion from Cerniq staging against `fast` endpoint — expect 200 + tool_calls if configured.
2. Confirm embedding dimension remains **4096** for RAG indexes shared with internalCMDB.
3. Monitor OpenRouter dashboard spend under the Cerniq.app key after first production traffic.

## Rollback

If Cerniq must revert to self-hosted GPU during soak:

```bash
./scripts/cutover_llm_openrouter.sh rollback
# Restart vLLM/Ollama on hz.113/hz.62
```

No Cerniq environment variable changes are needed for rollback — only upstream HAProxy targets change.
