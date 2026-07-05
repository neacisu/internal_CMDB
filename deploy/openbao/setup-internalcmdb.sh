#!/usr/bin/env bash
# Provision OpenBao resources for internalCMDB (F0.1 + F0.3).
#
# Creates:
#   - KV-v2 secrets at secret/internalcmdb (SECRET_KEY, JWT_SECRET_KEY, REDIS_PASSWORD)
#   - Database connection + static role for user internalcmdb (14-day rotation)
#   - AppRole auth for internalcmdb-api/worker containers
#   - Policies scoped to least privilege
#
# NEVER prints secret values.  Placeholders are written to temp files (mode 600)
# and deleted immediately after use.
#
# Prerequisites:
#   - bao CLI with admin/root token (BAO_TOKEN or VAULT_TOKEN)
#   - PostgreSQL reachable from OpenBao for database secrets engine
#
# Usage:
#   export BAO_ADDR=https://s3cr3ts.neanelu.ro:8200
#   export BAO_TOKEN=<root-or-admin-token>
#   export PG_HOST=internalcmdb-postgres
#   export PG_PORT=5432
#   export PG_ADMIN_USER=postgres
#   export PG_ADMIN_PASSWORD_FILE=/run/secrets/pg_admin_password
#   ./deploy/openbao/setup-internalcmdb.sh
set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

BAO_ADDR="${BAO_ADDR:-${VAULT_ADDR:-http://localhost:8200}}"
PG_HOST="${PG_HOST:-internalcmdb-postgres}"
PG_PORT="${PG_PORT:-5432}"
PG_ADMIN_USER="${PG_ADMIN_USER:-postgres}"
PG_DB_NAME="${PG_DB_NAME:-internalCMDB}"
APP_DB_USER="${APP_DB_USER:-internalcmdb}"
STATIC_ROLE="${STATIC_ROLE:-internalcmdb}"
KV_MOUNT="${KV_MOUNT:-secret}"
KV_PATH="${KV_PATH:-internalcmdb}"
APPROLE_NAME="${APPROLE_NAME:-internalcmdb}"
POLICY_NAME="${POLICY_NAME:-internalcmdb-read}"
DB_CONFIG_NAME="${DB_CONFIG_NAME:-internalcmdb-postgres}"
ROTATION_DAYS="${ROTATION_DAYS:-14}"
ROTATION_SECONDS=$((ROTATION_DAYS * 86400))

command -v bao >/dev/null 2>&1 || die "bao CLI not found"
command -v openssl >/dev/null 2>&1 || die "openssl not found"

[[ -n "${BAO_TOKEN:-${VAULT_TOKEN:-}}" ]] || die "Set BAO_TOKEN or VAULT_TOKEN"

if [[ -n "${PG_ADMIN_PASSWORD_FILE:-}" && -f "$PG_ADMIN_PASSWORD_FILE" ]]; then
  PG_ADMIN_PASSWORD="$(<"$PG_ADMIN_PASSWORD_FILE")"
elif [[ -n "${PG_ADMIN_PASSWORD:-}" ]]; then
  PG_ADMIN_PASSWORD="$PG_ADMIN_PASSWORD"
else
  die "Set PG_ADMIN_PASSWORD or PG_ADMIN_PASSWORD_FILE"
fi

tmpdir="$(mktemp -d)"
chmod 700 "$tmpdir"
trap 'rm -rf "$tmpdir"' EXIT

write_secret_file() {
  local name="$1"
  openssl rand -base64 48 | tr -d '\n' >"${tmpdir}/${name}"
  chmod 600 "${tmpdir}/${name}"
}

echo "==> Ensuring KV-v2 mount at ${KV_MOUNT}/"
if ! bao secrets list -format=json 2>/dev/null | grep -q "\"${KV_MOUNT}/\""; then
  bao secrets enable -path="${KV_MOUNT}" kv-v2 || die "Failed to enable KV-v2 at ${KV_MOUNT}"
fi

