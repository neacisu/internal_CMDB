# Zero-trust rollout status — 2026-07-05

## Fleet token_hash

| Metric | Value |
|---|---|
| Active agents | 24 |
| With per-agent token (`token_hash`) | 22 |
| Legacy (NULL token_hash) | 2 |

### Remaining legacy agents

| host_code | Blocker |
|---|---|
| `Alexs-iMac` | SSH alias `imac` unreachable; use `Alexs-iMac.local` when on LAN |
| `lxc-neanelu-staging` | Disk full on host — free space then re-run `./scripts/deploy_agent.sh lxc-neanelu-staging` |

## Completed

- Migration `0024`: dev bootstrap deactivated
- Prod bootstrap: `prod-bootstrap-20260705` in DB; secret at `/run/secrets/bootstrap_enroll_token`
- Redis key prefix: `infraq:auth:*`, `infraq:agent:token:*`
- Agent daemon: `X-Bootstrap-Token`, credentials persistence, re-enroll on 401
- `ALLOW_LEGACY_AGENT_HMAC=true` on dev compose during transition (22/24 migrated)
- Prod compose: `ALLOW_LEGACY_AGENT_HMAC=false`, `ENV=production`
- Fail-closed lockout/revocation (no dev fail-open)
- SPIRE compose updated (ports 18080/18081); deploy blocked until port conflict resolved on orchestrator

## Next steps

1. Free disk on `lxc-neanelu-staging` and redeploy
2. Deploy `imac` when SSH reachable
3. When `token_hash` = 24/24: set `ALLOW_LEGACY_AGENT_HMAC=false` on dev API, run `./scripts/cutover_prod.sh`
4. Repair Redis AOF on `redis-shared` (still `BusyLoadingError` intermittently)
5. SPIRE: `./scripts/deploy_spire.sh` after port 8080 conflict resolved or use 18080 mapping
