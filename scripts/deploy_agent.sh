#!/usr/bin/env bash
# deploy_agent.sh — Deploy the internalCMDB collector agent to remote hosts.
#
# Usage:
#   ./scripts/deploy_agent.sh <host_code> [api_url]
#   ./scripts/deploy_agent.sh all [api_url]
#
# Examples:
#   ./scripts/deploy_agent.sh hz.113
#   ./scripts/deploy_agent.sh all https://cmdb.internal:4444/api/v1/collectors

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
AGENT_SRC="$REPO_ROOT/src/internalcmdb"
SYSTEMD_UNIT="$REPO_ROOT/deploy/agent/internalcmdb-agent.service"
REMOTE_AGENT_DIR="/opt/internalcmdb/agent"
REMOTE_CONFIG_DIR="/etc/internalcmdb"
DEFAULT_API_URL="https://infraq.app/api/v1/collectors"

# All known hosts
HOSTS=(
    orchestrator
    postgres-main
    imac
    hz.62
    hz.113
    hz.118
    hz.123
    hz.157
    hz.164
    hz.215
    hz.223
    hz.247
)

deploy_to_host() {
    local host_code="$1"
    local api_url="${2:-$DEFAULT_API_URL}"

    echo "=== Deploying agent to $host_code ==="

    # Create directories
    ssh "$host_code" "mkdir -p $REMOTE_AGENT_DIR/internalcmdb/collectors/agent/collectors $REMOTE_CONFIG_DIR /var/log/internalcmdb"

    # Copy agent package
    scp -r "$AGENT_SRC/collectors/" "$host_code:$REMOTE_AGENT_DIR/internalcmdb/collectors/"

    # Copy __init__.py for package structure
    ssh "$host_code" "touch $REMOTE_AGENT_DIR/internalcmdb/__init__.py"

    # Validate URL scheme
    if [[ "$api_url" != https://* ]]; then
        echo "WARNING: api_url '$api_url' is not HTTPS — agents should use TLS in production"
    fi

    # Generate agent config
    ssh "$host_code" "cat > $REMOTE_CONFIG_DIR/agent.toml << TOML
[agent]
api_url = \"$api_url\"
host_code = \"$host_code\"
log_level = \"INFO\"
verify_ssl = true
# ca_bundle = \"\"  # Set to CA cert path for self-signed Traefik certs
TOML"

    # Install systemd unit
    scp "$SYSTEMD_UNIT" "$host_code:/etc/systemd/system/internalcmdb-agent.service"

    # Install httpx (the only external dependency)
    ssh "$host_code" "pip3 install httpx 2>/dev/null || python3 -m pip install httpx 2>/dev/null || true"

    # Enable and start
    ssh "$host_code" "systemctl daemon-reload && systemctl enable internalcmdb-agent && systemctl restart internalcmdb-agent"

    # Verify
    sleep 2
    ssh "$host_code" "systemctl is-active internalcmdb-agent && echo '✓ Agent running on $host_code' || echo '✗ Agent failed on $host_code'"

    echo ""
}

# Main
TARGET="${1:-}"
API_URL="${2:-$DEFAULT_API_URL}"

if [[ -z "$TARGET" ]]; then
    echo "Usage: $0 <host_code|all> [api_url]"
    exit 1
fi

if [[ "$TARGET" == "all" ]]; then
    for host in "${HOSTS[@]}"; do
        deploy_to_host "$host" "$API_URL" || echo "WARNING: Failed to deploy to $host"
    done
    echo "=== Deployment complete ==="
else
    deploy_to_host "$TARGET" "$API_URL"
fi
