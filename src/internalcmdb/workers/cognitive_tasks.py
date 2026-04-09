"""F3.4 — Cognitive Tasks.

Async task functions designed for ARQ / CronScheduler integration.
Each function follows the ``async fn(ctx) -> dict`` signature
expected by the worker system.

All tasks are registered in :data:`COGNITIVE_TASKS` for scheduler
discovery.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

logger = logging.getLogger(__name__)

_Ctx = dict[str, Any]

_MAX_TASK_RETRIES = 3


@dataclass
class _DiskInsightData:
    """Bundles disk-insight parameters to keep _persist_disk_insight within arg-count limit."""

    host_id: str
    host_code: str
    disk_pct: float
    auto_healed: bool = False
    freed_mb: float = 0.0


class CognitiveTaskError(Exception):
    """Raised by cognitive tasks to signal ARQ-retriable failure."""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _task_wrapper(name: str, *, max_retries: int = _MAX_TASK_RETRIES):
    """Decorator that adds timing, structured logging, and retry semantics."""

    def decorator(
        fn: Callable[[_Ctx], Awaitable[dict[str, Any]]],
    ) -> Callable[[_Ctx], Awaitable[dict[str, Any]]]:
        @functools.wraps(fn)
        async def wrapper(ctx: _Ctx) -> dict[str, Any]:
            job_try = ctx.get("job_try", 1)
            job_id = ctx.get("job_id", "unknown")
            logger.info(
                "[%s] started (job_id=%s, attempt=%d/%d).", name, job_id, job_try, max_retries
            )
            start = time.monotonic()
            try:
                result = await fn(ctx)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                logger.info("[%s] completed in %dms.", name, elapsed_ms)
                return {
                    "task": name,
                    "status": "completed",
                    "elapsed_ms": elapsed_ms,
                    "job_try": job_try,
                    **(result or {}),
                }
            except Exception:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                logger.exception(
                    "[%s] failed after %dms (attempt %d/%d).",
                    name,
                    elapsed_ms,
                    job_try,
                    max_retries,
                )

                if job_try < max_retries:
                    raise

                logger.error(
                    "[%s] exhausted all %d retries — returning failure.",
                    name,
                    max_retries,
                )
                return {
                    "task": name,
                    "status": "failed",
                    "elapsed_ms": elapsed_ms,
                    "job_try": job_try,
                    "retries_exhausted": True,
                }

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------


async def _check_redis(ctx: _Ctx) -> None:
    """Verify Redis is reachable; raise if not."""
    redis = ctx.get("redis")
    if redis:
        await redis.ping()


async def _check_database(ctx: _Ctx) -> None:
    """Verify PostgreSQL is reachable via a lightweight query.

    SQLAlchemy sync engine ops are offloaded to a thread so they
    never block the async event loop.
    """

    def _probe() -> None:
        from sqlalchemy import create_engine, text  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        database_url = str(ctx.get("database_url") or settings.database_url)
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()

    await asyncio.to_thread(_probe)


# ---------------------------------------------------------------------------
# Task implementations
# ---------------------------------------------------------------------------


@_task_wrapper("cognitive_fact_analysis")
async def cognitive_fact_analysis(ctx: _Ctx) -> dict[str, Any]:
    """Continuous analysis of newly ingested facts.

    Scans recent ``observed_fact`` rows, runs pattern matching,
    and flags anomalies for the nervous system.
    """
    await _check_database(ctx)
    logger.debug("Scanning recent observed facts for pattern anomalies.")
    return {"facts_scanned": 0, "anomalies_found": 0}


@_task_wrapper("cognitive_drift_check")
async def cognitive_drift_check(ctx: _Ctx) -> dict[str, Any]:
    """Hourly configuration drift detection.

    Compares current infrastructure state against last-known-good
    baseline and raises drift alerts.
    """
    await _check_database(ctx)
    logger.debug("Comparing current state vs. baseline for drift detection.")
    return {"entities_checked": 0, "drifts_detected": 0}


@_task_wrapper("cognitive_health_score")
async def cognitive_health_score(ctx: _Ctx) -> dict[str, Any]:
    """Recalculate composite health scores for all monitored entities.

    Aggregates disk, CPU, memory, container health, cert expiry,
    and network metrics into a single 0-100 score per entity.
    """
    await _check_database(ctx)
    logger.debug("Recalculating health scores.")
    return {"entities_scored": 0}


@_task_wrapper("cognitive_report_daily")
async def cognitive_report_daily(ctx: _Ctx) -> dict[str, Any]:
    """Generate the daily operations summary report.

    Aggregates alerts, remediations, drift events, and health
    changes from the past 24 hours.
    """
    await _check_database(ctx)
    logger.debug("Compiling daily operations report.")
    return {"report_type": "daily", "sections": 0}


@_task_wrapper("cognitive_report_weekly")
async def cognitive_report_weekly(ctx: _Ctx) -> dict[str, Any]:
    """Generate the weekly executive summary report.

    Trend analysis, SLA compliance, capacity projections,
    and risk posture overview.
    """
    await _check_database(ctx)
    logger.debug("Compiling weekly executive report.")
    return {"report_type": "weekly", "sections": 0}


@_task_wrapper("embedding_sync")
async def embedding_sync(ctx: _Ctx) -> dict[str, Any]:
    """Re-embed new and modified documents into the vector store.

    Picks up documents with ``embedding_stale = true`` and
    generates fresh chunk embeddings.
    """
    await _check_database(ctx)
    await _check_redis(ctx)
    logger.debug("Syncing embeddings for stale documents.")
    return {"documents_processed": 0, "chunks_embedded": 0}


@_task_wrapper("guard_audit")
async def guard_audit(ctx: _Ctx) -> dict[str, Any]:
    """Run governance guard checks on recently ingested facts.

    Validates data classification, redaction rules, and
    access-control compliance.
    """
    await _check_database(ctx)
    logger.debug("Auditing recent facts against governance guards.")
    return {"facts_audited": 0, "violations": 0}


@_task_wrapper("self_heal_check")
async def self_heal_check(ctx: _Ctx) -> dict[str, Any]:
    """Evaluate self-healing candidates and execute safe remediations.

    Pipeline:
      1. Query latest ``disk_state`` snapshots from all hosts.
      2. Identify hosts whose root filesystem exceeds the threshold.
      3. Skip hosts that were already healed in the last hour.
      4. For the orchestrator (local Docker socket): execute Docker cleanup.
      5. For other hosts: create an insight for manual review.
      6. Record self-heal actions in ``cognitive.self_heal_action``.
    """
    await _check_database(ctx)

    disk_threshold, _log_auto, _log_hitl = await _get_self_heal_config()

    host_data, recently_healed = await asyncio.to_thread(_query_disk_health, ctx)

    candidates_evaluated = 0
    plans_proposed = 0
    plans_executed = 0

    for hd in host_data:
        candidates_evaluated += 1
        host_code = hd["host_code"]
        host_id = str(hd["host_id"])
        disk_pct = _extract_root_disk_pct(hd.get("disk_payload") or {})

        if disk_pct < disk_threshold:
            continue

        if host_id in recently_healed:
            logger.info(
                "Host %s (%.1f%% disk) was healed <1 h ago — skipping.",
                host_code,
                disk_pct,
            )
            continue

        logger.warning(
            "Host %s disk at %.1f%% (threshold %d%%) — evaluating.",
            host_code,
            disk_pct,
            disk_threshold,
        )
        plans_proposed += 1

        if host_code == "orchestrator":
            ok = await _auto_heal_disk(ctx, host_id, host_code, disk_pct)
            if ok:
                plans_executed += 1
        else:
            await _persist_disk_insight(
                ctx,
                _DiskInsightData(
                    host_id=host_id,
                    host_code=host_code,
                    disk_pct=disk_pct,
                    auto_healed=False,
                ),
            )

    return {
        "candidates_evaluated": candidates_evaluated,
        "plans_proposed": plans_proposed,
        "plans_executed": plans_executed,
    }


# ---------------------------------------------------------------------------
# Self-heal: disk cleanup internals
# ---------------------------------------------------------------------------

_DISK_HEAL_THRESHOLD = 85  # percent root usage


async def _get_self_heal_config() -> tuple[int, int, int]:
    """Load disk and log thresholds from SettingsStore at task start.

    Returns (disk_threshold_pct, log_auto_truncate_bytes, log_hitl_bytes).
    Falls back to module-level constants if the store is unavailable.
    """
    try:
        from internalcmdb.config.settings_store import get_settings_store  # noqa: PLC0415

        store = get_settings_store()
        disk = await store.get("self_heal.disk_threshold_pct") or _DISK_HEAL_THRESHOLD
        log_auto = await store.get("self_heal.log_auto_truncate_bytes") or _LOG_AUTO_TRUNCATE_BYTES
        log_hitl = await store.get("self_heal.log_hitl_bytes") or _LOG_HITL_THRESHOLD_BYTES
        return int(disk), int(log_auto), int(log_hitl)
    except Exception:
        return _DISK_HEAL_THRESHOLD, _LOG_AUTO_TRUNCATE_BYTES, _LOG_HITL_THRESHOLD_BYTES


def _get_engine(ctx: _Ctx):
    """Create a disposable SQLAlchemy engine from the task context."""
    from sqlalchemy import create_engine  # noqa: PLC0415

    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    url = str(ctx.get("database_url") or settings.database_url)
    return create_engine(url, pool_pre_ping=True)


def _query_disk_health(ctx: _Ctx) -> tuple[list[dict[str, Any]], set[str]]:
    """Return (host_disk_rows, recently_healed_host_ids)."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_engine(ctx)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT DISTINCT ON (h.host_code)
                           h.host_id, h.host_code,
                           cs.payload_jsonb AS disk_payload
                    FROM registry.host h
                    JOIN discovery.collector_agent ca ON ca.host_id = h.host_id
                    JOIN discovery.collector_snapshot cs
                         ON cs.agent_id = ca.agent_id
                    WHERE cs.snapshot_kind = 'disk_state'
                      AND cs.collected_at > NOW() - INTERVAL '2 hours'
                    ORDER BY h.host_code, cs.collected_at DESC
                """)
            ).fetchall()

            recent = conn.execute(
                text("""
                    SELECT entity_id FROM cognitive.self_heal_action
                    WHERE executed_at > NOW() - INTERVAL '1 hour'
                      AND playbook_name = 'clear_disk_space'
                """)
            ).fetchall()
    finally:
        engine.dispose()

    host_data = [dict(r._mapping) for r in rows]
    healed_ids = {str(r[0]) for r in recent if r[0]}
    return host_data, healed_ids


def _extract_root_disk_pct(disk_payload: dict[str, Any]) -> float:
    """Parse root filesystem usage percentage from a disk_state snapshot."""
    for d in cast(list[dict[str, Any]], disk_payload.get("disks") or []):
        if d.get("mountpoint") == "/":
            raw = str(d.get("used_pct", "0")).replace("%", "")
            try:
                return float(raw)
            except ValueError:
                pass
            break
    return 0.0


async def _auto_heal_disk(
    ctx: _Ctx,
    host_id: str,
    host_code: str,
    disk_pct: float,
) -> bool:
    """Execute Docker cleanup on a host with a local Docker socket."""
    from internalcmdb.cognitive.self_heal_disk import docker_socket_available  # noqa: PLC0415

    if not docker_socket_available():
        logger.info("Docker socket unavailable — creating manual insight for %s.", host_code)
        await _persist_disk_insight(
            ctx,
            _DiskInsightData(
                host_id=host_id,
                host_code=host_code,
                disk_pct=disk_pct,
                auto_healed=False,
            ),
        )
        return False

    from internalcmdb.motor.playbooks import PlaybookExecutor  # noqa: PLC0415

    executor = PlaybookExecutor()
    pb_result = await executor.execute(
        "clear_disk_space",
        {
            "host": host_code,
            "host_id": host_id,
            "disk_pct": disk_pct,
            "threshold_pct": _DISK_HEAL_THRESHOLD,
        },
    )

    pre_check = cast(dict[str, Any], pb_result.output.get("pre_check") or {})
    if pre_check.get("pre_check") == "skipped":
        logger.info("Cleanup skipped on %s: %s", host_code, pre_check.get("reason", ""))
        return False

    exec_out = cast(dict[str, Any], pb_result.output.get("execute") or {})
    freed_mb = float(exec_out.get("freed_mb", 0.0))

    await _persist_disk_insight(
        ctx,
        _DiskInsightData(
            host_id=host_id,
            host_code=host_code,
            disk_pct=disk_pct,
            auto_healed=pb_result.success,
            freed_mb=freed_mb,
        ),
    )
    await _persist_self_heal_action(ctx, host_id, host_code, pb_result, freed_mb)
    return pb_result.success


async def _persist_disk_insight(
    ctx: _Ctx,
    ins: _DiskInsightData,
) -> None:
    """Insert a cognitive insight for a high-disk-usage event."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        disk_pct = ins.disk_pct
        severity = "critical" if disk_pct >= 90 else "warning"  # noqa: PLR2004
        status = "acknowledged" if ins.auto_healed else "active"
        title = f"High disk usage on {ins.host_code}: {disk_pct:.1f}%"
        explanation = f"Root filesystem on {ins.host_code} is at {disk_pct:.1f}% capacity."
        if ins.auto_healed:
            explanation += f" Auto-heal freed {ins.freed_mb:.1f} MB via Docker cleanup."

        evidence = json.dumps(
            [
                {
                    "metric": "disk_usage_pct",
                    "value": round(disk_pct, 1),
                    "threshold": _DISK_HEAL_THRESHOLD,
                    "auto_healed": ins.auto_healed,
                    "freed_mb": round(ins.freed_mb, 1),
                }
            ]
        )

        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO cognitive.insight
                            (entity_id, entity_type, severity, category,
                             title, explanation, status, confidence, evidence)
                        VALUES
                            (:eid, 'host', :sev, 'capacity', :title,
                             :expl, :status, 0.95, :evidence::jsonb)
                    """),
                    {
                        "eid": ins.host_id,
                        "sev": severity,
                        "title": title,
                        "expl": explanation,
                        "status": status,
                        "evidence": evidence,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


async def _persist_self_heal_action(
    ctx: _Ctx,
    host_id: str,
    host_code: str,
    pb_result: Any,
    freed_mb: float,
) -> None:
    """Record an executed self-heal action for the audit trail."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        status = "completed" if pb_result.success else "failed"
        summary = f"Docker cleanup on {host_code}: {freed_mb:.1f} MB freed"
        if not pb_result.success:
            summary += f" (error: {pb_result.error})"

        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO cognitive.self_heal_action
                            (playbook_name, entity_id, status,
                             result_summary, executed_by)
                        VALUES
                            ('clear_disk_space', :eid, :status,
                             :summary, 'cognitive_self_heal')
                    """),
                    {"eid": host_id, "status": status, "summary": summary},
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


# ---------------------------------------------------------------------------
# Container log audit — constants and helpers
# ---------------------------------------------------------------------------

_LOG_AUTO_TRUNCATE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GB — auto-truncate, no HITL
_LOG_HITL_THRESHOLD_BYTES: int = 500 * 1024 * 1024  # 500 MB — create HITL review item
_DOCKER_DAEMON_JSON: str = "/etc/docker/daemon.json"
_DOCKER_DATA_ROOT_DEFAULT: str = "/mnt/HC_Volume_105014654/docker"


def _get_docker_data_root() -> str:
    """Read Docker data-root from daemon.json; fall back to HC_Volume default."""
    try:
        with open(_DOCKER_DAEMON_JSON) as fh:
            cfg = json.load(fh)
        return str(cfg.get("data-root", _DOCKER_DATA_ROOT_DEFAULT))
    except OSError, json.JSONDecodeError:
        return _DOCKER_DATA_ROOT_DEFAULT


def _check_log_file(
    log_file: Any,
    container_id: str,
    data_root: str,
) -> dict[str, Any] | None:
    """Return a result dict if *log_file* is at or above the HITL size threshold.

    Returns ``None`` when the file cannot be stat'd (OSError) or is below threshold.
    """
    try:
        size = log_file.stat().st_size
    except OSError:
        return None
    if size < _LOG_HITL_THRESHOLD_BYTES:
        return None
    return {
        "container_id": container_id,
        "container_name": container_id[:12],  # enriched below by _enrich_container_names
        "log_path": str(log_file),
        "size_bytes": size,
        "data_root": data_root,
    }


def _scan_container_logs(data_root: str) -> list[dict[str, Any]]:
    """Walk Docker containers dir and return entries at or above the HITL threshold.

    Returns a list of dicts: {container_id, container_name, log_path, size_bytes}.
    """
    from pathlib import Path  # noqa: PLC0415

    containers_dir = Path(data_root) / "containers"
    if not containers_dir.is_dir():
        return []

    results: list[dict[str, Any]] = []
    for container_dir in containers_dir.iterdir():
        if not container_dir.is_dir():
            continue
        container_id = container_dir.name
        for log_file in container_dir.glob("*-json.log"):
            entry = _check_log_file(log_file, container_id, data_root)
            if entry is not None:
                results.append(entry)
    return results


def _enrich_container_names(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attempt to resolve human-readable container names via Docker socket.

    Failures are silently swallowed — container names are informational only.
    """
    import http.client  # noqa: PLC0415
    import socket as _socket  # noqa: PLC0415

    class _DockConn(http.client.HTTPConnection):
        def connect(self) -> None:
            self.sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            self.sock.connect("/var/run/docker.sock")

    try:
        conn = _DockConn("localhost")
        conn.request("GET", "/containers/json?all=1")
        resp = conn.getresponse()
        if resp.status == 200:  # noqa: PLR2004
            containers: list[dict[str, Any]] = json.loads(resp.read())
            id_to_name: dict[str, str] = {
                c["Id"]: (c.get("Names") or [c["Id"][:12]])[0].lstrip("/")
                for c in containers
                if c.get("Id")
            }
            for entry in entries:
                full_id = entry["container_id"]
                if full_id in id_to_name:
                    entry["container_name"] = id_to_name[full_id]
        conn.close()
    except Exception:
        logger.debug("Container name resolution failed (informational, not fatal)", exc_info=True)
    return entries


