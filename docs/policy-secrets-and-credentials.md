---
id: POL-002
title: internalCMDB — Secrets, Credentials & Trust Policy
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: security_and_policy_owner
tags: [policy, secrets, credentials, trust, wave-1]
---

# internalCMDB — Secrets, Credentials & Trust Policy

**Version**: 1.0
**Date**: 2026-03-08
**Owner**: Alex Neacsu (Security & Policy Owner)
**Status**: Approved (Wave-1 posture)

---

## 1. Scope

This policy covers all credentials, secrets, and trust relationships used by
the internalCMDB platform and its associated audit tooling.

---

## 2. Credential Inventory

| Secret | Purpose | Storage | Rotation |
|--------|---------|---------|----------|
| `POSTGRES_PASSWORD` | internalCMDB DB access | Local `.env` (gitignored) + `~/internalcmdb/.env` on orchestrator | Manual; rotate before any external operator access |
| SSH keys (cluster) | Audit host access | `~/.ssh/` on local Mac | Managed by `cluster-key-mesh` subproject |
| Cloudflare DNS API token | Traefik ACME DNS challenge for `*.neanelu.ro`, `*.orchestrator.neanelu.ro` | Traefik docker-compose env var on orchestrator | Rotate on compromise; review every 90 days |
| Zitadel OIDC credentials | CloudBeaver oauth2-proxy | Zitadel (pa55words.neanelu.ro) | Managed by Identity Provider |
| OpenBao paths | Future secrets engine integration | `s3cr3ts.neanelu.ro` | Per vault policy |

---

## 3. Rules

### 3.1 No Secrets in Version Control

- `.env` files MUST be listed in `.gitignore` and MUST NOT be committed.
- Any accidental commit requires immediate rotation of the affected secret.
- `pyproject.toml`, migration files, and loader code MUST NOT contain credentials.

### 3.2 Transport Security

- Database connections MUST use `sslmode=require` (or higher) when connecting
  via `postgres.orchestrator.neanelu.ro:5432`.
- The TLS certificate is issued by Let's Encrypt via Cloudflare DNS-01 challenge
  and is managed by Traefik. The ALPN extension `"postgresql"` is accepted per
  `/opt/traefik/dynamic/postgres.yml`.
- Connections from within the orchestrator host to `127.0.0.1:5433` (container)
  are plaintext but are loopback-only and acceptable per Wave-1 posture.

### 3.3 Least Privilege

- The `internalcmdb` PostgreSQL role has access ONLY to the `internalCMDB`
  database. It has no superuser, replication, or `pg_hba` modification rights.
- Audit loaders run with the `internalcmdb` role. They do NOT require `SUPERUSER`.
- Discovery results (`current.json` files) are read-only inputs; loaders do NOT
  write back to the host being audited.

### 3.4 Credential Rotation Procedure

1. Generate a new password (min 32 chars, cryptographically random).
2. Update `~/internalcmdb/.env` on orchestrator.
3. Update local `.env`.
4. Update the Zitadel / OpenBao vault record if applicable.
5. Run `psql ALTER ROLE internalcmdb PASSWORD 'newpassword'` against PostgreSQL.
6. Verify connection: `alembic upgrade head` (no-op if at head).
7. Document rotation in the log below.

---

## 4. Trust Boundaries

```
[Local Mac]
    │ sslmode=require, TLS + ALPN=postgresql
    ▼
[Traefik :5432 on orchestrator]   ← cert from Cloudflare ACME
    │ loopback plaintext
    ▼
[internalcmdb-postgres :5432]     ← password auth, pg_hba: md5
    │ PGDATA on HC_Volume_105014654
    ▼
[PostgreSQL 17 data files]
```

The audit loaders connect to the database from the local Mac over the public
internet via HTTPS/TLS. The SSH audit loaders connect to cluster hosts via SSH
(key-based, no password). No plain-text credentials traverse the network.

---

## 5. Compliance Notes

- **Bootstrap credentials** (initial `internalcmdb` password set at `docker compose up`)
  are rotated after first successful connection.
- **External-postgres path**: the Traefik TCP routing provides TLS for the
  external postgres path as required by epic-9 (`external-postgres-and-broker-paths-require-explicit-tls-and-trust-handling`).
- **Secret rotation alignment**: rotation must align with role-bound access;
  see epic-9 `secret-rotation-must-align-with-role-bound-access-and-audit-controls`.

---

## 6. Credential Rotation Log

| Date       | Secret Rotated | Reason | Operator |
|------------|----------------|--------|----------|
| 2026-03-08 | Initial setup  | First deployment | Alex Neacsu |

---

*Generated: 2026-03-08 | Approved: Alex Neacsu | Review date: 2026-06-08*
