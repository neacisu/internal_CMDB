# Post-rollout monitoring (7 days)

| Metric | Command / source | Alert threshold |
|---|---|---|
| Legacy HMAC | `docker logs internalcmdb-api --since 24h 2>&1 \| grep -c 'Legacy HMAC'` | > 0 |
| token_hash NULL | SQL below | > 0 active agents |
| Redis NoPermission | `docker logs internalcmdb-api 2>&1 \| grep NoPermission` | any |
| Bootstrap expiry | SQL below | < 14 days |
| Agent stale | SQL below | last_seen > 5 min |

## Daily SQL

```sql
SELECT
  count(*) FILTER (WHERE token_hash IS NOT NULL AND is_active) AS with_token,
  count(*) FILTER (WHERE token_hash IS NULL AND is_active) AS legacy
FROM discovery.collector_agent;

SELECT label, expires_at FROM discovery.bootstrap_tokens WHERE is_active;

SELECT host_code, agent_id, last_seen_at
FROM discovery.collector_agent
WHERE is_active AND last_seen_at < now() - interval '5 minutes'
ORDER BY last_seen_at;
```

## Cron example (orchestrator)

```bash
0 8 * * * /opt/stacks/internalcmdb/scripts/monitor_rollout.sh >> /var/log/internalcmdb-rollout-monitor.log 2>&1
```
