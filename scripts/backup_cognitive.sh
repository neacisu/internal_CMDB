#!/usr/bin/env bash
# backup_cognitive.sh — pg_dump selective backup for telemetry, governance, and cognitive schemas.
#
# Usage:
#   ./scripts/backup_cognitive.sh [BACKUP_DIR] [KEEP_COUNT]
#
# Environment:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE — standard libpq variables
#   BACKUP_DIR — override via env or first argument  (default: /var/backups/internalcmdb)
#   KEEP_COUNT — number of backup sets to retain      (default: 7)

set -euo pipefail

BACKUP_DIR="${1:-${BACKUP_DIR:-/var/backups/internalcmdb}}"
KEEP_COUNT="${2:-${KEEP_COUNT:-7}}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SCHEMAS=("telemetry" "governance" "cognitive")
LOCK_FILE="${BACKUP_DIR}/.backup.lock"
MIN_FREE_MB="${MIN_FREE_MB:-1024}"

cleanup() {
    rm -f "${LOCK_FILE}"
    if [ -n "${_PARTIAL_FILE:-}" ] && [ -f "${_PARTIAL_FILE}" ]; then
        echo "  Cleaning up partial backup: ${_PARTIAL_FILE}"
        rm -f "${_PARTIAL_FILE}"
    fi
}
trap cleanup EXIT

mkdir -p "${BACKUP_DIR}"

# --- Concurrent run protection ---
if [ -f "${LOCK_FILE}" ]; then
    lock_pid="$(cat "${LOCK_FILE}" 2>/dev/null || true)"
    if [ -n "${lock_pid}" ] && kill -0 "${lock_pid}" 2>/dev/null; then
        echo "[$(date -Iseconds)] ERROR: Another backup is running (PID ${lock_pid}). Exiting."
        exit 1
    fi
    echo "[$(date -Iseconds)] WARN: Stale lock file found (PID ${lock_pid} not running). Removing."
    rm -f "${LOCK_FILE}"
fi
echo $$ > "${LOCK_FILE}"

# --- Disk space pre-check ---
avail_kb="$(df --output=avail "${BACKUP_DIR}" 2>/dev/null | tail -1 | tr -d ' ')"
if [ -n "${avail_kb}" ]; then
    avail_mb=$((avail_kb / 1024))
    if [ "${avail_mb}" -lt "${MIN_FREE_MB}" ]; then
        echo "[$(date -Iseconds)] ERROR: Insufficient disk space: ${avail_mb}MB available, need ${MIN_FREE_MB}MB."
        exit 1
    fi
    echo "[$(date -Iseconds)] Disk check OK: ${avail_mb}MB available."
fi

echo "[$(date -Iseconds)] Backup started — schemas: ${SCHEMAS[*]}"

FAILED=0
for schema in "${SCHEMAS[@]}"; do
    outfile="${BACKUP_DIR}/${schema}_${TIMESTAMP}.sql.gz"
    _PARTIAL_FILE="${outfile}"
    echo "  Dumping schema '${schema}' → ${outfile}"

    if ! pg_dump \
        --schema="${schema}" \
        --no-owner \
        --no-privileges \
        --format=plain \
        | gzip -9 > "${outfile}"; then
        echo "  ERROR: pg_dump failed for schema '${schema}'"
        rm -f "${outfile}"
        FAILED=$((FAILED + 1))
        continue
    fi

    # --- Integrity verification ---
    if ! gzip -t "${outfile}" 2>/dev/null; then
        echo "  ERROR: Integrity check failed for ${outfile} — removing corrupt backup"
        rm -f "${outfile}"
        FAILED=$((FAILED + 1))
        continue
    fi

    _PARTIAL_FILE=""
    echo "  Done: $(du -h "${outfile}" | cut -f1) (integrity verified)"
done

if [ "${FAILED}" -gt 0 ]; then
    echo "[$(date -Iseconds)] WARNING: ${FAILED} schema backup(s) failed."
fi

echo "[$(date -Iseconds)] All schemas dumped (${FAILED} failures)."

# ---------------------------------------------------------------------------
# Retention — keep only the newest KEEP_COUNT backups per schema
# ---------------------------------------------------------------------------

for schema in "${SCHEMAS[@]}"; do
    file_count=$(find "${BACKUP_DIR}" -maxdepth 1 -name "${schema}_*.sql.gz" | wc -l)
    if [ "${file_count}" -gt "${KEEP_COUNT}" ]; then
        remove_count=$((file_count - KEEP_COUNT))
        echo "  Pruning ${remove_count} old backup(s) for schema '${schema}'"
        find "${BACKUP_DIR}" -maxdepth 1 -name "${schema}_*.sql.gz" -printf '%T@ %p\n' \
            | sort -n \
            | head -n "${remove_count}" \
            | awk '{print $2}' \
            | xargs rm -f
    fi
done

echo "[$(date -Iseconds)] Backup complete. Retained last ${KEEP_COUNT} per schema in ${BACKUP_DIR}"
