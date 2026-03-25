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
CONFIG_DIR="$REPO_ROOT/deploy/configs/agents"
REMOTE_AGENT_DIR="/opt/internalcmdb/agent"
REMOTE_CONFIG_DIR="/etc/internalcmdb"
DEFAULT_API_URL="https://infraq.app/api/v1/collectors"

# Host code → SSH alias mapping
declare -A HOST_SSH=(
    [orchestrator]="orchestrator"
    [postgres-main]="postgres-main"
    [imac]="imac"
    [hz.62]="hz.62"
    [hz.113]="hz.113"
    [hz.118]="hz.118"
    [hz.123]="hz.123"
    [hz.157]="hz.157"
    [hz.164]="hz.164"
    [hz.215]="hz.215"
    [hz.223]="hz.223"
    [hz.247]="hz.247"
    [lxc-llm-guard]="lxc-llm-guard"
    [lxc-wapp-pro-app]="wapp-pro-app"
)

# Host code → config file name mapping (matches deploy/configs/agents/*.toml)
declare -A HOST_CONFIG=(
    [orchestrator]="orchestrator"
    [postgres-main]="postgres-main"
    [imac]="imac"
    [hz.62]="hz-62"
    [hz.113]="hz-113"
    [hz.118]="hz-118"
    [hz.123]="hz-123"
    [hz.157]="hz-157"
    [hz.164]="proxmox"
    [hz.215]="hz-215"
    [hz.223]="hz-223"
    [hz.247]="hz-247"
    [lxc-llm-guard]="lxc-llm-guard"
    [lxc-wapp-pro-app]="lxc-wapp-pro-app"
)

HOSTS=("${!HOST_SSH[@]}")

deploy_to_host() {
    local host_code="$1"
    local api_url="${2:-$DEFAULT_API_URL}"
    local ssh_host="${HOST_SSH[$host_code]:-$host_code}"
    local config_name="${HOST_CONFIG[$host_code]:-$host_code}"
    local config_file="$CONFIG_DIR/${config_name}.toml"

    echo "=== Deploying agent to $host_code (SSH: $ssh_host) ==="

    # Validate config file exists
    if [[ ! -f "$config_file" ]]; then
        echo "ERROR: Config file not found: $config_file"
        echo "       Create it at deploy/configs/agents/${config_name}.toml"
        return 1
    fi

    # Validate TOML syntax
    if command -v python3 &>/dev/null; then
        if ! python3 -c "import tomllib; tomllib.load(open('$config_file', 'rb'))" 2>/dev/null; then
            echo "ERROR: Invalid TOML syntax in $config_file"
            return 1
        fi
    fi

    # Create directories
    ssh "$ssh_host" "mkdir -p $REMOTE_AGENT_DIR/internalcmdb/collectors/agent/collectors $REMOTE_CONFIG_DIR /var/log/internalcmdb"

    # Copy package init files
    ssh "$ssh_host" "touch $REMOTE_AGENT_DIR/internalcmdb/__init__.py"

    # Copy collectors package with correct structure
    scp "$AGENT_SRC/collectors/__init__.py" "$ssh_host:$REMOTE_AGENT_DIR/internalcmdb/collectors/__init__.py"
    scp "$AGENT_SRC/collectors/schedule_tiers.py" "$ssh_host:$REMOTE_AGENT_DIR/internalcmdb/collectors/schedule_tiers.py"
    for f in staleness.py fleet_health.py diff_engine.py; do
        [[ -f "$AGENT_SRC/collectors/$f" ]] && scp "$AGENT_SRC/collectors/$f" "$ssh_host:$REMOTE_AGENT_DIR/internalcmdb/collectors/$f"
    done

    # Copy agent subpackage (daemon, __main__, updater)
    for f in __init__.py __main__.py daemon.py updater.py; do
        scp "$AGENT_SRC/collectors/agent/$f" "$ssh_host:$REMOTE_AGENT_DIR/internalcmdb/collectors/agent/$f"
    done

    # Copy all collector modules
    scp "$AGENT_SRC/collectors/agent/collectors/__init__.py" "$ssh_host:$REMOTE_AGENT_DIR/internalcmdb/collectors/agent/collectors/__init__.py"
    scp "$AGENT_SRC/collectors/agent/collectors/"*.py "$ssh_host:$REMOTE_AGENT_DIR/internalcmdb/collectors/agent/collectors/"

    # Copy the per-host TOML config
    scp "$config_file" "$ssh_host:$REMOTE_CONFIG_DIR/agent.toml"

    # Install systemd unit
    scp "$SYSTEMD_UNIT" "$ssh_host:/etc/systemd/system/internalcmdb-agent.service"

    # Install httpx (the only external dependency)
    # Handle PEP 668 (Debian 13+, Ubuntu 24.04+) and Python <3.11 (needs tomli)
    ssh "$ssh_host" "
        python3 -c 'import httpx' 2>/dev/null && exit 0
        apt-get install -y -qq python3-httpx 2>/dev/null && exit 0
        pip3 install --break-system-packages httpx 2>/dev/null && exit 0
        pip3 install httpx 2>/dev/null && exit 0
        python3 -m pip install httpx 2>/dev/null || true
    "
    # tomli fallback for Python < 3.11
    ssh "$ssh_host" "python3 -c 'import tomllib' 2>/dev/null || pip3 install --break-system-packages tomli 2>/dev/null || pip3 install tomli 2>/dev/null || true"

    # Enable and start
    ssh "$ssh_host" "systemctl daemon-reload && systemctl enable internalcmdb-agent && systemctl restart internalcmdb-agent"

    # Verify
    sleep 2
    ssh "$ssh_host" "systemctl is-active internalcmdb-agent && echo '✓ Agent running on $host_code' || echo '✗ Agent failed on $host_code'"

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
