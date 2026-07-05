# LLM OpenRouter migration status

**Date:** 2026-07-05  
**Status:** completed (7-day GPU soak until 2026-07-12 before Hetzner cancel)

## Target architecture

| Endpoint | Upstream |
|---|---|
| `/llm/v1/reasoning/*` | HAProxy :49001 → LiteLLM :8001 → `deepseek/deepseek-v4-pro` |
| `/llm/v1/fast/*` | HAProxy :49002 → LiteLLM :8001 → `deepseek/deepseek-v4-flash` |
| `/llm/v1/embeddings/*` | HAProxy :49003 → LiteLLM :8001 → `qwen/qwen3-embedding-8b` |
| `/llm/v1/guard/*` | LLM Guard local :8000 (unchanged) |
| Open WebUI | HAProxy :49000 → :3000 on lxc-llm-guard |

Single `litellm-gateway` container on **10.0.1.115:8001** (all VIPs share one proxy; model selected by request body alias).

## Decommissioned (stopped 2026-07-05)

- **hz.113** — vLLM + Open WebUI (GPU) — Hetzner cancel after soak
- **hz.62** — Ollama embeddings (GPU) — Hetzner cancel after soak

## OpenBao paths

- `kv-llm/openrouter` — MANAGEMENT_KEY, CERNIQ_APP_KEY, INFRA_APP_KEY
- AppRole `llm-gateway` → `/run/secrets/bao_llm_gateway_secret_id` on lxc-llm-guard
- Agent HCL: `deploy/openbao/bao-agent-llm-gateway.hcl` (+ systemd unit in repo)
- **Action:** rotate keys per `docs/rollout/openrouter-key-rotation.md` if exposed in chat

## Validation (2026-07-05)

| Check | Result |
|---|---|
| LiteLLM direct :8001 health | OK |
| Fast chat + tool_call | OK |
| Reasoning (reasoning_content) | OK |
| Embed dim via VIP :49003 | 4096 |
| Traefik `/llm/v1/reasoning/health/liveness` | OK |
| Guard `/analyze/prompt` injection | blocked (`is_valid=false`) |
| pgvector cosine (OpenRouter vs Ollama stored) | 0.9964 |
| `llm.embed.api_format` in DB | `openai` |

## Cerniq.app

See **`docs/rollout/cerniq-llm-openrouter.md`** for Cerniq-specific verification.

Base URLs unchanged: `https://infraq.app/llm/v1/{reasoning,fast,embeddings}`.  
API key: `CERNIQ_APP_KEY` in OpenBao.

## Rollback

```bash
./scripts/cutover_llm_openrouter.sh rollback
# Restart GPU compose on hz.113/hz.62 manually
```

## Post-soak (2026-07-12)

- Cancel Hetzner servers hz.113 + hz.62
- Remove stale Prometheus scrape targets for GPU exporters
- Install OpenBao agent on lxc when BAO network path is available (static env in use)
