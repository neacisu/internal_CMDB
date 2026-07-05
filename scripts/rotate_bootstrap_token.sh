#!/usr/bin/env bash
# rotate_bootstrap_token.sh — Generate production bootstrap token and insert hash into DB.
#
# Usage:
#   ./scripts/rotate_bootstrap_token.sh [--apply]
#
# Without --apply: prints token to stdout (for manual copy) and hash for verification.
# With --apply: writes /run/secrets/bootstrap_enroll_token, inserts into Postgres, deactivates dev token.
#
# NEVER commit the plaintext token.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SECRET_FILE="/run/secrets/bootstrap_enroll_token"
LABEL="prod-bootstrap-$(date +%Y%m%d)"

APPLY=false
if [[ "${1:-}" == "--apply" ]]; then
    APPLY=true
fi

TOKEN="$(openssl rand -hex 32)"
HASH="$(printf '%s' "$TOKEN" | sha256sum | awk '{print $1}')"
EXPIRES="$(date -u -d '+90 days' '+%Y-%m-%d %H:%M:%S+00' 2>/dev/null || date -u -v+90d '+%Y-%m-%d %H:%M:%S+00')"

echo "Bootstrap label: $LABEL"
echo "SHA-256 hash: $HASH"
echo "Expires at: $EXPIRES"

if [[ "$APPLY" != true ]]; then
    echo ""
    echo "Dry-run only. Re-run with --apply to write secret file and update DB."
    echo "Plaintext token (store securely, do NOT commit):"
    echo "$TOKEN"
    exit 0
fi

install -d -m 700 /run/secrets
printf '%s' "$TOKEN" >"$SECRET_FILE"
chmod 600 "$SECRET_FILE"
echo "Wrote $SECRET_FILE (mode 600)"

# Load DB credentials from orchestrator .env if present
ENV_FILE="${REPO_ROOT}/.env"
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$ENV_FILE"
    set +a
fi

PGHOST="${POSTGRES_SYNC_HOST:-127.0.0.1}"
PGPORT="${POSTGRES_SYNC_PORT:-5433}"
PGUSER="${POSTGRES_USER:?POSTGRES_USER required}"
PGDB="${POSTGRES_DB:?POSTGRES_DB required}"
PGPASS="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}"

export PGPASSWORD="$PGPASS"

psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 <<SQL
UPDATE discovery.bootstrap_tokens SET is_active = false WHERE label = 'dev-bootstrap';
INSERT INTO discovery.bootstrap_tokens (token_hash, label, is_active, expires_at)
VALUES ('$HASH', '$LABEL', true, '$EXPIRES'::timestamptz)
ON CONFLICT (token_hash) DO UPDATE SET is_active = true, expires_at = EXCLUDED.expires_at;
SQL

echo "OK: bootstrap token '$LABEL' active in DB; dev-bootstrap deactivated."
