---
id: RB-COGNITIVE-003
title: Event Bus Lag Runbook Procedure
doc_class: runbook
domain: infrastructure
version: "1.0"
status: draft
created: 2026-03-22
updated: 2026-03-23
owner: sre_observability_owner
binding:
  - entity_type: registry.service
    entity_id: event-bus
    relation: describes
---

# RB-COGNITIVE-003 — Event Bus Lag

## Problem

Redis Streams consumer groups are falling behind — events are produced
faster than consumers can process them, causing growing backlog (lag)
in one or more streams.

## Symptoms

- Prometheus metric `redis_stream_lag` > 1000 for any stream
- Delayed anomaly detection (events arrive minutes after collection)
- API response for `/metrics/fleet/matrix` shows stale timestamps
- Redis `XINFO GROUPS <stream>` shows high `pending` count
- Agent logs show normal ingestion but cognitive insights are delayed

## Impact

- **Medium** — Real-time alerting degrades to near-real-time or batch.
- Anomaly detection may miss transient spikes.
- HITL items are submitted with stale context.

## Steps to Resolve

1. **Identify the lagging stream:**
   ```bash
   ssh orchestrator 'docker exec internalcmdb-redis redis-cli XINFO GROUPS sensor:ingest'
   ssh orchestrator 'docker exec internalcmdb-redis redis-cli XINFO GROUPS cortex:anomaly'
   ```

2. **Check consumer health:**
   ```bash
   # List consumers in the group
   ssh orchestrator 'docker exec internalcmdb-redis redis-cli \
     XINFO CONSUMERS sensor:ingest sensor:ingest:default'
   ```

3. **Check if consumers are running:**
   ```bash
   ssh orchestrator 'docker ps | grep worker'
   ssh orchestrator 'docker logs internalcmdb-worker --tail 50'
   ```

4. **Clear stale pending entries (if consumers crashed):**
   ```bash
   # Claim old messages (idle > 300000ms = 5min)
   ssh orchestrator 'docker exec internalcmdb-redis redis-cli \
     XAUTOCLAIM sensor:ingest sensor:ingest:default recovery-consumer 300000 0-0'
   ```

5. **Restart the worker if needed:**
   ```bash
   ssh orchestrator 'docker restart internalcmdb-worker'
   ```

6. **Trim stream if excessively long (emergency only):**
   ```bash
   # Keep last 100,000 messages
   ssh orchestrator 'docker exec internalcmdb-redis redis-cli \
     XTRIM sensor:ingest MAXLEN ~ 100000'
   ```

## Prevention

- Set `MAXLEN ~ 500000` on all streams to prevent unbounded growth
- Monitor `redis_stream_lag` with alerting at 500 and 1000 thresholds
- Scale consumer workers horizontally for high-throughput streams
- Implement dead-letter queue for messages that fail processing 3 times
