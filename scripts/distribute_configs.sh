#!/usr/bin/env bash
# distribute_configs.sh — SCP agent configs to each host via SSH.
#
# Idempotent: only copies when the config has changed (checksum comparison).
#
# Usage:
#   ./scripts/distribute_configs.sh [host_code]
#   ./scripts/distribute_configs.sh            # distribute to all hosts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$REPO_ROOT/deploy/configs/agents"
REMOTE_CONFIG="/etc/internalcmdb/agent.toml"

# Host code → SSH alias mapping (matches deploy_agent.sh)
# Keys = basename of deploy/configs/agents/<name>.toml (no hz-164.toml — use proxmox for hz.164)
declare -A HOST_MAP=(
    [orchestrator]="orchestrator"
    [postgres-main]="postgres-main"
    [imac]="imac"
    [hz-113]="hz.113"
    [hz-62]="hz.62"
    [hz-118]="hz.118"
    [lxc-hz118-traktors]="hz.118.lxc.100"
    [lxc-hz118-tecdocnode]="hz.118.lxc.101"
    [lxc-hz118-tecdocmysql]="hz.118.lxc.102"
    [lxc-hz118-mediserver2]="hz.118.lxc.103"
    [hz-123]="hz.123"
    [hz-157]="hz.157"
    [hz-215]="hz.215"
    [hz-223]="hz.223"
    [hz-247]="hz.247"
    [proxmox]="hz.164"
    [lxc]="hz.164"
    [lxc-llm-guard]="lxc-llm-guard"
    [lxc-wapp-pro-app]="wapp-pro-app"
    [lxc-postgres-main]="lxc-postgres-main"
    [lxc-ci-worker]="lxc-ci-worker"
    [lxc-neanelu-prod]="lxc-neanelu-prod"
    [lxc-neanelu-staging]="lxc-neanelu-staging"
    [lxc-prod-cerniq]="lxc-prod-cerniq"
    [lxc-staging-cerniq]="lxc-staging-cerniq"
)

log() { echo "[$(date -Iseconds)] $*"; }

distribute_to_host() {
    local config_name="$1"
    local config_file="$CONFIG_DIR/${config_name}.toml"
    local ssh_host="${HOST_MAP[$config_name]:-$config_name}"

    if [[ ! -f "$config_file" ]]; then
        log "SKIP: No config file found for '$config_name' at $config_file"
        return 0
    fi

    # Validate TOML syntax before distributing
    if command -v python3 &>/dev/null; then
        if ! python3 -c "import tomllib; tomllib.load(open('$config_file', 'rb'))" 2>/dev/null; then
            log "ERROR: Invalid TOML syntax in $config_file — aborting for $config_name"
            return 1
        fi
    fi

    log "Checking $config_name ($ssh_host)..."

    local local_hash
    local_hash=$(sha256sum "$config_file" | awk '{print $1}')

    # Run sha256sum on the remote host; awk to extract the hash runs locally.
    # REMOTE_CONFIG is passed as a discrete SSH argument — no double-quoted
    # shell string — which eliminates the SC2029 client-side expansion warning.
    local remote_hash
    if remote_hash_line=$(ssh "$ssh_host" sha256sum -- "$REMOTE_CONFIG" 2>/dev/null); then
        remote_hash=$(awk '{print $1}' <<< "$remote_hash_line")
    else
        remote_hash="none"
    fi

    if [[ "$local_hash" == "$remote_hash" ]]; then
        log "  ✓ Config unchanged on $ssh_host — skipping"
        return 0
    fi

    ssh "$ssh_host" "mkdir -p /etc/internalcmdb"

    # Backup existing remote config before overwrite
    if [[ "$remote_hash" != "none" ]]; then
        # Pass cp args directly — no shell-string quoting needed (SC2029 avoided).
        ssh "$ssh_host" cp -- "$REMOTE_CONFIG" "${REMOTE_CONFIG}.bak" || true
        log "  → Backed up existing config on $ssh_host"
    fi

    scp "$config_file" "$ssh_host:$REMOTE_CONFIG"
    log "  → Updated config on $ssh_host"

    # Restart agent to pick up new config
    ssh "$ssh_host" "systemctl restart internalcmdb-agent 2>/dev/null || true"
    log "  → Restarted agent on $ssh_host"
}

# Main
TARGET="${1:-all}"

if [[ "$TARGET" == "all" ]]; then
    for config_file in "$CONFIG_DIR"/*.toml; do
        name="$(basename "$config_file" .toml)"
        distribute_to_host "$name" || log "WARNING: Failed for $name"
    done
    log "=== Distribution complete ==="
else
    distribute_to_host "$TARGET"
fi
