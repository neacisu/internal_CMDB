#!/usr/bin/env bash
# Provision OpenBao KV secrets for OpenRouter LLM gateway.
#
# Creates:
#   - KV-v2 at kv-llm/openrouter (MANAGEMENT_KEY, CERNIQ_APP_KEY, INFRA_APP_KEY)
#   - Policy llm-gateway-read + AppRole llm-gateway
#
# NEVER prints secret values. Keys are read from *_FILE env vars (mode 600).
set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

BAO_ADDR="${BAO_ADDR:-${VAULT_ADDR:-http://127.0.0.1:8200}}"
KV_MOUNT="${KV_MOUNT:-kv-llm}"
KV_PATH="${KV_PATH:-openrouter}"
APPROLE_NAME="${APPROLE_NAME:-llm-gateway}"
POLICY_NAME="${POLICY_NAME:-llm-gateway-read}"

if command -v bao >/dev/null 2>&1; then
  BAO=(bao)
elif docker ps --format '{{.Names}}' 2>/dev/null | grep -qx openbao; then
  BAO=(docker exec openbao bao)
else
  die "bao CLI not found and openbao container not running"
fi

read_key_file() {
  local var_name="$1"
  local file_var="${var_name}_FILE"
  local file_path="${!file_var:-}"
  if [[ -n "$file_path" && -f "$file_path" ]]; then
    cat "$file_path"
    return 0
  fi
  local direct="${!var_name:-}"
  if [[ -n "$direct" ]]; then
    printf '%s' "$direct"
    return 0
  fi
  die "Set ${var_name} or ${file_var}"
}

tmpdir="$(mktemp -d)"
chmod 700 "$tmpdir"
trap 'rm -rf "$tmpdir"' EXIT

write_from_env() {
  local name="$1"
  local env_name="$2"
  read_key_file "$env_name" >"${tmpdir}/${name}"
  chmod 600 "${tmpdir}/${name}"
  [[ -s "${tmpdir}/${name}" ]] || die "${env_name} file is empty"
}

echo "==> Ensuring KV mount ${KV_MOUNT}/ exists"
if ! "${BAO[@]}" secrets list -format=json 2>/dev/null | grep -q "\"${KV_MOUNT}/\""; then
  "${BAO[@]}" secrets enable -path="${KV_MOUNT}" kv-v2 || die "Failed to enable KV-v2"
fi

echo "==> Writing OpenRouter keys to ${KV_MOUNT}/${KV_PATH} (values NOT printed)"
write_from_env MANAGEMENT_KEY OPENROUTER_MANAGEMENT_KEY
write_from_env CERNIQ_APP_KEY OPENROUTER_CERNIQ_APP_KEY
write_from_env INFRA_APP_KEY OPENROUTER_INFRA_APP_KEY

"${BAO[@]}" kv put -mount="${KV_MOUNT}" "${KV_PATH}" \
  "MANAGEMENT_KEY=@${tmpdir}/MANAGEMENT_KEY" \
  "CERNIQ_APP_KEY=@${tmpdir}/CERNIQ_APP_KEY" \
  "INFRA_APP_KEY=@${tmpdir}/INFRA_APP_KEY" \
  || die "Failed to write OpenRouter KV secrets"

echo "==> Creating policy ${POLICY_NAME}"
"${BAO[@]}" policy write "${POLICY_NAME}" - <<EOF
path "${KV_MOUNT}/data/${KV_PATH}" {
  capabilities = ["read"]
}
path "${KV_MOUNT}/metadata/${KV_PATH}" {
  capabilities = ["read", "list"]
}
EOF

echo "==> Enabling AppRole auth (if not already enabled)"
if ! "${BAO[@]}" auth list -format=json 2>/dev/null | grep -q '"approle/"'; then
  "${BAO[@]}" auth enable approle || die "Failed to enable AppRole auth"
fi

echo "==> Creating AppRole ${APPROLE_NAME}"
"${BAO[@]}" write "auth/approle/role/${APPROLE_NAME}" \
  token_policies="${POLICY_NAME}" \
  token_ttl="1h" \
  token_max_ttl="4h" \
  secret_id_ttl="0" \
  secret_id_num_uses="0" \
  || die "Failed to create AppRole"

ROLE_ID="$("${BAO[@]}" read -field=role_id "auth/approle/role/${APPROLE_NAME}/role-id")"
SECRET_ID="$("${BAO[@]}" write -f -field=secret_id "auth/approle/role/${APPROLE_NAME}/secret-id")"

printf '%s' "$SECRET_ID" >"${tmpdir}/secret_id"
chmod 600 "${tmpdir}/secret_id"

echo "==> AppRole provisioned:"
echo "    VAULT_ROLE_ID=${ROLE_ID}"
echo "    secret_id written to ${tmpdir}/secret_id"
echo "    Copy to lxc-llm-guard:/run/secrets/bao_llm_gateway_secret_id (chmod 600)"

echo "==> Verifying KV metadata (no secret values)"
"${BAO[@]}" kv metadata get -mount="${KV_MOUNT}" "${KV_PATH}" | head -5

echo "OK: OpenRouter OpenBao provisioning complete."
