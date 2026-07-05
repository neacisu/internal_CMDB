#!/usr/bin/env bash
# monitor_rollout.sh — Daily checks for zero-trust rollout health.
set -euo pipefail

echo "=== $(date -Iseconds) rollout monitor ==="

LEGACY_LOG=$(docker logs internalcmdb-api --since 24h 2>&1 | grep -c "Legacy HMAC" || true)
echo "Legacy HMAC (24h): $LEGACY_LOG"
if [[ "$LEGACY_LOG" -gt 0 ]]; then
    echo "ALERT: Legacy HMAC still present"
fi

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
    print('Agents with_token:', r.with_token, 'legacy:', r.legacy)
    if r.legacy and r.legacy > 0:
        print('ALERT: legacy agents remain')
    boots = db.execute(text(
        \"SELECT label, expires_at FROM discovery.bootstrap_tokens WHERE is_active\"
    )).all()
    for b in boots:
        print('Bootstrap:', b.label, 'expires', b.expires_at)
" 2>/dev/null || echo "WARN: could not query DB"

NOPERM=$(docker logs internalcmdb-api --since 24h 2>&1 | grep -c NoPermission || true)
echo "Redis NoPermission (24h): $NOPERM"
if [[ "$NOPERM" -gt 0 ]]; then
    echo "ALERT: Redis ACL errors"
fi
