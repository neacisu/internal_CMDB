#!/usr/bin/env bash
# cutover_prod.sh — Switch internalCMDB from dev to production compose.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$REPO_ROOT/deploy/orchestrator"
DEV="$COMPOSE_DIR/docker-compose.internalcmdb.yml"
PROD="$COMPOSE_DIR/docker-compose.internalcmdb.prod.yml"

echo "=== Pre-cutover checks ==="
if [[ ! -f /run/secrets/bao_secret_id ]]; then
    echo "WARN: /run/secrets/bao_secret_id missing — OpenBao AppRole may fail" >&2
fi

docker exec internalcmdb-api python -c "
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
load_dotenv('/opt/stacks/internalcmdb/.env')
e = create_engine(f\"postgresql+psycopg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@127.0.0.1:5433/{os.environ['POSTGRES_DB']}\")
with e.connect() as c:
    leg = c.execute(text('SELECT count(*) FROM discovery.collector_agent WHERE is_active AND token_hash IS NULL')).scalar()
    if leg:
        raise SystemExit(f'BLOCK: {leg} agents still on legacy (token_hash NULL)')
print('OK: all active agents have token_hash')
" || { echo "Aborting cutover — re-enroll remaining agents first"; exit 1; }

echo "=== Cutover to production compose ==="
docker compose -f "$DEV" down
docker compose -f "$PROD" up -d --build
sleep 15
docker exec internalcmdb-api alembic upgrade head
curl -sf https://infraq.app/health | head -c 100
echo ""
docker exec internalcmdb-api printenv ENV
echo "OK: production cutover complete"
