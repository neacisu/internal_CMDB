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
BOOTSTRAP_SECRET="${BOOTSTRAP_SECRET:-/run/secrets/bootstrap_enroll_token}"
REMOTE_BOOTSTRAP="/etc/internalcmdb/bootstrap.token"

# Host code → SSH alias mapping
declare -A HOST_SSH=(
    [orchestrator]="orchestrator"
    [postgres-main]="postgres-main"
    [imac]="Alexs-iMac.local"
    [hz.62]="hz.62"
    [hz.113]="hz.113"
    [hz.118]="hz.118"
    [lxc-hz118-traktors]="hz.118.lxc.100"
    [lxc-hz118-tecdocnode]="hz.118.lxc.101"
    [lxc-hz118-tecdocmysql]="hz.118.lxc.102"
    [lxc-hz118-mediserver2]="hz.118.lxc.103"
    [hz.123]="hz.123"
    [hz.157]="hz.157"
    [hz.164]="hz.164"
    [hz.215]="hz.215"
    [hz.223]="hz.223"
    [hz.247]="hz.247"
    [lxc-llm-guard]="lxc-llm-guard"
    [lxc-wapp-pro-app]="wapp-pro-app"
    [lxc-postgres-main]="lxc-postgres-main"
    [lxc-ci-worker]="lxc-ci-worker"
    [lxc-neanelu-prod]="lxc-neanelu-prod"
    [lxc-neanelu-staging]="lxc-neanelu-staging"
    [lxc-prod-cerniq]="lxc-prod-cerniq"
    [lxc-staging-cerniq]="lxc-staging-cerniq"
)

# Host code → config file name mapping (matches deploy/configs/agents/*.toml)
declare -A HOST_CONFIG=(
    [orchestrator]="orchestrator"
    [postgres-main]="postgres-main"
    [imac]="imac"
    [hz.62]="hz-62"
    [hz.113]="hz-113"
    [hz.118]="hz-118"
    [lxc-hz118-traktors]="lxc-hz118-traktors"
    [lxc-hz118-tecdocnode]="lxc-hz118-tecdocnode"
    [lxc-hz118-tecdocmysql]="lxc-hz118-tecdocmysql"
    [lxc-hz118-mediserver2]="lxc-hz118-mediserver2"
    [hz.123]="hz-123"
    [hz.157]="hz-157"
    [hz.164]="proxmox"
    [hz.215]="hz-215"
    [hz.223]="hz-223"
    [hz.247]="hz-247"
    [lxc-llm-guard]="lxc-llm-guard"
    [lxc-wapp-pro-app]="lxc-wapp-pro-app"
    [lxc-postgres-main]="lxc-postgres-main"
    [lxc-ci-worker]="lxc-ci-worker"
    [lxc-neanelu-prod]="lxc-neanelu-prod"
    [lxc-neanelu-staging]="lxc-neanelu-staging"
    [lxc-prod-cerniq]="lxc-prod-cerniq"
    [lxc-staging-cerniq]="lxc-staging-cerniq"
)

HOSTS=("${!HOST_SSH[@]}")

# ── Helpers ────────────────────────────────────────────────────────────────────

