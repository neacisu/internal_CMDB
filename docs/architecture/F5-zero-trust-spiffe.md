# F5.1 — Zero-Trust Workload Identity (SPIFFE/SPIRE)

## Overview

internalCMDB collectors and API workers will authenticate to each other using
SPIFFE IDs and mTLS rather than long-lived shared secrets alone.  This document
describes the integration plan; runtime enforcement is staged behind feature
flags until SPIRE is deployed fleet-wide.

## Trust domain

| Property | Value |
|----------|-------|
| Trust domain | `internalcmdb.local` |
| SPIRE version | 1.15.1 |
| Compose file | `deploy/spire/docker-compose.spire.yml` |
| Validation stub | `src/internalcmdb/auth/spiffe.py` |

## SPIFFE ID scheme

```
spiffe://internalcmdb.local/<component>/<host_code>
```

Examples:

- `spiffe://internalcmdb.local/collector/hz-223`
- `spiffe://internalcmdb.local/api/orchestrator`
- `spiffe://internalcmdb.local/worker/cognitive`

## Integration phases

### Phase 1 — SPIRE deployment (current scaffolding)

1. Start SPIRE server + agent via `docker-compose.spire.yml`.
2. Register collector nodes with join tokens; issue X509-SVIDs per host.
3. Mount agent socket (`/tmp/spire-agent/public/api.sock`) into collector containers.

### Phase 2 — Agent mTLS to API

1. Configure Traefik / HAProxy to require client certificates signed by the SPIRE CA.
2. Collectors present X509-SVID during TLS handshake to `/api/v1/collectors/*`.
3. API middleware extracts SPIFFE ID from cert SAN and maps to `discovery.collector_agent`.

### Phase 3 — JWT-SVID for service-to-service

1. Workloads fetch JWT-SVIDs via SPIRE agent API (`/api/v1/agent/fetch_jwt_svid`).
2. API validates JWT-SVID using `SpiffeJwtValidator` (see `auth/spiffe.py`).
3. JWT audience: `internalcmdb-api`; issuer: SPIRE OIDC discovery endpoint.

## API middleware plan

```
Request
  │
  ├─► Existing JWT auth (human users)
  │
  └─► SPIFFE middleware (agents)
        ├─ Extract SPIFFE ID from client cert or JWT-SVID
        ├─ SpiffeJwtValidator.validate(token)  [Phase 3]
        └─ Map spiffe_id → collector_agent row
```

Fail-closed: if SPIFFE validation is enabled (`SPIFFE_AUTH_ENABLED=true`) and
validation fails, return `401` — no fallback to bootstrap tokens.

## Configuration

| Env var | Purpose |
|---------|---------|
| `SPIFFE_AUTH_ENABLED` | Enable SPIFFE/JWT-SVID gate (default `false`) |
| `SPIFFE_TRUST_DOMAIN` | Trust domain (default `internalcmdb.local`) |
| `SPIRE_AGENT_SOCKET` | Agent socket path for local SVID fetch |
| `SPIFFE_JWKS_URL` | JWKS endpoint for JWT-SVID verification |

## Rollout checklist

- [ ] Deploy SPIRE server with persistent datastore (PostgreSQL in production)
- [ ] Issue join tokens per collector host; rotate quarterly
- [ ] Enable mTLS on collector → API path in staging
- [ ] Wire `SpiffeJwtValidator` into `global_auth` middleware
- [ ] Deprecate bootstrap tokens after 100% SPIFFE enrollment

## References

- [SPIRE documentation](https://spiffe.io/docs/latest/spire-about/)
- [SPIFFE JWT-SVID spec](https://github.com/spiffe/spiffe/blob/main/standards/JWT-SVID.md)
- Collector auth: `src/internalcmdb/collectors/agent_auth.py`
- Bootstrap tokens migration: `0020_agent_token_bootstrap.py`
