#!/usr/bin/env bash
# setup_firewall.sh — Idempotent UFW firewall rules for internalCMDB nodes.
#
# Restricts monitoring exporters to the orchestrator IP and ensures
# agent communication happens over HTTPS only.
#
# Usage:
#   sudo ./scripts/setup_firewall.sh

set -euo pipefail

ORCHESTRATOR_IP="77.42.76.185"
VSWITCH_SUBNET="10.0.0.0/24"

log() { echo "[$(date -Iseconds)] $*"; }

# Root check — UFW requires root privileges
if [[ $EUID -ne 0 ]]; then
    log "ERROR: This script must be run as root (got UID=$EUID)"
    log "       Re-run with: sudo $0"
    exit 1
fi

ensure_rule() {
    local action="$1"; shift
    local rule_desc
    rule_desc="$(printf '%s ' "$@")"
    if ufw status numbered | grep -qF "$rule_desc"; then
        log "Rule already exists: ufw $action $rule_desc"
    else
        ufw "$action" "$@"
        log "Added rule: ufw $action $rule_desc"
    fi
}

# Ensure UFW is installed and enabled
if ! command -v ufw &>/dev/null; then
    log "ERROR: ufw not found. Install with: apt install ufw"
    exit 1
fi

if ufw status | grep -q "Status: inactive"; then
    log "Enabling UFW..."
    ufw --force enable
fi

# Default policies
ufw default deny incoming 2>/dev/null || true
ufw default allow outgoing 2>/dev/null || true

# --- SSH (always allow) ---
ensure_rule allow 22/tcp

# --- HTTPS (agent communication) ---
ensure_rule allow 443/tcp

# --- node_exporter :9100 — orchestrator only ---
ensure_rule allow from "$ORCHESTRATOR_IP" to any port 9100 proto tcp

# --- cAdvisor :8080 — orchestrator only ---
ensure_rule allow from "$ORCHESTRATOR_IP" to any port 8080 proto tcp

# --- nvidia_exporter :9835 — orchestrator only ---
ensure_rule allow from "$ORCHESTRATOR_IP" to any port 9835 proto tcp

# --- Internal services — vSwitch subnet ---
ensure_rule allow from "$VSWITCH_SUBNET"

# --- Block direct HTTP to API (force HTTPS) ---
# Port 4444 (dev API) should not be reachable externally
ensure_rule deny 4444/tcp

# --- IPv6: deny incoming by default (UFW manages ip6tables when enabled) ---
# Ensure /etc/default/ufw has IPV6=yes so rules above are mirrored to ip6tables.
if grep -q "^IPV6=no" /etc/default/ufw 2>/dev/null; then
    sed -i 's/^IPV6=no/IPV6=yes/' /etc/default/ufw
    log "Enabled IPv6 support in /etc/default/ufw — restart UFW to apply"
fi

log "Firewall rules applied successfully."
ufw status verbose
