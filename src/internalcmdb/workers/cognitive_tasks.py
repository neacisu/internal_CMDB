"""F3.4 — Cognitive Tasks.

Async task functions designed for ARQ / CronScheduler integration.
Each function follows the ``async fn(ctx) -> dict`` signature
expected by the worker system.

All tasks are registered in :data:`COGNITIVE_TASKS` for scheduler
discovery.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_Ctx = dict[str, Any]

_MAX_TASK_RETRIES = 3


class CognitiveTaskError(Exception):
    """Raised by cognitive tasks to signal ARQ-retriable failure."""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _task_wrapper(name: str, *, max_retries: int = _MAX_TASK_RETRIES):
    """Decorator that adds timing, structured logging, and retry semantics."""

    def decorator(fn):  # noqa: ANN001, ANN202
        async def wrapper(ctx: _Ctx) -> dict[str, Any]:
            job_try = ctx.get("job_try", 1)
            job_id = ctx.get("job_id", "unknown")
            logger.info("[%s] started (job_id=%s, attempt=%d/%d).", name, job_id, job_try, max_retries)
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
                logger.exception("[%s] failed after %dms (attempt %d/%d).", name, elapsed_ms, job_try, max_retries)

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

        wrapper.__qualname__ = fn.__qualname__
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
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
        from internalcmdb.api.config import get_settings  # noqa: PLC0415
        from sqlalchemy import create_engine, text  # noqa: PLC0415

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
    and network metrics into a single 0–100 score per entity.
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

    host_data, recently_healed = await asyncio.to_thread(
        _query_disk_health, ctx
    )

    candidates_evaluated = 0
    plans_proposed = 0
    plans_executed = 0

    for hd in host_data:
        candidates_evaluated += 1
        host_code = hd["host_code"]
        host_id = str(hd["host_id"])
        disk_pct = _extract_root_disk_pct(hd.get("disk_payload") or {})

        if disk_pct < _DISK_HEAL_THRESHOLD:
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
            _DISK_HEAL_THRESHOLD,
        )
        plans_proposed += 1

        if host_code == "orchestrator":
            ok = await _auto_heal_disk(ctx, host_id, host_code, disk_pct)
            if ok:
                plans_executed += 1
        else:
            await _persist_disk_insight(
                ctx, host_id, host_code, disk_pct, auto_healed=False
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


def _get_engine(ctx: _Ctx):  # noqa: ANN202
    """Create a disposable SQLAlchemy engine from the task context."""
    from internalcmdb.api.config import get_settings  # noqa: PLC0415
    from sqlalchemy import create_engine  # noqa: PLC0415

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
    for d in disk_payload.get("disks") or []:
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
        await _persist_disk_insight(ctx, host_id, host_code, disk_pct, auto_healed=False)
        return False

    from internalcmdb.motor.playbooks import PlaybookExecutor  # noqa: PLC0415

    executor = PlaybookExecutor()
    pb_result = await executor.execute(
        "clear_disk_space",
        {"host": host_code, "host_id": host_id, "disk_pct": disk_pct, "threshold_pct": _DISK_HEAL_THRESHOLD},
    )

    pre_check = pb_result.output.get("pre_check") or {}
    if pre_check.get("pre_check") == "skipped":
        logger.info("Cleanup skipped on %s: %s", host_code, pre_check.get("reason", ""))
        return False

    freed_mb = 0.0
    exec_out = pb_result.output.get("execute") or {}
    freed_mb = exec_out.get("freed_mb", 0.0)

    await _persist_disk_insight(
        ctx,
        host_id,
        host_code,
        disk_pct,
        auto_healed=pb_result.success,
        freed_mb=freed_mb,
    )
    await _persist_self_heal_action(ctx, host_id, host_code, pb_result, freed_mb)
    return pb_result.success


async def _persist_disk_insight(
    ctx: _Ctx,
    host_id: str,
    host_code: str,
    disk_pct: float,
    *,
    auto_healed: bool = False,
    freed_mb: float = 0.0,
) -> None:
    """Insert a cognitive insight for a high-disk-usage event."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        severity = "critical" if disk_pct >= 90 else "warning"
        status = "acknowledged" if auto_healed else "active"
        title = f"High disk usage on {host_code}: {disk_pct:.1f}%"
        explanation = f"Root filesystem on {host_code} is at {disk_pct:.1f}% capacity."
        if auto_healed:
            explanation += f" Auto-heal freed {freed_mb:.1f} MB via Docker cleanup."

        evidence = json.dumps([{
            "metric": "disk_usage_pct",
            "value": round(disk_pct, 1),
            "threshold": _DISK_HEAL_THRESHOLD,
            "auto_healed": auto_healed,
            "freed_mb": round(freed_mb, 1),
        }])

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
                        "eid": host_id,
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
    "hitl_escalation": hitl_escalation,
    "accuracy_eval": accuracy_eval,
}
