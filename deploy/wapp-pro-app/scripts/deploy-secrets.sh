#!/usr/bin/env bash
# Resolve ${BAO:secret/wapp/KEY} placeholders from OpenBao KV v2 into .env.* files.
# Requires: bao CLI, jq, curl. Env: BAO_ADDR, BAO_ROLE_ID, BAO_SECRET_ID.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(dirname "$SCRIPT_DIR")"
cd "$STACK_DIR"

die() { echo "ERROR: $*" >&2; exit 1; }

[[ -n "${BAO_ADDR:-}" ]] || die "BAO_ADDR is not set"
[[ -n "${BAO_ROLE_ID:-}" ]] || die "BAO_ROLE_ID is not set"
[[ -n "${BAO_SECRET_ID:-}" ]] || die "BAO_SECRET_ID is not set"

command -v bao >/dev/null 2>&1 || die "bao CLI not found"
command -v jq >/dev/null 2>&1 || die "jq not found"

for f in .env.evolution.template .env.gateway.template; do
  [[ -f "$f" ]] || die "missing template: $f"
done

export BAO_ADDR
# AppRole → client token (non-interactive)
LOGIN_JSON="$(bao write -format=json auth/approle/login role_id="$BAO_ROLE_ID" secret_id="$BAO_SECRET_ID" 2>/dev/null)" \
  || die "AppRole login failed"
export BAO_TOKEN="$(echo "$LOGIN_JSON" | jq -r '.auth.client_token // empty')"
[[ -n "$BAO_TOKEN" && "$BAO_TOKEN" != "null" ]] || die "could not read client_token from login response"

# KV v2: single mount read as JSON
SECRET_JSON="$(bao kv get -mount=secret -format=json wapp 2>/dev/null)" \
  || SECRET_JSON="$(bao kv get -format=json secret/wapp 2>/dev/null)" \
  || die "bao kv get secret/wapp failed"

# data.data holds key-value map for KV v2
DATA="$(echo "$SECRET_JSON" | jq -r '.data.data // .data // empty')"
[[ -n "$DATA" && "$DATA" != "null" ]] || die "unexpected secret JSON (no data.data)"

substitute_template() {
  local src="$1" dst="$2"
  cp -f "$src" "$dst"
  local keys
  keys="$(echo "$DATA" | jq -r 'keys[]')"
  while IFS= read -r key; do
    [[ -z "$key" ]] && continue
    val="$(echo "$DATA" | jq -r --arg k "$key" '.[$k] // empty')"
    val="${val//$'\r'/}"
    [[ -n "$val" ]] || die "empty value for key: $key"
    esc_val="$(printf '%s\n' "$val" | sed -e 's/[\/&]/\\&/g')"
    sed -i "s|\${BAO:secret/wapp/${key}}|${esc_val}|g" "$dst"
  done <<< "$keys"
}

substitute_template .env.evolution.template .env.evolution
substitute_template .env.gateway.template .env.gateway

chmod 600 .env.evolution .env.gateway

# Verify no unresolved BAO placeholders
for f in .env.evolution .env.gateway; do
  if grep -qE '\$\{BAO:' "$f"; then
    echo "Unresolved placeholders in $f:" >&2
    grep -nE '\$\{BAO:' "$f" >&2 || true
    die "fix OpenBao keys or templates"
  fi
done

echo "OK: wrote .env.evolution and .env.gateway (mode 600), zero BAO: placeholders remaining."
