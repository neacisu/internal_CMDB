---
id: RB-COGNITIVE-005
title: Cognitive Job Failure Runbook Procedure
doc_class: runbook
domain: infrastructure
version: "1.0"
status: draft
created: 2026-03-22
updated: 2026-03-23
owner: sre_observability_owner
binding:
  - entity_type: registry.service
    entity_id: cognitive-pipeline
    relation: describes
---

# RB-COGNITIVE-005 — Cognitive Job Failure

## Problem

Scheduled cognitive analysis jobs (anomaly detection, drift analysis,
insight generation) are failing or not producing results.

## Symptoms

- No new insights appearing in `/cognitive/insights` for > 1 hour
- ARQ worker logs show job failures or timeouts
- Prometheus alert `CognitiveJobFailureRate > 0.1` firing
- `cognitive_tasks` worker shows `status: failed` in queue
- Fleet health score stale (not updated by cognitive analysis)

## Impact

- **Medium** — Proactive anomaly detection stops; drift goes unnoticed.
- HITL queue stops receiving new items from the cognitive pipeline.
- Health scores become stale and may show false-positive "healthy" status.

## Steps to Resolve

1. **Check worker status:**
   ```bash
   ssh orchestrator 'docker logs internalcmdb-worker --tail 100 2>&1 | grep -i error'
   ```

2. **Check Redis queue state:**
   ```bash
   ssh orchestrator 'docker exec internalcmdb-redis redis-cli \
     LLEN arq:queue:default'
   ssh orchestrator 'docker exec internalcmdb-redis redis-cli \
     LLEN arq:queue:default:failed'
   ```

3. **Check for database connection issues:**
   ```bash
   ssh postgres-main 'pg_isready -h localhost -p 5433 -d internalCMDB'
   ```

4. **Restart the worker:**
   ```bash
   ssh orchestrator 'docker restart internalcmdb-worker'
   ```

5. **Re-queue failed jobs (if needed):**
   ```bash
   # Via the API
   curl -X POST https://infraq.app/api/v1/workers/retry-failed
   ```

6. **Check for LLM backend dependency:**
   - Cognitive analysis requires LLM backends (reasoning/fast).
   - If LLM is down, see RB-COGNITIVE-001.
   - Jobs may fail with `httpx.ConnectError` or `httpx.ReadTimeout`.

7. **Check memory / disk on orchestrator:**
   ```bash
   ssh orchestrator 'free -h && df -h /var/lib/docker'
   ```

## Prevention

- Set up dead-letter queue monitoring for failed ARQ jobs
- Configure job timeout to 5 minutes (prevent hung workers)
- Monitor worker container restarts in Prometheus
- Ensure cognitive jobs have circuit breaker protection for LLM calls
- Run `make test` before deploying changes to cognitive modules
