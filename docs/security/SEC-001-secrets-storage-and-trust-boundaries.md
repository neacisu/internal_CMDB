---
id: SEC-001
title: internalCMDB — Secrets Storage and Trust Boundary Model (Wave-1)
doc_class: policy_pack
domain: security
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: security_and_policy_owner
tags: [secrets, trust-boundaries, credentials, wave-1, m9-1]
---

# internalCMDB — Secrets Storage and Trust Boundary Model

## 1. Purpose

Approved model mapping every privileged secret class to an owner, storage boundary, and access rule.
Satisfies pt-028 [m9-1].

---

## 2. Secret Classes

| Secret Class | Examples | Sensitivity |
| --- | --- | --- |
| DB_CREDENTIAL | PostgreSQL user + password | HIGH |
| API_KEY | HuggingFace token, external API keys | HIGH |
| TLS_PRIVATE_KEY | Private keys for TLS endpoints | CRITICAL |
| SESSION_SECRET | App session signing keys | HIGH |
| INFRA_BOOTSTRAP | SSH keys, Hetzner API tokens | CRITICAL |
| SERVICE_ACCOUNT | Internal service-to-service tokens | MEDIUM |

---

## 3. Storage Boundary Rules

| Secret Class | Approved Storage | Prohibited Locations |
| --- | --- | --- |
| DB_CREDENTIAL | Environment variable at container start; `.env` file not committed to VCS | Source code, logs, CMDB registry tables |
| API_KEY | Environment variable or secrets manager | Source code, config files in VCS |
| TLS_PRIVATE_KEY | Host filesystem with mode 600; mounted read-only at container start | Container image layers, object storage |
| SESSION_SECRET | Environment variable | Source code, shared config files |
| INFRA_BOOTSTRAP | SSH agent forwarding or Hetzner Cloud console only | Git repos, chat/ticket systems |
| SERVICE_ACCOUNT | Environment variable set by orchestrator | Application code, database columns |

---

## 4. Access Rules per Secret Class

| Secret Class | Read Access | Write / Rotate Access |
| --- | --- | --- |
| DB_CREDENTIAL | Application service user only | platform_architecture_lead + DBA role required |
| API_KEY | Specific application process only | security_and_policy_owner approval required |
| TLS_PRIVATE_KEY | TLS termination process only | Certificate rotation procedure (SEC-003) |
| SESSION_SECRET | Application process only | platform_architecture_lead only |
| INFRA_BOOTSTRAP | Platform lead only | security_and_policy_owner + executive_sponsor approval |
| SERVICE_ACCOUNT | Named service only | platform_architecture_lead |

---

## 5. Trust Boundaries

```
[Public Internet]
      │
      ▼
[UFW / Host Firewall] ── blocks unauthorized ports
      │
      ▼
[Docker Network: internalcmdb_net]
      ├── internalcmdb-postgres  ── DB_CREDENTIAL (env var only)
      ├── internalcmdb-app       ── DB_CREDENTIAL + SESSION_SECRET (env var)
      └── [vSwitch / Private net] ── no DB credentials cross vSwitch boundary
```

**Trust Zones:**
- Zone A (Host OS): INFRA_BOOTSTRAP + TLS_PRIVATE_KEY — no container access
- Zone B (Docker network): DB_CREDENTIAL + SESSION_SECRET — container-scoped env vars
- Zone C (vSwitch): no secrets propagated — API endpoints only
- Zone D (Public internet): zero secret exposure — TLS-terminated endpoints

---

## 6. Prohibited Patterns

- Any secret class in Git history (enforced via `gitleaks` pre-push hook).
- Secrets logged in application stdout/stderr.
- DB_CREDENTIAL in CMDB `observed_fact` or `chunk_embedding` content.
- Hardcoded fallback secrets in application source.
- Shared accounts (each service uses a dedicated credential).

---

## 7. Verification Checklist

- [x] Every privileged secret class maps to a named owner.
- [x] Every secret class has an approved storage boundary.
- [x] Every secret class has an explicit access rule (read + write/rotate).
- [x] No secret class bypasses gitleaks pre-push enforcement.
- [x] Trust zones map to physical network layers without overlap.
