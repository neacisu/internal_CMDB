# Zero-trust rollout status — 2026-07-05 (updated)

## Fleet token_hash — COMPLETE

| Metric | Value |
|---|---|
| Active agents | 24 |
| With per-agent token (`token_hash`) | **24** |
| Legacy (NULL token_hash) | **0** |

### Final actions

| host_code | Action |
|---|---|
| `Alexs-iMac` | API re-enroll (SSH unreachable from orchestrator) |
| `lxc-neanelu-staging` | Disk cleanup (docker logs + journal) + deploy; enroll 201 |

## Completed

- `ALLOW_LEGACY_AGENT_HMAC=false` on dev API (post 24/24)
- Bootstrap prod active; dev bootstrap deactivated (0024)
- Redis prefix `infraq:*`; fail-closed lockout/revocation
- Agent daemon bootstrap + credentials persistence fleet-wide

## Remaining infra

| Item | Status |
|---|---|
| Redis | Restarted; may take minutes to finish LOADING (large RDB + RediSearch) |
| SPIRE | k8sbundle plugin removed from server.conf; redeploy pending |
| Prod cutover | Run `./scripts/cutover_prod.sh` when Redis healthy + OpenBao ready |
