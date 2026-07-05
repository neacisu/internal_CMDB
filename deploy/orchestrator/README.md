# internalCMDB Orchestrator Deployment

Compose files and Traefik routing for the internalCMDB stack on the orchestrator host.

## Compose files

| File | Purpose |
|------|---------|
| `docker-compose.internalcmdb.yml` | Dev stack with hot-reload |
| `docker-compose.internalcmdb.prod.yml` | Production stack |
| `docker-compose.postgresql.yml` | PostgreSQL sidecar |

## Deploy

```bash
cd /opt/stacks/internalcmdb
docker compose -f deploy/orchestrator/docker-compose.internalcmdb.prod.yml up -d
```

## Image digest pinning (F5.5 — supply chain)

Production deployments should pin container images by **digest**, not mutable `:latest` tags.
This prevents silent supply-chain drift when a registry tag is overwritten.

### Resolve digests after CI build

```bash
API_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' \
  ghcr.io/alexneacsu/internalcmdb-api:${GIT_SHA})
FRONTEND_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' \
  ghcr.io/alexneacsu/internalcmdb-frontend:${GIT_SHA})
```

### Pin in compose override

Create `docker-compose.internalcmdb.prod.override.yml`:

```yaml
services:
  internalcmdb-api:
    image: ghcr.io/alexneacsu/internalcmdb-api@sha256:abc123...
  internalcmdb-frontend:
    image: ghcr.io/alexneacsu/internalcmdb-frontend@sha256:def456...
```

Deploy with both files:

```bash
docker compose \
  -f deploy/orchestrator/docker-compose.internalcmdb.prod.yml \
  -f deploy/orchestrator/docker-compose.internalcmdb.prod.override.yml \
  up -d
```

### Verification workflow

1. CI generates SBOM via `.github/workflows/sbom.yml` (Syft CycloneDX).
2. After cosign key setup, uncomment verify steps in `.github/workflows/cd.yml`.
3. Record pinned digests in deployment notes for audit trail.

## Related

- SPIRE workload identity: `deploy/spire/docker-compose.spire.yml`
- Traefik routes: `cmdb-api.yml`, `internalcmdb.yml`
