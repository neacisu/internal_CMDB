#!/usr/bin/env bash
# Pe LXC-uri din VLAN 4000, IP-urile publice ale orchestratorului (77.42.x) pot fi
# nerutabile; Traefik pe VIP intern răspunde pe SNI. Acest script forțează /etc/hosts.
set -euo pipefail
VIP="${1:-10.0.1.10}"
tmp="$(mktemp)"
grep -vE '[[:space:]]redis\.infraq\.app$|[[:space:]]logs-neanelu\.neanelu\.ro$' /etc/hosts >"$tmp" || true
echo "${VIP} redis.infraq.app" >>"$tmp"
echo "${VIP} logs-neanelu.neanelu.ro" >>"$tmp"
install -m 644 "$tmp" /etc/hosts
rm -f "$tmp"
echo "OK: /etc/hosts — redis.infraq.app și logs-neanelu.neanelu.ro → ${VIP}"
