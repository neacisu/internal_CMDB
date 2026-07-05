#!/usr/bin/env bash
# Rotate JWT_SECRET_KEY in OpenBao and reload the internalCMDB API key ring.
#
# Zero-downtime rotation procedure:
#   1. Write a NEW JWT_SECRET_KEY to KV-v2 (creates version N+1).
#   2. Call POST /api/v1/auth/secrets/reload (admin session required).
#   3. Existing sessions signed with the previous key remain valid until expiry.
#   4. New logins are signed with the current key.
#
# Prerequisites:
#   - bao CLI authenticated (BAO_ADDR + BAO_TOKEN or AppRole env vars)
#   - Admin session cookie or bearer token for the reload endpoint
#
# Usage:
#   export BAO_ADDR=https://s3cr3ts.neanelu.ro:8200
#   export BAO_TOKEN=<admin-or-provisioning-token>
#   export CMDB_API_URL=https://infraq.app
#   export CMDB_SESSION=<admin cmdb_session cookie value>
#   ./scripts/rotate_jwt.sh
#
# NEVER print secret values — this script writes via a temp file with mode 600.
set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

BAO_ADDR="${BAO_ADDR:-${VAULT_ADDR:-http://localhost:8200}}"
BAO_MOUNT="${BAO_MOUNT:-secret}"
BAO_PATH="${BAO_PATH:-internalcmdb}"
CMDB_API_URL="${CMDB_API_URL:-http://127.0.0.1:4444}"
CMDB_SESSION="${CMDB_SESSION:-}"

command -v bao >/dev/null 2>&1 || die "bao CLI not found"
command -v openssl >/dev/null 2>&1 || die "openssl not found"
command -v curl >/dev/null 2>&1 || die "curl not found"

[[ -n "${BAO_TOKEN:-${VAULT_TOKEN:-}}" ]] || {
  [[ -n "${BAO_ROLE_ID:-${VAULT_ROLE_ID:-}}" ]] || die "Set BAO_TOKEN or BAO_ROLE_ID for authentication"
  [[ -n "${BAO_SECRET_ID:-${VAULT_SECRET_ID:-}}" ]] || die "Set BAO_SECRET_ID when using AppRole"
  LOGIN_JSON="$(bao write -format=json auth/approle/login \
    role_id="${BAO_ROLE_ID:-${VAULT_ROLE_ID}}" \
    secret_id="${BAO_SECRET_ID:-${VAULT_SECRET_ID}}" 2>/dev/null)" \
    || die "AppRole login failed"
  export BAO_TOKEN
  BAO_TOKEN="$(echo "$LOGIN_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["auth"]["client_token"])')"
}

NEW_SECRET_FILE="$(mktemp)"
chmod 600 "$NEW_SECRET_FILE"
trap 'rm -f "$NEW_SECRET_FILE"' EXIT

openssl rand -base64 48 | tr -d '\n' >"$NEW_SECRET_FILE"

echo "Writing new JWT_SECRET_KEY version to OpenBao (${BAO_MOUNT}/${BAO_PATH})..."
bao kv patch -mount="$BAO_MOUNT" "$BAO_PATH" "JWT_SECRET_KEY=@${NEW_SECRET_FILE}" \
  || bao kv put -mount="$BAO_MOUNT" "$BAO_PATH" "JWT_SECRET_KEY=@${NEW_SECRET_FILE}" \
  || die "Failed to write JWT_SECRET_KEY to OpenBao"

echo "Triggering API secret reload at ${CMDB_API_URL}/api/v1/auth/secrets/reload ..."
if [[ -z "$CMDB_SESSION" ]]; then
  die "CMDB_SESSION (admin cookie value) is required for reload"
fi

HTTP_CODE="$(curl -sS -o /tmp/rotate_jwt_reload.json -w '%{http_code}' \
  -X POST "${CMDB_API_URL}/api/v1/auth/secrets/reload" \
  -H "Cookie: cmdb_session=${CMDB_SESSION}" \
  -H "Content-Type: application/json")"

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "Reload failed (HTTP ${HTTP_CODE}):" >&2
  cat /tmp/rotate_jwt_reload.json >&2 || true
  die "Secret reload endpoint returned ${HTTP_CODE}"
fi

echo "OK: JWT key rotated in OpenBao and API ring reloaded (HTTP 200)."
echo "Verify: log in with a new session; existing sessions remain valid until expiry."