echo "==> Writing application secrets to ${KV_MOUNT}/${KV_PATH} (values NOT printed)"
write_secret_file SECRET_KEY
write_secret_file JWT_SECRET_KEY
write_secret_file REDIS_PASSWORD
bao kv put -mount="${KV_MOUNT}" "${KV_PATH}" \
  "SECRET_KEY=@${tmpdir}/SECRET_KEY" \
  "JWT_SECRET_KEY=@${tmpdir}/JWT_SECRET_KEY" \
  "REDIS_PASSWORD=@${tmpdir}/REDIS_PASSWORD" \
  || die "Failed to write KV secrets"

echo "==> Ensuring database secrets engine"
if ! bao secrets list -format=json 2>/dev/null | grep -q '"database/"'; then
  bao secrets enable database || die "Failed to enable database secrets engine"
fi

echo "==> Configuring database connection ${DB_CONFIG_NAME}"
bao write "database/config/${DB_CONFIG_NAME}" \
  plugin_name="postgresql-database-plugin" \
  allowed_roles="${STATIC_ROLE},internalcmdb-monitoring" \
  connection_url="postgresql://{{username}}:{{password}}@${PG_HOST}:${PG_PORT}/${PG_DB_NAME}?sslmode=disable" \
  username="${PG_ADMIN_USER}" \
  password="${PG_ADMIN_PASSWORD}" \
  || die "Failed to configure database connection"

echo "==> Creating static role ${STATIC_ROLE} (rotation ${ROTATION_DAYS}d)"
bao write "database/static-roles/${STATIC_ROLE}" \
  db_name="${DB_CONFIG_NAME}" \
  username="${APP_DB_USER}" \
  rotation_period="${ROTATION_SECONDS}" \
  || die "Failed to create static role"

echo "==> Creating policy ${POLICY_NAME}"
bao policy write "${POLICY_NAME}" - <<EOF
# internalCMDB application — read-only access to its secrets
path "secret/data/${KV_PATH}" {
  capabilities = ["read"]
}
path "secret/metadata/${KV_PATH}" {
  capabilities = ["read", "list"]
}
path "database/static-creds/${STATIC_ROLE}" {
  capabilities = ["read"]
}
EOF

echo "==> Enabling AppRole auth (if not already enabled)"
if ! bao auth list -format=json 2>/dev/null | grep -q '"approle/"'; then
  bao auth enable approle || die "Failed to enable AppRole auth"
fi

echo "==> Creating AppRole ${APPROLE_NAME}"
bao write "auth/approle/role/${APPROLE_NAME}" \
  token_policies="${POLICY_NAME}" \
  token_ttl="1h" \
  token_max_ttl="4h" \
  secret_id_ttl="0" \
  secret_id_num_uses="0" \
  || die "Failed to create AppRole"

ROLE_ID="$(bao read -field=role_id "auth/approle/role/${APPROLE_NAME}/role-id")"
SECRET_ID="$(bao write -f -field=secret_id "auth/approle/role/${APPROLE_NAME}/secret-id")"

echo "==> AppRole provisioned (store secret_id securely, never commit):"
echo "    VAULT_ROLE_ID=${ROLE_ID}"
echo "    secret_id written to ${tmpdir}/secret_id (mode 600 — copy to /run/secrets/bao_secret_id)"
printf '%s' "$SECRET_ID" >"${tmpdir}/secret_id"
chmod 600 "${tmpdir}/secret_id"

echo "==> Verifying static credentials path (username only, password NOT printed)"
CREDS_USER="$(bao read -field=username "database/static-creds/${STATIC_ROLE}")"
echo "    static-creds username: ${CREDS_USER}"

echo "OK: OpenBao provisioning complete for internalCMDB."
echo "Next steps:"
echo "  1. Copy ${tmpdir}/secret_id to /run/secrets/bao_secret_id on the orchestrator (chmod 600)."
echo "  2. Set VAULT_ADDR=${BAO_ADDR} and VAULT_ROLE_ID=${ROLE_ID} in docker-compose."
echo "  3. Deploy internalcmdb-api/worker with ENV=production (no .env file)."
echo "  4. Remove bootstrap .env after verifying API health."
