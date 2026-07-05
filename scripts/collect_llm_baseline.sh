#!/usr/bin/env bash
# Save rollback baseline before LLM OpenRouter cutover.
set -euo pipefail

OUT="${1:-docs/rollout/baseline-llm-pre-openrouter-$(date -u +%Y%m%d).txt}"
mkdir -p "$(dirname "$OUT")"

{
  echo "=== LLM baseline $(date -u -Iseconds) ==="
  echo "--- HAProxy hz.247 LLM backends ---"
  ssh hz.247 'grep -E "10\.0\.1\.(13|62|115)" /etc/haproxy/haproxy.cfg | head -20' || true
  echo "--- hz.113 docker ---"
  ssh hz.113 'docker ps --format "{{.Names}}" 2>/dev/null' || true
  echo "--- hz.62 docker ---"
  ssh hz.62 'docker ps --format "{{.Names}}" 2>/dev/null' || true
  echo "--- lxc-llm-guard ---"
  ssh lxc-llm-guard 'free -h; docker ps --format "{{.Names}}"' || true
} >"$OUT"

echo "Baseline written to $OUT"
