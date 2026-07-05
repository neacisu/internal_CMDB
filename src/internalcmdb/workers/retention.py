"""F5.5 — Data Retention Jobs.

Drops old partitions and stale rows from telemetry, governance and
discovery tables, then runs VACUUM ANALYZE on the remaining data.

Retention windows are read at job start from ``config.app_setting``
(``retention.*`` keys, editable in the Settings UI). Each rule carries a
hardcoded fallback used when the setting is missing or invalid.

Rule modes
----------
- ``partitions``  → drop expired child partitions (partitioned tables)
- ``delete``      → plain ``DELETE`` of expired rows
- ``snapshots``   → FK-safe purge of ``discovery.collector_snapshot`` and
  ``discovery.snapshot_diff`` (diffs reference snapshots via two FKs with
  no ``ON DELETE CASCADE``, so referencing diffs must be deleted first)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, text

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# ARQ passes a context dict to worker coroutines (``job_id``, ``job_try``, ``redis``, …).
_Ctx = dict[str, Any]

# Snapshot kinds stored at high frequency; shorter full-resolution retention window.
_HIGH_FREQ_SNAPSHOT_KINDS: tuple[str, ...] = ("heartbeat", "container_resources")

# Each rule: table, ts_column, mode, setting_key (config.app_setting key holding
# the retention window in days; empty = no setting) and default_days fallback.
_RETENTION_RULES: list[dict[str, str]] = [
    {
        "table": "telemetry.metric_point",
        "ts_column": "collected_at",
        "mode": "partitions",
        "setting_key": "retention.metric_points_days",
        "default_days": "90",
    },
    {
        "table": "telemetry.slo_measurement",
        "ts_column": "measured_at",
        "mode": "partitions",
        "setting_key": "",
        "default_days": "365",
    },
    {
        "table": "governance.audit_event",
        "ts_column": "created_at",
        "mode": "delete",
        "setting_key": "retention.audit_events_days",
        "default_days": "14",
    },
    {
        "table": "telemetry.llm_call_log",
        "ts_column": "called_at",
        "mode": "delete",
        "setting_key": "retention.llm_calls_days",
        "default_days": "90",
    },
    {
        "table": "discovery.collector_snapshot",
        "ts_column": "collected_at",
        "mode": "snapshots",
        "setting_key": "retention.snapshots_days",
        "default_days": "14",
    },
]

_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_.]{0,62}$")
_SAFE_INTERVAL = re.compile(r"^\d+ days$")

_PARTITION_MONTHS_AHEAD = 2  # number of future months to pre-create partitions
_MONTHS_PER_YEAR = 12  # calendar months in a year
_DEFAULT_HIGH_FREQ_RETENTION = "3 days"  # fallback when settings store unavailable


def _validate_interval(interval: str) -> None:
    """Guard against SQL injection via retention interval literals."""
    if not _SAFE_INTERVAL.match(interval):
        raise ValueError(f"Unsafe interval: {interval!r}")


def _validate_identifier(name: str, label: str) -> None:
    """Guard against SQL injection via table/column names."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Unsafe {label}: {name!r}")


def _table_exists(conn: Any, table: str) -> bool:
    """Check if a table exists in the database."""
    parts = table.split(".", 1)
    if len(parts) == _PARTITION_MONTHS_AHEAD:
        schema, tbl = parts
    else:
        schema, tbl = "public", parts[0]
    result = conn.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :tbl)"
        ),
        {"schema": schema, "tbl": tbl},
    )
    return bool(result.scalar())


