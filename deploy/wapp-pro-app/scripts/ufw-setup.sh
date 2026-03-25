#!/usr/bin/env bash
# UFW for wapp-pro-app — GAP-12 / plan 0.6.12: only HAProxy VIP may reach app ports.
set -euo pipefail

HAPROXY_VIP="${HAPROXY_VIP:-10.0.1.10}"

command -v ufw >/dev/null 2>&1 || { echo "ERROR: ufw not installed" >&2; exit 1; }

ufw default deny incoming
ufw default allow outgoing

ufw allow from "$HAPROXY_VIP" to any port 26000 proto tcp
ufw allow from "$HAPROXY_VIP" to any port 26001 proto tcp
ufw allow from "$HAPROXY_VIP" to any port 26002 proto tcp
ufw allow from "$HAPROXY_VIP" to any port 26004 proto tcp

ufw allow ssh
ufw --force enable

echo "OK: UFW enabled. Verify with: ufw status verbose"
