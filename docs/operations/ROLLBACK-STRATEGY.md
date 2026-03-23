# Rollback Strategy

Per-component rollback procedures for the internalCMDB stack.

---

## 1. API Docker Container

**Trigger:** Health check failure after deploy, HTTP 5xx spike, unresponsive API.

### Automated (CD Pipeline)

The CD pipeline automatically rolls back when `/health` fails within 30s:

```bash
docker tag "$PREV_IMAGE" ghcr.io/alexneacsu/internalcmdb-api:latest
docker compose -f $COMPOSE_FILE up -d
```

### Manual

```bash
# List recent images
docker images ghcr.io/alexneacsu/internalcmdb-api --format "{{.Tag}} {{.CreatedAt}}"

# Roll back to previous tag
docker tag ghcr.io/alexneacsu/internalcmdb-api:<previous-sha> \
           ghcr.io/alexneacsu/internalcmdb-api:latest

docker compose -f deploy/orchestrator/docker-compose.internalcmdb.yml up -d --no-deps internalcmdb-api
```

### Verification

```bash
curl -sf https://infraq.app/health | jq .
docker logs internalcmdb-api --tail 50
```

---

## 2. Alembic Migrations

**Trigger:** Migration introduces schema errors, data corruption, or performance regression.

### Downgrade

```bash
# Check current revision
alembic -c alembic.ini current

# Downgrade one step
alembic -c alembic.ini downgrade -1

# Downgrade to specific revision
alembic -c alembic.ini downgrade <revision>
```

### Pre-flight Check

Always run `make migrate-check` before applying migrations in production.
This generates the SQL and scans for destructive operations (DROP TABLE/COLUMN).

### Point-in-time Recovery (PITR)

For catastrophic data loss, restore from the PostgreSQL WAL archive:

```bash
# On postgres-main:
pg_restore -d internalCMDB /backup/internalcmdb_$(date +%Y%m%d).dump
```

---

## 3. Agent Binary

**Trigger:** Agent crash loop, telemetry ingestion failure, version incompatibility.

### Auto-rollback

The `AgentUpdater` automatically restores from `/opt/internalcmdb/agent.bak/`
when an update fails verification or crashes on startup.

### Manual

```bash
# On the affected host:
systemctl stop internalcmdb-agent

# Restore backup
rm -rf /opt/internalcmdb/agent
cp -r /opt/internalcmdb/agent.bak /opt/internalcmdb/agent

systemctl start internalcmdb-agent
systemctl status internalcmdb-agent
```

### Redeploy from Orchestrator

```bash
./scripts/deploy_agent.sh <host_code>
```

---

## 4. Prometheus Configs

**Trigger:** Scrape failures, missing metrics, alert rule errors.

### Rollback

Prometheus configs are version-controlled. Restore from git:

```bash
# On orchestrator:
cd /opt/stacks/internalcmdb
git checkout HEAD~1 -- deploy/observability/prometheus/
docker compose -f deploy/orchestrator/docker-compose.internalcmdb.yml restart prometheus
```

### Validate Before Apply

```bash
# Check config syntax
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml

# Check rule files
docker exec prometheus promtool check rules /etc/prometheus/rules/*.yml
```

---

## 5. Frontend Container

**Trigger:** Frontend blank page, JavaScript errors, Next.js 500s.

### Rollback

```bash
# List recent images
docker images ghcr.io/alexneacsu/internalcmdb-frontend --format "{{.Tag}} {{.CreatedAt}}"

# Roll back to previous tag
docker tag ghcr.io/alexneacsu/internalcmdb-frontend:<previous-sha> \
           ghcr.io/alexneacsu/internalcmdb-frontend:latest

docker compose -f deploy/orchestrator/docker-compose.internalcmdb.yml up -d --no-deps internalcmdb-frontend
```

### Verification

```bash
curl -sf https://infraq.app/ | head -20
docker logs internalcmdb-frontend --tail 50
```

---

## 6. Worker Process

**Trigger:** ARQ jobs stuck, cognitive pipeline halted, queue growing.

### Rollback

The worker uses the same image as the API. Rollback follows the API procedure
above — both containers restart with the same image.

```bash
docker compose -f deploy/orchestrator/docker-compose.internalcmdb.yml \
  up -d --no-deps internalcmdb-worker
```

### Verification

```bash
docker logs internalcmdb-worker --tail 50
# Check Redis queue draining
ssh orchestrator 'docker exec internalcmdb-redis redis-cli LLEN arq:queue:default'
```

---

## General Principles

1. **Always validate before deploy:** `make check` + `make migrate-check`
2. **Keep previous images:** Never prune Docker images on the same day as deploy
3. **Monitor after rollback:** Watch `/health`, Prometheus dashboards, and agent heartbeats for 15 minutes
4. **Document the incident:** Create a post-mortem if the rollback was triggered by a production issue
5. **Test rollback procedures quarterly:** Verify that backups and rollback paths work