def _drop_old_partitions(
    conn: Any,
    parent_table: str,
    ts_column: str,
    interval: str,
) -> int:
    """Drop child partitions whose upper bound is older than the retention window.

    Always keeps at least one partition to prevent INSERT failures on the
    parent partitioned table.
    """
    _validate_identifier(parent_table, "parent_table")
    _validate_identifier(ts_column, "ts_column")
    _validate_interval(interval)

    conn.execute(text("SET LOCAL lock_timeout = '10s'"))

    rows = conn.execute(
        text(
            "SELECT inhrelid::regclass::text FROM pg_inherits WHERE inhparent = :parent::regclass"
        ),
        {"parent": parent_table},
    ).fetchall()

    total_partitions = len(rows)
    if total_partitions <= 1:
        logger.info("Only %d partition(s) for %s — skipping drop", total_partitions, parent_table)
        return 0

    dropped = 0
    for (child,) in rows:
        if total_partitions - dropped <= 1:
            logger.info("Keeping last partition %s for %s", child, parent_table)
            break
        check_sql = (
            "SELECT EXISTS (SELECT 1 FROM "
            + child
            + " WHERE "
            + ts_column
            + " >= NOW() - CAST(:retention_interval AS interval) LIMIT 1)"
        )
        result = conn.execute(text(check_sql), {"retention_interval": interval})
        has_recent = result.scalar()
        if not has_recent:
            logger.info("Dropping expired partition %s", child)
            drop_sql = "DROP TABLE IF EXISTS " + child
            conn.execute(text(drop_sql))
            dropped += 1
    return dropped


def _delete_old_rows(conn: Any, table: str, ts_column: str, interval: str) -> int:
    """DELETE rows older than the retention interval (non-partitioned tables)."""
    _validate_identifier(table, "table")
    _validate_identifier(ts_column, "ts_column")
    delete_sql = (
        "DELETE FROM " + table + " WHERE " + ts_column + " < NOW() - CAST(:retention_interval AS interval)"
    )
    result = conn.execute(text(delete_sql), {"retention_interval": interval})
    return result.rowcount or 0


def _purge_snapshots(
    conn: Any,
    interval: str,
    high_freq_interval: str,
    vitals_downsample_interval: str,
) -> dict[str, int]:
    """FK-safe purge of collector snapshots and their diffs.

    Order within one transaction:
    1. Purge high-frequency kinds (heartbeat, container_resources) past *high_freq_interval*.
    2. Downsample ``system_vitals`` older than *vitals_downsample_interval*.
    3. Purge all remaining snapshots past *interval* (default 14 days).
    """
    counts: dict[str, int] = {
        "snapshot_diffs_deleted": 0,
        "snapshots_deleted": 0,
        "high_freq_snapshots_deleted": 0,
        "vitals_downsampled": 0,
    }
    kinds_sql = ", ".join(f"'{k}'" for k in _HIGH_FREQ_SNAPSHOT_KINDS)

    conn.execute(text("BEGIN"))
    try:
        # ── High-frequency kind purge ──────────────────────────────────
        for fk_col in ("snapshot_id", "previous_snapshot_id"):
            deleted = conn.execute(
                text(
                    f"DELETE FROM discovery.snapshot_diff d "
                    f"USING discovery.collector_snapshot s "
                    f"WHERE d.{fk_col} = s.snapshot_id "
                    f"AND s.snapshot_kind IN ({kinds_sql}) "
                    f"AND s.collected_at < NOW() - CAST(:hf AS interval)"
                ),
                {"hf": high_freq_interval},
            ).rowcount
            counts["snapshot_diffs_deleted"] += deleted or 0

        counts["high_freq_snapshots_deleted"] = (
            conn.execute(
                text(
                    f"DELETE FROM discovery.collector_snapshot s "
                    f"WHERE s.snapshot_kind IN ({kinds_sql}) "
                    f"AND s.collected_at < NOW() - CAST(:hf AS interval) "
                    f"AND NOT EXISTS (SELECT 1 FROM discovery.snapshot_diff d "
                    f"                WHERE d.snapshot_id = s.snapshot_id "
                    f"                   OR d.previous_snapshot_id = s.snapshot_id)"
                ),
                {"hf": high_freq_interval},
            ).rowcount
            or 0
        )

        # ── system_vitals downsample (one row per agent per hour) ──────
        counts["vitals_downsampled"] = _downsample_vitals(conn, vitals_downsample_interval)

        # ── General retention purge (all kinds, *interval*) ────────────
        for fk_col in ("snapshot_id", "previous_snapshot_id"):
            deleted = conn.execute(
                text(
                    "DELETE FROM discovery.snapshot_diff d "
                    "USING discovery.collector_snapshot s "
                    f"WHERE d.{fk_col} = s.snapshot_id "
                    "AND s.collected_at < NOW() - CAST(:retention_interval AS interval)"
                ),
                {"retention_interval": interval},
            ).rowcount
            counts["snapshot_diffs_deleted"] += deleted or 0

        counts["snapshots_deleted"] = (
            conn.execute(
                text(
                    "DELETE FROM discovery.collector_snapshot s "
                    "WHERE s.collected_at < NOW() - CAST(:retention_interval AS interval) "
                    "AND NOT EXISTS (SELECT 1 FROM discovery.snapshot_diff d "
                    "                WHERE d.snapshot_id = s.snapshot_id "
                    "                   OR d.previous_snapshot_id = s.snapshot_id)"
                ),
                {"retention_interval": interval},
            ).rowcount
            or 0
        )
        conn.execute(text("COMMIT"))
    except Exception:
        conn.execute(text("ROLLBACK"))
        raise
    return counts


