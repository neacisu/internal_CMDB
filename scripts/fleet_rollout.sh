#!/usr/bin/env bash
# fleet_rollout.sh — Gradual re-enroll rollout for all agents.
#
# Usage:
#   ./scripts/fleet_rollout.sh canary <host_code>
#   ./scripts/fleet_rollout.sh batch
#   ./scripts/fleet_rollout.sh all
#
# Requires: /run/secrets/bootstrap_enroll_token, API with migration 0024 applied.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY="$REPO_ROOT/scripts/deploy_agent.sh"
MAP="$REPO_ROOT/docs/rollout/agent-host-map.csv"

CANARY_HOST="${CANARY_HOST:-lxc-llm-guard}"

verify_db_progress() {
    docker exec internalcmdb-api python -c "
from internalcmdb.api.deps import SessionLocal
from sqlalchemy import text
with SessionLocal() as db:
    r = db.execute(text('''
        SELECT
          count(*) FILTER (WHERE token_hash IS NOT NULL AND is_active) AS with_token,
          count(*) FILTER (WHERE token_hash IS NULL AND is_active) AS legacy
        FROM discovery.collector_agent
    ''')).one()
    print(f'with_token={r.with_token} legacy={r.legacy}')
" 2>/dev/null || echo "DB check unavailable"
}

verify_no_legacy_hmac() {
    local count
    count=$(docker logs internalcmdb-api --since 5m 2>&1 | grep -c "Legacy HMAC" || true)
    echo "Legacy HMAC (5m): $count"
}

case "${1:-}" in
    canary)
        HOST="${2:-$CANARY_HOST}"
        echo "=== Canary rollout: $HOST ==="
        "$DEPLOY" "$HOST"
        sleep 5
        verify_db_progress
        verify_no_legacy_hmac
        ;;
    batch)
        # First 5 from deploy script host list (excluding orchestrator)
        BATCH=(hz.62 hz.113 hz.118 hz.123 hz.157)
        for h in "${BATCH[@]}"; do
            echo "=== Batch host: $h ==="
            "$DEPLOY" "$h" || echo "WARN: failed $h"
            sleep 10
        done
        verify_db_progress
        ;;
    all)
        echo "=== Full fleet rollout ==="
        "$DEPLOY" all
        verify_db_progress
        verify_no_legacy_hmac
        ;;
    *)
        echo "Usage: $0 {canary [host]|batch|all}"
        exit 1
        ;;
esac
