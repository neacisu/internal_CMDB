---
id: REL-002
title: internalCMDB — Rollback Contracts and Migration Recovery Drills (Wave-1)
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [rollback, migration, recovery, drills, wave-1, m11-2]
depends_on: [REL-001, CONT-002]
---

# internalCMDB — Rollback Contracts and Migration Recovery Drills

## 1. Purpose

Rollback playbooks and exercised migration recovery procedures for database-bearing changes.
Satisfies pt-035 [m11-2].

---

## 2. Rollback Contract

Every release promoted to wave-1-production must have a documented rollback path before promotion.

| Component | Rollback Scope | Rollback Reversibility |
| --- | --- | --- |
| Application code (Docker image) | Roll back Docker Compose service to previous image tag | Fully reversible: re-tag previous image and restart |
| Database schema migration | Alembic downgrade to previous revision | Reversible if downgrade script exists; data loss possible if columns dropped |
| Configuration files | Restore from Git previous commit | Fully reversible |
| Docker Compose configuration | Restore from Git previous commit | Fully reversible |

---

## 3. Application Rollback Procedure

```bash
# Step 1: Identify previous image tag
docker images internalcmdb-app --format "{{.Tag}}" | head -5

# Step 2: Stop current service
docker compose stop internalcmdb-app

# Step 3: Update compose to previous tag (or use --scale)
# Edit INTERNALCMDB_APP_TAG in .env.prod to previous version

# Step 4: Restart
docker compose up -d internalcmdb-app

# Step 5: Verify health
docker logs internalcmdb-app 2>&1 | tail -20
curl -sf http://localhost:8080/health | python3 -m json.tool

# Step 6: Record rollback in governance.change_log
```

---

## 4. Database Migration Rollback Procedure

```bash
# Step 1: Check current Alembic revision
PGPASSWORD="${DB_PASSWORD}" psql -U internalcmdb_app -d internalcmdb -c "SELECT version_num FROM alembic_version;"

# Step 2: List available downgrades
PYTHONPATH=src .venv/bin/python3 -m alembic history

# Step 3: Downgrade one revision
PYTHONPATH=src .venv/bin/python3 -m alembic downgrade -1

# Step 4: Verify schema state
PYTHONPATH=src .venv/bin/python3 -m alembic current

# Step 5: Restart application to use downgraded schema
docker compose restart internalcmdb-app

# Step 6: Record in governance.change_log with change_type=migration_rollback
```

**Warning**: Downgrade scripts must be reviewed before production migration. If a migration adds a NOT NULL column, downgrade may require data preservation.

---

## 5. Migration Recovery Drill Record

**Drill 1 — Wave-1 Pre-Production Exercise (2026-03-08)**

| Step | Outcome | Notes |
| --- | --- | --- |
| Simulated forward migration (add column) | PASS | Column added, data preserved |
| Applied downgrade script (-1 revision) | PASS | Column removed, no data loss (nullable) |
| Application restarted against downgraded schema | PASS | No ORM mapping errors |
| Verified row counts pre/post | PASS | No data loss |
| Record in change_log | DONE | change_type=migration_rollback_drill |

**Outcome**: Downgrade path exercised under drill conditions. No ad-hoc invention required.

---

## 6. Drill Schedule

| Drill Type | Frequency | Responsible |
| --- | --- | --- |
| Application rollback (image swap) | Per release cycle before production | platform_architecture_lead |
| Database migration downgrade | Per schema migration before production | platform_architecture_lead |
| Full DR (container loss) | Quarterly — see CONT-003 | platform_architecture_lead |

---

## 7. Verification

- [x] Rollback procedure for application code is documented and executable.
- [x] Rollback procedure for database migration is documented and executable.
- [x] At least one migration recovery drill has been executed (§5).
- [x] Drill can be followed without ad-hoc invention.
- [x] Drill outcomes recorded in governance.change_log.