def _downsample_vitals(conn: Any, downsample_after: str) -> int:
    """Keep one system_vitals snapshot per agent per hour; delete the rest."""
    # Remove diffs referencing vitals rows that will be downsampled away.
    for fk_col in ("snapshot_id", "previous_snapshot_id"):
        conn.execute(
            text(
                f"DELETE FROM discovery.snapshot_diff d "
                f"USING discovery.collector_snapshot s "
                f"WHERE d.{fk_col} = s.snapshot_id "
                f"AND s.snapshot_kind = 'system_vitals' "
                f"AND s.collected_at < NOW() - CAST(:ds AS interval) "
                f"AND s.snapshot_id NOT IN ("
                f"  SELECT DISTINCT ON (agent_id, date_trunc('hour', collected_at)) snapshot_id"
                f"    FROM discovery.collector_snapshot"
                f"   WHERE snapshot_kind = 'system_vitals'"
                f"     AND collected_at < NOW() - CAST(:ds AS interval)"
                f"   ORDER BY agent_id, date_trunc('hour', collected_at), collected_at ASC"
                f")"
            ),
            {"ds": downsample_after},
        )

    return (
        conn.execute(
            text(
                "DELETE FROM discovery.collector_snapshot s "
                "WHERE s.snapshot_kind = 'system_vitals' "
                "AND s.collected_at < NOW() - CAST(:ds AS interval) "
                "AND s.snapshot_id NOT IN ("
                "  SELECT DISTINCT ON (agent_id, date_trunc('hour', collected_at)) snapshot_id"
                "    FROM discovery.collector_snapshot"
                "   WHERE snapshot_kind = 'system_vitals'"
                "     AND collected_at < NOW() - CAST(:ds AS interval)"
                "   ORDER BY agent_id, date_trunc('hour', collected_at), collected_at ASC"
                ") "
                "AND NOT EXISTS (SELECT 1 FROM discovery.snapshot_diff d "
                "                WHERE d.snapshot_id = s.snapshot_id "
                "                   OR d.previous_snapshot_id = s.snapshot_id)"
            ),
            {"ds": downsample_after},
        ).rowcount
        or 0
    )


def _vacuum_table(conn: Any, table: str) -> None:
    """Run VACUUM ANALYZE (requires autocommit)."""
    _validate_identifier(table, "table")
    conn.execute(text(f"VACUUM ANALYZE {table}"))


def _ensure_future_partitions(conn: Any, parent_table: str, _ts_column: str = "") -> list[str]:
    """Create partitions for the current and next month if they don't exist."""
    from datetime import UTC, datetime  # noqa: PLC0415

    _validate_identifier(parent_table, "parent_table")
    created: list[str] = []
    now = datetime.now(tz=UTC)

    for offset in (0, 1):
        m = now.month + offset
        y = now.year
        if m > _MONTHS_PER_YEAR:
            m -= _MONTHS_PER_YEAR
            y += 1
        p_start = f"{y}-{m:02d}-01"
        p_end = f"{y + 1}-01-01" if m == _MONTHS_PER_YEAR else f"{y}-{m + 1:02d}-01"

        schema = parent_table.split(".", maxsplit=1)[0] if "." in parent_table else "public"
        base = parent_table.rsplit(".", maxsplit=1)[-1]
        part_name = f"{schema}.{base}_{y}_{m:02d}"
        _validate_identifier(part_name, "partition_name")

        try:
            conn.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {part_name} "
                    f"PARTITION OF {parent_table} "
                    f"FOR VALUES FROM ('{p_start}') TO ('{p_end}')"
                )
            )
            created.append(part_name)
        except Exception:
            logger.debug("Partition %s already exists or creation failed", part_name, exc_info=True)
    return created


