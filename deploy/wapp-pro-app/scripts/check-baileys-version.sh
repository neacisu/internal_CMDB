#!/usr/bin/env bash
# Compare remote Baileys default version with CONFIG_SESSION_PHONE_VERSION in .env.evolution.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${STACK_DIR}/.env.evolution"
BAILEYS_JSON_URL="https://raw.githubusercontent.com/WhiskeySockets/Baileys/master/src/Defaults/baileys-version.json"
WEBHOOK_URL="${BAILEYS_ALERT_WEBHOOK:-}"

log() { echo "[$(date -Iseconds)] $*"; }

remote_version="$(curl -fsSL "$BAILEYS_JSON_URL" | jq -r '.version // empty')" \
  || { log "WARN: failed to fetch $BAILEYS_JSON_URL"; exit 0; }

[[ -n "$remote_version" ]] || { log "WARN: empty version in upstream JSON"; exit 0; }

if [[ ! -f "$ENV_FILE" ]]; then
  log "WARN: $ENV_FILE missing — skip compare"
  exit 0
fi

local_line="$(grep -E '^CONFIG_SESSION_PHONE_VERSION=' "$ENV_FILE" | tail -1 || true)"
local_version="${local_line#CONFIG_SESSION_PHONE_VERSION=}"
local_version="${local_version//\"/}"

if [[ -z "$local_version" ]]; then
  log "WARN: CONFIG_SESSION_PHONE_VERSION not set in $ENV_FILE"
  exit 0
fi

if [[ "$remote_version" != "$local_version" ]]; then
  log "WARN: Baileys upstream version ($remote_version) differs from CONFIG_SESSION_PHONE_VERSION ($local_version). Update .env.evolution when ready."
  if [[ -n "$WEBHOOK_URL" ]]; then
    payload="$(jq -n --arg r "$remote_version" --arg l "$local_version" \
      '{text: ("Baileys version drift: upstream=" + $r + " env=" + $l)}')"
    curl -fsS -X POST -H "Content-Type: application/json" -d "$payload" "$WEBHOOK_URL" \
      || log "WARN: webhook post failed"
  fi
  exit 0
fi

log "OK: CONFIG_SESSION_PHONE_VERSION matches upstream ($remote_version)."
