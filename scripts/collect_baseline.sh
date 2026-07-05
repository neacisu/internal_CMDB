#!/usr/bin/env bash
# collect_baseline.sh — F0 pre-flight inventory for zero-trust rollout.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
OUT_DIR="$REPO_ROOT/docs/rollout"
STAMP="$(date +%Y%m%d)"
OUT_FILE="$OUT_DIR/baseline-${STAMP}.txt"

mkdir -p "$OUT_DIR"

{
    echo "=== internalCMDB zero-trust baseline ${STAMP} ==="
    echo "Host: $(hostname)"
    echo "Date: $(date -Iseconds)"
    echo ""

    echo "=== Docker containers ==="
    docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null || echo "docker unavailable"
    echo ""

    echo "=== ENV (api) ==="
    docker exec internalcmdb-api printenv ENV 2>/dev/null || echo "internalcmdb-api not running"
    echo ""

    echo "=== Alembic ==="
    docker exec internalcmdb-api alembic current 2>/dev/null || echo "alembic unavailable"
    echo ""

    echo "=== Agent token stats ==="
    docker exec internalcmdb-api python -c "
from internalcmdb.api.deps import SessionLocal
from sqlalchemy import text
with SessionLocal() as db:
    r = db.execute(text(\"\"\"
        SELECT
          count(*) FILTER (WHERE is_active) AS active,
          count(*) FILTER (WHERE token_hash IS NOT NULL) AS with_token,
          count(*) FILTER (WHERE token_hash IS NULL AND is_active) AS legacy
        FROM discovery.collector_agent
    \"\"\")).one()
    print(dict(r._mapping))
" 2>/dev/null || echo "DB query unavailable"
    echo ""

    echo "=== Bootstrap tokens ==="
    docker exec internalcmdb-api python -c "
from internalcmdb.api.deps import SessionLocal
from sqlalchemy import text
with SessionLocal() as db:
    rows = db.execute(text('SELECT label, is_active, expires_at FROM discovery.bootstrap_tokens ORDER BY created_at')).all()
    for row in rows:
        print(row)
" 2>/dev/null || echo "bootstrap query unavailable"
    echo ""

    echo "=== Legacy HMAC count (5 min) ==="
    docker logs internalcmdb-api --since 5m 2>&1 | grep -c "Legacy HMAC" || true
    echo ""

    echo "=== TOML configs ==="
    ls -1 "$REPO_ROOT/deploy/configs/agents/"*.toml 2>/dev/null | wc -l
    echo ""

    echo "=== SSH aliases ==="
    grep -E '^Host ' "${HOME}/.ssh/config" 2>/dev/null | awk '{print $2}' | sort || echo "no ssh config"
} | tee "$OUT_FILE"

echo "Baseline written to $OUT_FILE"
