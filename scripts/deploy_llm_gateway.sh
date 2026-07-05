#!/usr/bin/env bash
# Deploy LiteLLM OpenRouter gateway to lxc-llm-guard (10.0.1.115).
#
# Usage:
#   ./scripts/deploy_llm_gateway.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${LLM_GATEWAY_HOST:-lxc-llm-guard}"
GATEWAY_IP="${GATEWAY_IP:-10.0.1.115}"
REMOTE_DIR="/opt/llm-gateway"

echo "==> Sync deploy/llm-gateway → ${TARGET}:${REMOTE_DIR}"
ssh "$TARGET" "mkdir -p ${REMOTE_DIR}/litellm ${REMOTE_DIR}/webui-data"
rsync -av --delete \
  "${REPO_ROOT}/deploy/llm-gateway/" \
  "${TARGET}:${REMOTE_DIR}/"

echo "==> Pull images and start stack"
ssh "$TARGET" "cd ${REMOTE_DIR} && docker compose pull && docker compose up -d"

echo "==> Health checks"
curl -sf "http://${GATEWAY_IP}:8001/health/liveness" >/dev/null && echo " OK :8001"

echo "Deploy complete."