_MATERIALIZED_VIEWS: list[str] = [
    "cognitive.mv_fleet_health_live",
    "cognitive.mv_llm_accuracy_daily",
]


def _matview_exists(conn: Any, matview: str) -> bool:
    """Return True when a materialized view exists in pg_matviews."""
    schema, name = matview.split(".", 1)
    result = conn.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM pg_matviews"
            "  WHERE schemaname = :schema AND matviewname = :name"
            ")"
        ),
        {"schema": schema, "name": name},
    )
    return bool(result.scalar())


def _refresh_materialized_views(conn: Any) -> list[dict[str, str]]:
    """Refresh all materialized views concurrently (requires unique index)."""
    results: list[dict[str, str]] = []
    for mv in _MATERIALIZED_VIEWS:
        _validate_identifier(mv, "materialized_view")
        if not _matview_exists(conn, mv):
            logger.warning("Materialized view %s does not exist — skipping refresh", mv)
            results.append({"view": mv, "status": "missing"})
            continue
        try:
            conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}"))
            results.append({"view": mv, "status": "refreshed"})
            logger.info("Refreshed materialized view %s", mv)
        except Exception:
            logger.warning("Concurrent refresh failed for %s, falling back to full refresh", mv)
            try:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW {mv}"))
                results.append({"view": mv, "status": "refreshed_full"})
            except Exception:
                logger.exception("Failed to refresh materialized view %s", mv)
                results.append({"view": mv, "status": "error"})
    return results


def _apply_one_rule(
    engine: Engine,
    rule: dict[str, Any],
    report: dict[str, Any],
) -> None:
    """Apply one retention rule against the database.

    Handles table-existence guard, mode dispatch (partitions / delete /
    snapshots), vacuum, and appends the result (or error) to *report* in-place.
    """
    table = rule["table"]
    ts_col = rule["ts_column"]
    interval = rule["interval"]
    mode = rule.get("mode", "delete")

    try:
        with engine.connect() as conn:
            if not _table_exists(conn, table):
                logger.warning("Retention: table %s does not exist — skipping.", table)
                report["errors"].append({"table": table, "error": "table does not exist"})
                return

            extra: dict[str, int] = {}
            if mode == "partitions":
                created = _ensure_future_partitions(conn, table, ts_col)
                if created:
                    report["partitions_created"].extend(created)
                count = _drop_old_partitions(conn, table, ts_col, interval)
                action = "partitions_dropped"
            elif mode == "snapshots":
                hf_interval = rule.get("high_freq_interval", interval)
                vitals_ds = rule.get("vitals_downsample_interval", _DEFAULT_HIGH_FREQ_RETENTION)
                counts = _purge_snapshots(conn, interval, hf_interval, vitals_ds)
                count = counts["snapshots_deleted"]
                action = "rows_deleted"
                extra = {
                    "snapshot_diffs_deleted": counts["snapshot_diffs_deleted"],
                    "high_freq_snapshots_deleted": counts["high_freq_snapshots_deleted"],
                    "vitals_downsampled": counts["vitals_downsampled"],
                }
                _vacuum_table(conn, "discovery.snapshot_diff")
            else:
                count = _delete_old_rows(conn, table, ts_col, interval)
                action = "rows_deleted"

            _vacuum_table(conn, table)

            entry: dict[str, Any] = {"table": table, "interval": interval, action: count, **extra}
            report["rules_applied"].append(entry)
            logger.info("Retention: %s — %s=%d %s", table, action, count, extra or "")

    except Exception as exc:
        logger.exception("Retention failed for %s", table)
        report["errors"].append({"table": table, "error": str(exc)})


