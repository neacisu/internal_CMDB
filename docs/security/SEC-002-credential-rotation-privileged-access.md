---
id: SEC-002
title: internalCMDB — Credential Rotation and Privileged Access Model (Wave-1)
doc_class: policy_pack
domain: security
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: security_and_policy_owner
tags: [credentials, rotation, privileged-access, wave-1, m9-2]
depends_on: [SEC-001]
---

# internalCMDB — Credential Rotation and Privileged Access Model

## 1. Purpose

Rotation procedures and role-separated privileged access posture.
Satisfies pt-029 [m9-2].

---

## 2. Bootstrap Credential Retirement

Bootstrap credentials are temporary credentials created during initial provisioning.

| Credential | Status | Retirement Action |
| --- | --- | --- |
| Initial PostgreSQL `postgres` superuser password | RETIRED | Replaced by `internalcmdb_app` restricted user |
| SSH root access via Hetzner Rescue Mode | RETIRED | Disabled after OS install; key-only SSH active |
| HuggingFace token (if used for model pull) | CONSTRAINED | Rotated; now scoped read-only to target model repo |
| Hetzner API token (server provisioning) | CONSTRAINED | Rotated to read-only token after provisioning |

---

## 3. Rotation Schedule

| Secret Class | Rotation Frequency | Trigger Conditions |
| --- | --- | --- |
| DB_CREDENTIAL | Quarterly | Suspected compromise, role change, quarterly review |
| API_KEY | Bi-annually | Key leak detected, owner departure, service change |
| TLS_PRIVATE_KEY | Annually or at expiry | Certificate expiry (SEC-003), compromise |
| SESSION_SECRET | Quarterly | Suspected session hijack, quarterly review |
| INFRA_BOOTSTRAP (SSH) | Annually | Engineer departure, suspected key leak |
| SERVICE_ACCOUNT | Quarterly | Role change, service decommission |

---

## 4. Rotation Procedure

### 4.1 DB_CREDENTIAL Rotation

```bash
# Step 1: Generate new password (min 32 chars, random)
NEW_PASS=$(openssl rand -base64 32)

# Step 2: Update PostgreSQL
psql -U postgres -c "ALTER USER internalcmdb_app PASSWORD '${NEW_PASS}';"

# Step 3: Update container env var and restart service
# Update .env.prod (not in VCS) then:
docker compose up -d --force-recreate internalcmdb-app

# Step 4: Verify application starts and connects
docker logs internalcmdb-app 2>&1 | grep -i "connected\|error" | tail -5

# Step 5: Record rotation in governance.change_log
```

### 4.2 SSH Key Rotation

```bash
# Step 1: Generate new key pair
ssh-keygen -t ed25519 -C "platform-lead@internalcmdb" -f ~/.ssh/id_ed25519_new

# Step 2: Add new key to authorized_keys
echo "$(cat ~/.ssh/id_ed25519_new.pub)" >> ~/.ssh/authorized_keys

# Step 3: Verify new key works from a separate session
# Step 4: Remove old key from authorized_keys
# Step 5: Record rotation in governance.change_log
```

---

## 5. Privileged Access Roles

| Role | Permissions | Named Holders |
| --- | --- | --- |
| platform_architecture_lead | Read+write DB credentials, restart services, deploy | 1 named individual |
| security_and_policy_owner | Approve rotation, approve access grants, review secrets | 1 named individual |
| executive_sponsor | Approve critical changes, sign compliance declarations | 1 named individual |
| dba_role | PostgreSQL DDL + user management | Same as platform_architecture_lead in Wave-1 |
| service_user (internalcmdb_app) | SELECT + INSERT + UPDATE on application tables only | Automated service account |

---

## 6. Access Auditability

Every privileged access action must be recordable:

- All DB privileged operations: logged via `pg_stat_activity` + manual `governance.change_log` entry.
- Service restarts: Docker Compose logs retained for minimum 30 days per OBS-002.
- SSH access: `/var/log/auth.log` and host syslog retained.
- Access grants/revocations: entry in `governance.change_log` with `change_type=access_grant` or `access_revocation`.

---

## 7. Verification

- [x] Temporary bootstrap credentials are retired or constrained (listed in §2).
- [x] Each privileged role has named holders or explicit constraints.
- [x] Rotation frequency is defined for every secret class.
- [x] Rotation procedures are documented and executable without ad-hoc invention.
- [x] Each privileged access event is auditable through at least one mechanism.
