#!/usr/bin/env bash
# LLM cutover: self-hosted GPU (hz.113/hz.62) → OpenRouter via LiteLLM on 10.0.1.115
#
# Usage:
#   ./scripts/cutover_llm_openrouter.sh preflight   # health checks only
#   ./scripts/cutover_llm_openrouter.sh cutover    # HAProxy + Traefik reload
#   ./scripts/cutover_llm_openrouter.sh rollback   # restore hz.113/hz.62 backends
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HAPROXY_HOST="${HAPROXY_HOST:-hz.247}"
TARGET="${LLM_GATEWAY_HOST:-lxc-llm-guard}"
GATEWAY_IP="${GATEWAY_IP:-10.0.1.115}"
ORCHESTRATOR="${ORCHESTRATOR:-orchestrator}"

die() { echo "ERROR: $*" >&2; exit 1; }

preflight() {
  echo "==> Gateway direct health (via ${TARGET})"
  ssh "$TARGET" "curl -sf http://127.0.0.1:8001/health/liveness" >/dev/null \
    || die "LiteLLM :8001 unhealthy"
  echo "  OK :8001 (all models)"
  ssh "$TARGET" "curl -sf http://127.0.0.1:8000/healthz" >/dev/null || die "LLM Guard unhealthy"
  echo "  OK :8000 guard"

  echo "==> HAProxy VIP probes (via ${HAPROXY_HOST})"
  ssh "$HAPROXY_HOST" "curl -sf http://10.0.1.10:49001/health/liveness >/dev/null || curl -sf http://10.0.1.10:49001/health >/dev/null" \
    || die "VIP :49001 unhealthy"
  echo "  OK VIP :49001"
}

apply_haproxy() {
  local target_ip="$1"
  echo "==> Patching HAProxy backends → ${target_ip}"
  ssh "$HAPROXY_HOST" "cp /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.bak.\$(date -u +%Y%m%dT%H%M%SZ)"
  ssh "$HAPROXY_HOST" "sed -i \
    -e 's/10\\.0\\.1\\.13:3000/${target_ip}:3000/g' \
    -e 's/10\\.0\\.1\\.13:8001/${target_ip}:8001/g' \
    -e 's/10\\.0\\.1\\.13:8002/${target_ip}:8001/g' \
    -e 's/10\\.0\\.1\\.62:8003/${target_ip}:8001/g' \
    -e 's/10\\.0\\.1\\.115:8002/${target_ip}:8001/g' \
    -e 's/10\\.0\\.1\\.115:8003/${target_ip}:8001/g' \
    /etc/haproxy/haproxy.cfg"
  ssh "$HAPROXY_HOST" "haproxy -c -f /etc/haproxy/haproxy.cfg"
  ssh "$HAPROXY_HOST" "systemctl reload haproxy"
  echo "HAProxy reloaded"
}

deploy_traefik() {
  echo "==> Deploy Traefik llm-api.yml"
  scp "${REPO_ROOT}/deploy/orchestrator/llm-api.yml" \
    "${ORCHESTRATOR}:/opt/traefik/dynamic/llm-api.yml"
  ssh "$ORCHESTRATOR" "docker exec traefik kill -HUP 1 2>/dev/null || true"
}

cutover() {
  preflight
  apply_haproxy "$GATEWAY_IP"
  deploy_traefik
  preflight
  echo "Cutover complete. Monitor OpenRouter spend + LLMEndpointDown for 15 min."
}

rollback() {
  apply_haproxy "10.0.1.13"
  ssh "$HAPROXY_HOST" "sed -i 's/10\\.0\\.1\\.13:8003/10.0.1.62:8003/g' /etc/haproxy/haproxy.cfg"
  ssh "$HAPROXY_HOST" "haproxy -c -f /etc/haproxy/haproxy.cfg && systemctl reload haproxy"
  echo "Rollback HAProxy to hz.113/hz.62. Start GPU compose manually if needed."
}

case "${1:-}" in
  preflight) preflight ;;
  cutover) cutover ;;
  rollback) rollback ;;
  *) die "Usage: $0 {preflight|cutover|rollback}" ;;
esac