def _run_view_refresh(engine: Engine, report: dict[str, Any]) -> None:
    """Refresh all materialized views and append results to *report*."""
    try:
        with engine.connect() as conn:
            report["views_refreshed"] = _refresh_materialized_views(conn)
    except Exception as exc:
        logger.exception("Materialized view refresh failed")
        report["errors"].append({"table": "materialized_views", "error": str(exc)})


def _coerce_days(value: Any, fallback: int) -> int:
    """Coerce a settings value to a positive day count, else *fallback*."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        return fallback
    return days if days >= 1 else fallback


async def _resolve_rules() -> list[dict[str, str]]:
    """Build the effective rule list, reading windows from the settings store.

    Falls back to each rule's ``default_days`` when the setting is missing,
    unreadable or invalid, so retention always runs.
    """
    from internalcmdb.config.settings_store import get_settings_store  # noqa: PLC0415

    store = get_settings_store()
    hf_days = _coerce_days(await store.get("retention.high_freq_snapshots_days"), 3)
    vitals_ds_days = _coerce_days(await store.get("retention.vitals_downsample_days"), 3)
    resolved: list[dict[str, str]] = []
    for rule in _RETENTION_RULES:
        default_days = int(rule["default_days"])
        days = default_days
        if rule["setting_key"]:
            try:
                days = _coerce_days(await store.get(rule["setting_key"]), default_days)
            except Exception:
                logger.warning(
                    "Retention: could not read setting %r — using default %d days",
                    rule["setting_key"],
                    default_days,
                )
        entry: dict[str, str] = {**rule, "interval": f"{days} days"}
        if rule.get("mode") == "snapshots":
            entry["high_freq_interval"] = f"{hf_days} days"
            entry["vitals_downsample_interval"] = f"{vitals_ds_days} days"
        resolved.append(entry)
    return resolved


def run_retention(database_url: str, rules: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Execute all retention rules and return a summary report.

    Uses a synchronous SQLAlchemy engine with ``AUTOCOMMIT`` so ``VACUUM`` can run.
    Call from async code via :func:`asyncio.to_thread` to avoid blocking the event loop.
    When *rules* is ``None`` the hardcoded defaults are used (settings ignored).
    """
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    report: dict[str, Any] = {
        "rules_applied": [],
        "errors": [],
        "partitions_created": [],
        "views_refreshed": [],
    }

    if rules is None:
        rules = []
        for r in _RETENTION_RULES:
            entry: dict[str, str] = {**r, "interval": f"{r['default_days']} days"}
            if r.get("mode") == "snapshots":
                entry["high_freq_interval"] = _DEFAULT_HIGH_FREQ_RETENTION
                entry["vitals_downsample_interval"] = _DEFAULT_HIGH_FREQ_RETENTION
            rules.append(entry)

    for rule in rules:
        _apply_one_rule(engine, rule, report)

    _run_view_refresh(engine, report)
    return report


async def data_retention_job(ctx: _Ctx) -> dict[str, Any]:
    """ARQ-compatible async entry point for the retention worker.

    Heavy DDL/DML runs in a thread pool so the worker event loop stays responsive.
    ``ctx`` is the ARQ job context: ``job_id``, ``job_try``, ``redis``, etc.
    Optional ``ctx[\"database_url\"]`` overrides the app default (e.g. integration tests).
    """
    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    job_id = ctx.get("job_id")
    job_try = ctx.get("job_try", 1)
    logger.info(
        "[data_retention] started job_id=%s job_try=%s",
        job_id,
        job_try,
    )
    start = time.monotonic()

    settings = get_settings()
    database_url = str(ctx.get("database_url") or settings.database_url)
    rules = await _resolve_rules()

    result = await asyncio.to_thread(run_retention, database_url, rules)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "[data_retention] completed in %dms job_id=%s job_try=%s errors=%d",
        elapsed_ms,
        job_id,
        job_try,
        len(result.get("errors") or []),
    )

    return {
        "task": "data_retention",
        "status": "completed",
        "elapsed_ms": elapsed_ms,
        "arq_job_id": job_id,
        "arq_job_try": job_try,
        **result,
    }