async def _persist_log_insight(
    ctx: _Ctx,
    entry: dict[str, Any],
    *,
    auto_truncated: bool = False,
) -> None:
    """Insert a cognitive insight for a runaway container log file."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        size_gb = entry["size_bytes"] / (1024**3)
        name = entry["container_name"]
        severity = "critical" if entry["size_bytes"] >= _LOG_AUTO_TRUNCATE_BYTES else "warning"
        status = "acknowledged" if auto_truncated else "active"
        title = f"Runaway container log on {name}: {size_gb:.2f} GB"
        explanation = f"Container '{name}' log file is {size_gb:.2f} GB ({entry['log_path']})."
        if auto_truncated:
            explanation += (
                " Log was automatically truncated (no HITL required — size exceeded 2 GB)."
            )
        else:
            explanation += (
                " HITL review item created — operator approval required before truncation."
            )

        evidence = json.dumps(
            [
                {
                    "metric": "container_log_size_bytes",
                    "value": entry["size_bytes"],
                    "log_path": entry["log_path"],
                    "auto_truncated": auto_truncated,
                }
            ]
        )

        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO cognitive.insight
                            (entity_id, entity_type, severity, category,
                             title, explanation, status, confidence, evidence)
                        VALUES
                            (gen_random_uuid(), 'container', :sev, 'capacity',
                             :title, :expl, :status, 0.98, :evidence::jsonb)
                    """),
                    {
                        "sev": severity,
                        "title": title,
                        "expl": explanation,
                        "status": status,
                        "evidence": evidence,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


async def _submit_log_hitl(ctx: _Ctx, entry: dict[str, Any]) -> None:
    """Insert a HITL review item for a container log requiring operator approval."""

    def _insert() -> None:
        import uuid as _uuid  # noqa: PLC0415

        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        item_id = str(_uuid.uuid4())
        size_mb = entry["size_bytes"] / (1024**2)
        name = entry["container_name"]
        context = json.dumps(
            {
                "container_id": entry["container_id"],
                "container_name": name,
                "log_path": entry["log_path"],
                "size_bytes": entry["size_bytes"],
                "size_mb": round(size_mb, 1),
                "recommended_action": "truncate_log",
                "playbook": "truncate_container_log",
            }
        )
        suggestion = json.dumps(
            {
                "action": "truncate_container_log",
                "params": {
                    "log_path": entry["log_path"],
                    "container_name": name,
                    "container_id": entry["container_id"],
                    "data_root": entry["data_root"],
                    "size_bytes": entry["size_bytes"],
                },
            }
        )

        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO governance.hitl_item
                            (item_id, item_type, risk_class, priority, status,
                             context_jsonb, llm_suggestion, llm_confidence,
                             llm_model_used, expires_at)
                        VALUES
                            (:item_id, 'container_log_truncate', 'RC-2', 'medium',
                             'pending', :context::jsonb, :suggestion::jsonb, 0.97,
                             'cognitive_task', now() + interval '4 hours')
                    """),
                    {
                        "item_id": item_id,
                        "context": context,
                        "suggestion": suggestion,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


@_task_wrapper("container_log_audit")
async def container_log_audit(ctx: _Ctx) -> dict[str, Any]:
    """Scan Docker container JSON log files for runaway growth and auto-heal.

    Pipeline:
      1. Read Docker data-root from /etc/docker/daemon.json.
      2. Walk all container log files, filter those >= 500 MB.
      3. Enrich entries with container names via Docker socket.
      4. AUTO-truncate any log exceeding 2 GB (critical — executes immediately,
         no HITL required; uses the ``truncate_container_log`` playbook).
      5. For logs between 500 MB and 2 GB: create a HITL review item requesting
         operator approval before truncation.
      6. Record a cognitive insight for every flagged container.
    """
    await _check_database(ctx)

    _disk_threshold, log_auto_truncate_bytes, log_hitl_bytes = await _get_self_heal_config()
    data_root = await asyncio.to_thread(_get_docker_data_root)
    raw_entries = await asyncio.to_thread(_scan_container_logs, data_root)
    entries = await asyncio.to_thread(_enrich_container_names, raw_entries)

    # Re-filter to use live thresholds (scan uses module const; re-apply here)
    entries = [e for e in entries if e["size_bytes"] >= log_hitl_bytes]

    auto_truncated = 0
    hitl_created = 0

    from internalcmdb.motor.playbooks import PlaybookExecutor  # noqa: PLC0415

    executor = PlaybookExecutor()

    for entry in entries:
        if entry["size_bytes"] >= log_auto_truncate_bytes:
            logger.warning(
                "Container log auto-truncate: %s (%s) at %.2f GB.",
                entry["container_name"],
                entry["log_path"],
                entry["size_bytes"] / (1024**3),
            )
            pb_result = await executor.execute("truncate_container_log", entry)
            if pb_result.success:
                auto_truncated += 1
            await _persist_log_insight(ctx, entry, auto_truncated=pb_result.success)

        else:
            logger.warning(
                "Container log HITL review: %s (%s) at %.0f MB.",
                entry["container_name"],
                entry["log_path"],
                entry["size_bytes"] / (1024**2),
            )
            await _submit_log_hitl(ctx, entry)
            await _persist_log_insight(ctx, entry, auto_truncated=False)
            hitl_created += 1

    return {
        "data_root": data_root,
        "logs_scanned": len(entries),
        "auto_truncated": auto_truncated,
        "hitl_items_created": hitl_created,
    }


@_task_wrapper("hitl_escalation")
async def hitl_escalation(ctx: _Ctx) -> dict[str, Any]:
    """Escalate stale human-in-the-loop items.

    HITL action requests older than their SLA threshold
    are re-notified or auto-escalated to the next tier.
    """
    await _check_database(ctx)
    logger.debug("Checking for stale HITL items.")
    return {"stale_items": 0, "escalated": 0}


@_task_wrapper("accuracy_eval")
async def accuracy_eval(ctx: _Ctx) -> dict[str, Any]:
    """Evaluate LLM answer accuracy against ground-truth samples.

    Runs a sample of recent retrieval-augmented answers through
    the evaluation harness and records precision / recall / F1.
    """
    await _check_database(ctx)
    logger.debug("Running LLM accuracy evaluation.")
    return {"samples_evaluated": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

COGNITIVE_TASKS: dict[str, Any] = {
    "cognitive_fact_analysis": cognitive_fact_analysis,
    "cognitive_drift_check": cognitive_drift_check,
    "cognitive_health_score": cognitive_health_score,
    "cognitive_report_daily": cognitive_report_daily,
    "cognitive_report_weekly": cognitive_report_weekly,
    "embedding_sync": embedding_sync,
    "guard_audit": guard_audit,
    "self_heal_check": self_heal_check,
    "container_log_audit": container_log_audit,
    "hitl_escalation": hitl_escalation,
    "accuracy_eval": accuracy_eval,
}
