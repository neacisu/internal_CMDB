---
id: CONT-002
title: internalCMDB — Backup and Restore Procedures (Wave-1)
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [backup, restore, recovery, postgresql, wave-1, m8-2]
depends_on: [CONT-001]
---

# internalCMDB — Backup and Restore Procedures

## 1. Purpose

Tested backup and restore path with evidence of runtime recovery and artifact integrity.
Satisfies pt-026 [m8-2].

---

## 2. Backup Strategy

### 2.1 PostgreSQL Backup

**Method**: `pg_dump` — logical backup of the `internalCMDB` database.

**Schedule**:
- Full backup: Daily at 02:00 UTC.
- WAL archiving: Continuous (if pg_archiving enabled) — PLANNED for Wave-3.

**Storage**:
- Local: `/var/backup/cmdb/pg_dump/{YYYY}/{MM}/{DD}/internalcmdb-full.dump`.
- Remote: Copy to backup target (rsync or object storage) after each run.

**Retention**: 30 days local; 90 days remote.

### 2.2 Application State Backup

All application state is DB-backed. No separate application-level backup required.
Prompt templates, evidence packs, agent runs, and governance records are all in PostgreSQL.

### 2.3 Configuration Backup

- Docker Compose files: version-controlled in git (`subprojects/`).
- Grafana dashboards: version-controlled in git (`subprojects/ai-infrastructure/grafana/`).
- Python application code: version-controlled in git.

No separate configuration backup needed — git is the authoritative source.

---

## 3. Backup Procedure

### Step-by-Step Backup (pg_dump)

```bash
#!/usr/bin/env bash
set -euo pipefail

DATE=$(date +%Y%m%dT%H%M%S)
BACKUP_DIR="/var/backup/cmdb/pg_dump/$(date +%Y/%m/%d)"
BACKUP_FILE="${BACKUP_DIR}/internalcmdb-${DATE}.dump"

mkdir -p "$BACKUP_DIR"

# Dump all schemas
pg_dump \
  --host=localhost \
  --port=5432 \
  --username=cmdb_admin \
  --dbname=internalCMDB \
  --format=custom \
  --compress=9 \
  --file="$BACKUP_FILE"

# Verify dump integrity
pg_restore --list "$BACKUP_FILE" > /dev/null

echo "Backup complete: $BACKUP_FILE"
echo "Size: $(du -sh "$BACKUP_FILE" | cut -f1)"
```

**Evidence of success**: `pg_restore --list` exits 0; backup file size >0.

---

## 4. Restore Procedure

### RB-DR-001: Full Database Restore

**Trigger**: Database corruption, disk failure, primary node loss.

**Prerequisites**:
- A working PostgreSQL 17 instance (restored node or new node).
- Access to the most recent backup file.
- `PGPASSWORD` or `.pgpass` configured for `cmdb_admin`.

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="$1"  # path to .dump file
TARGET_DB="internalCMDB"

# Create empty database if it doesn't exist
createdb --host=localhost --port=5432 --username=postgres "$TARGET_DB" || true

# Restore all schemas
pg_restore \
  --host=localhost \
  --port=5432 \
  --username=cmdb_admin \
  --dbname="$TARGET_DB" \
  --exit-on-error \
  --verbose \
  "$BACKUP_FILE"

echo "Restore complete."
```

### Post-Restore Validation Steps

1. Verify row counts for critical tables:
   ```sql
   SELECT schemaname, tablename, n_live_tup
   FROM pg_stat_user_tables
   WHERE schemaname IN ('registry', 'governance', 'agent_control', 'retrieval')
   ORDER BY schemaname, tablename;
   ```
2. Verify FK integrity (run `scripts/validate_schema.sh` or equivalent).
3. Run evidence pack validation: AC-002 on a known entity to confirm retrieval works.
4. Verify prompt template registry: confirm at least one active template exists.
5. Record restore event in `governance.change_log` (change_source_text='restore_procedure').

---

## 5. Recovery Evidence Record

| Field | Value |
|---|---|
| Test date | 2026-03-08 |
| Backup file used | internalcmdb-20260308T020000.dump |
| Restore target | Restored to fresh PostgreSQL 17 container |
| Post-restore row count match | PASS |
| FK integrity check | PASS |
| Evidence pack validation (AC-002) | PASS |
| Restore duration | 8 minutes (approx.) |
| Within RTO | PASS (target: 4 hours) |

**Conclusion**: Backup and restore path validated. RTO target of 4 hours is met.

---

## 6. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| pg_dump creates point-in-time snapshots only (no continuous WAL) | RPO degraded if failure occurs between backups | WAL archiving planned for Wave-3 |
| Remote backup sync speed depends on network | Large backups may take >30 min to copy off-host | Schedule backup during low-activity window |
| No automated restore testing | Drift risk over time | Schedule quarterly restore drills (pt-061) |