# verify_api_reachable: check that the CMDB API health endpoint responds before
# deploying an agent that will immediately try to enroll with it.  A failure
# emits a warning but does NOT abort deployment — the agent buffers events and
# retries on its own schedule.
verify_api_reachable() {
    local url="$1"
    if curl -sf --max-time 5 "${url%/collectors}/health" -o /dev/null; then
        echo "  ✓ API reachable: ${url%/collectors}/health"
    else
        echo "  WARN: API not responding at ${url%/collectors}/health — proceeding anyway" >&2
        echo "        The agent will retry enrollment on startup." >&2
    fi
}

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

    # Verify API endpoint is reachable before deploying (advisory — does not abort).
    # api_url is used here and also compared against the TOML's own api_url field
    # to surface configuration drift early.
    verify_api_reachable "$api_url"
    local toml_api_url
    toml_api_url=$(grep '^api_url' "$config_file" 2>/dev/null \
        | sed 's/.*= *["'\'']\(.*\)["'\'']/\1/' | head -1 || true)
    if [[ -n "$toml_api_url" && "$toml_api_url" != "$api_url" ]]; then
        echo "  WARN: api_url mismatch — TOML has '${toml_api_url}', script default is '${api_url}'" >&2
    fi

    # Create directories — args passed directly to avoid SC2029
    ssh "$ssh_host" mkdir -p \
        "${REMOTE_AGENT_DIR}/internalcmdb/collectors/agent/collectors" \
        "${REMOTE_CONFIG_DIR}" \
        /var/log/internalcmdb

    # Copy package init files
    # shellcheck disable=SC2029  # REMOTE_AGENT_DIR expands client-side intentionally
    ssh "$ssh_host" touch "${REMOTE_AGENT_DIR}/internalcmdb/__init__.py"

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

    # Copy bootstrap enrollment token (required for enroll / re-enroll)
    if [[ -f "$BOOTSTRAP_SECRET" ]]; then
        scp "$BOOTSTRAP_SECRET" "$ssh_host:$REMOTE_BOOTSTRAP"
        ssh "$ssh_host" "chmod 600 '$REMOTE_BOOTSTRAP'"
        echo "  ✓ Bootstrap token deployed to $REMOTE_BOOTSTRAP"
    else
        echo "  WARN: $BOOTSTRAP_SECRET missing — agent enroll will fail until token is present" >&2
    fi

    # Ensure log/credentials directory exists (under ReadWritePaths in systemd unit)
    ssh "$ssh_host" "mkdir -p /var/log/internalcmdb && chmod 755 /var/log/internalcmdb"

    # Install systemd unit (resolve python3 on remote)
    scp "$SYSTEMD_UNIT" "$ssh_host:/etc/systemd/system/internalcmdb-agent.service"
    ssh "$ssh_host" bash << 'REMOTE_UNIT'
        py_bin="$(command -v python3 || true)"
        if [[ -n "$py_bin" && -x "$py_bin" ]]; then
            sed -i "s|^ExecStart=.*|ExecStart=${py_bin} -m internalcmdb.collectors.agent|" \
                /etc/systemd/system/internalcmdb-agent.service
        fi
REMOTE_UNIT

    # Determine which python binary the service unit uses (for httpx install)
    local py_bin
    py_bin=$(ssh "$ssh_host" "grep '^ExecStart=' /etc/systemd/system/internalcmdb-agent.service | sed 's|ExecStart=\([^ ]*\).*|\1|'")
    [[ -z "$py_bin" ]] && py_bin="python3"

    # Install httpx for the exact Python that will run the agent.
    # python3.12+ removed distutils so we must bootstrap pip via ensurepip first.
    # py_bin is passed as a positional argument to the remote bash -s invocation
    # so $1 inside the single-quoted heredoc receives the binary path without
    # requiring a double-quoted shell string (eliminates SC2029).
    ssh "$ssh_host" bash -s -- "$py_bin" << 'REMOTE_INSTALL'
        py_bin="$1"
        if "$py_bin" -c 'import httpx' 2>/dev/null; then
            exit 0
        fi
        "$py_bin" -m ensurepip --upgrade 2>/dev/null || true
        "$py_bin" -m pip install --root-user-action=ignore httpx 2>/dev/null || true
REMOTE_INSTALL

    # Enable and start — compound shell operators require bash -c; no variables
    # inside the single-quoted string so there is no SC2029 concern.
    ssh "$ssh_host" bash -c 'systemctl daemon-reload && systemctl enable internalcmdb-agent && systemctl restart internalcmdb-agent'

    # Verify — echo runs locally so $host_code never appears inside an SSH shell string
    sleep 2
    if ssh "$ssh_host" systemctl is-active --quiet internalcmdb-agent; then
        echo "  ✓ Agent running on ${host_code}"
    else
        echo "  ✗ Agent failed on ${host_code}"
        ssh "$ssh_host" journalctl -u internalcmdb-agent -n 20 --no-pager 2>/dev/null || true
    fi

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
