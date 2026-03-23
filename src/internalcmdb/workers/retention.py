"""F5.5 — Data Retention Jobs.

Drops old partitions and stale rows from telemetry and governance
tables, then runs VACUUM ANALYZE on the remaining data.

Retention windows
-----------------
- ``telemetry.metric_point``  → 90 days
- ``governance.audit_event``  → 1 year
- ``telemetry.llm_call_log``  → 6 months
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

# ARQ passes a context dict to worker coroutines (``job_id``, ``job_try``, ``redis``, …).
_Ctx = dict[str, Any]

_RETENTION_RULES: list[dict[str, str]] = [
    {
        "table": "telemetry.metric_point",
        "ts_column": "collected_at",
        "interval": "90 days",
        "partitioned": "true",
    },
    {
        "table": "telemetry.slo_measurement",
        "ts_column": "measured_at",
        "interval": "1 year",
        "partitioned": "true",
    },
    {
        "table": "governance.audit_event",
        "ts_column": "created_at",
        "interval": "1 year",
        "partitioned": "false",
    },
    {
        "table": "telemetry.llm_call_log",
        "ts_column": "called_at",
        "interval": "6 months",
        "partitioned": "false",
    },
]

import re  # noqa: E402, PLC0415

_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_.]{0,62}$")


def _validate_identifier(name: str, label: str) -> None:
    """Guard against SQL injection via table/column names."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Unsafe {label}: {name!r}")


def _table_exists(conn: Any, table: str) -> bool:
    """Check if a table exists in the database."""
    parts = table.split(".", 1)
    if len(parts) == 2:
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
    conn: Any, parent_table: str, ts_column: str, interval: str,
) -> int:
    """Drop child partitions whose upper bound is older than the retention window.

    Always keeps at least one partition to prevent INSERT failures on the
    parent partitioned table.
    """
    _validate_identifier(parent_table, "parent_table")
    _validate_identifier(ts_column, "ts_column")
    _validate_identifier(interval.replace(" ", "_"), "interval")

    conn.execute(text("SET LOCAL lock_timeout = '10s'"))

    rows = conn.execute(
        text(
            "SELECT inhrelid::regclass::text FROM pg_inherits "
            f"WHERE inhparent = '{parent_table}'::regclass"
        )
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
        result = conn.execute(
            text(f"""
                SELECT EXISTS (
                    SELECT 1
                      FROM {child}
                     WHERE {ts_column} >= NOW() - INTERVAL '{interval}'
                     LIMIT 1
                )
            """)
        )
        has_recent = result.scalar()
        if not has_recent:
            logger.info("Dropping expired partition %s", child)
            conn.execute(text(f"DROP TABLE IF EXISTS {child}"))
            dropped += 1
    return dropped


def _delete_old_rows(conn: Any, table: str, ts_column: str, interval: str) -> int:
    """DELETE rows older than the retention interval (non-partitioned tables)."""
    _validate_identifier(table, "table")
    _validate_identifier(ts_column, "ts_column")
    result = conn.execute(
        text(f"DELETE FROM {table} WHERE {ts_column} < NOW() - INTERVAL '{interval}'")
    )
    return result.rowcount or 0


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
        if m > 12:
            m -= 12
            y += 1
        p_start = f"{y}-{m:02d}-01"
        if m == 12:
            p_end = f"{y + 1}-01-01"
        else:
            p_end = f"{y}-{m + 1:02d}-01"

        schema = parent_table.split(".")[0] if "." in parent_table else "public"
        base = parent_table.split(".")[-1]
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


def _refresh_materialized_views(conn: Any) -> list[dict[str, str]]:
    """Refresh all materialized views concurrently (requires unique index)."""
    results: list[dict[str, str]] = []
    for mv in _MATERIALIZED_VIEWS:
        _validate_identifier(mv, "materialized_view")
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


def run_retention(database_url: str) -> dict[str, Any]:
    """Execute all retention rules and return a summary report.

    Uses a synchronous SQLAlchemy engine with ``AUTOCOMMIT`` so ``VACUUM`` can run.
    Call from async code via :func:`asyncio.to_thread` to avoid blocking the event loop.
    """
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    report: dict[str, Any] = {
        "rules_applied": [],
        "errors": [],
        "partitions_created": [],
        "views_refreshed": [],
    }

    for rule in _RETENTION_RULES:
        table = rule["table"]
        ts_col = rule["ts_column"]
        interval = rule["interval"]
        is_partitioned = rule["partitioned"] == "true"

        try:
            with engine.connect() as conn:
                if not _table_exists(conn, table):
                    logger.warning("Retention: table %s does not exist — skipping.", table)
                    report["errors"].append({"table": table, "error": "table does not exist"})
                    continue

                if is_partitioned:
                    created = _ensure_future_partitions(conn, table, ts_col)
                    if created:
                        report["partitions_created"].extend(created)
                    count = _drop_old_partitions(conn, table, ts_col, interval)
                    action = "partitions_dropped"
                else:
                    count = _delete_old_rows(conn, table, ts_col, interval)
                    action = "rows_deleted"

                _vacuum_table(conn, table)

                entry = {"table": table, "interval": interval, action: count}
                report["rules_applied"].append(entry)
                logger.info("Retention: %s — %s=%d", table, action, count)

        except Exception as exc:
            logger.exception("Retention failed for %s", table)
            report["errors"].append({"table": table, "error": str(exc)})

    try:
        with engine.connect() as conn:
            report["views_refreshed"] = _refresh_materialized_views(conn)
    except Exception as exc:
        logger.exception("Materialized view refresh failed")
        report["errors"].append({"table": "materialized_views", "error": str(exc)})

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

    result = await asyncio.to_thread(run_retention, database_url)

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
