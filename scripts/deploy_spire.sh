#!/usr/bin/env bash
# deploy_spire.sh — Start SPIRE server + orchestrator agent (Phase 1).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$REPO_ROOT/deploy/spire/docker-compose.spire.yml"

echo "=== Deploying SPIRE (trust domain: internalcmdb.local) ==="
docker compose -f "$COMPOSE_FILE" up -d

echo "Waiting for SPIRE health..."
sleep 10
docker compose -f "$COMPOSE_FILE" ps

echo "OK: SPIRE stack started. Next: issue join tokens per collector host (see F5-zero-trust-spiffe.md)."
