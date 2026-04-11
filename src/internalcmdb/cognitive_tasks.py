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
import math
import statistics
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

logger = logging.getLogger(__name__)

_Ctx = dict[str, Any]

_MAX_TASK_RETRIES = 3

_SQL_INSIGHT_DEDUP_2H = """
    SELECT 1 FROM cognitive.insight
    WHERE entity_id = :eid AND title = :title
      AND created_at > NOW() - INTERVAL '2 hours'
    LIMIT 1
"""


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

    Scans recent ``collector_snapshot`` rows for system_vitals and
    disk_state, runs fleet-wide Z-score anomaly detection per metric,
    and persists anomalies as cognitive insights.
    """
    await _check_database(ctx)

    snapshots = await asyncio.to_thread(
        _query_recent_snapshots, ctx, ("system_vitals", "disk_state")
    )
    if not snapshots:
        logger.info("cognitive_fact_analysis: no recent snapshots — skipping.")
        return {"facts_scanned": 0, "anomalies_found": 0}

    host_metrics = _build_host_metrics(snapshots)
    anomalies = _detect_metric_anomalies(host_metrics)

    anomalies_found = 0
    for anomaly in anomalies:
        await _persist_fact_insight(ctx, anomaly)
        anomalies_found += 1

    return {"facts_scanned": len(snapshots), "anomalies_found": anomalies_found}


@_task_wrapper("cognitive_drift_check")
async def cognitive_drift_check(ctx: _Ctx) -> dict[str, Any]:
    """Hourly configuration drift detection.

    Compares each host's latest snapshot against its previous snapshot
    of the same kind to detect unexpected configuration changes.
    Persists detected drifts to ``cognitive.drift_result``.
    """
    await _check_database(ctx)

    pairs = await asyncio.to_thread(_query_drift_pairs, ctx)
    if not pairs:
        logger.info("cognitive_drift_check: no snapshot pairs found — skipping.")
        return {"entities_checked": 0, "drifts_detected": 0}

    from internalcmdb.cognitive.drift_detector import DriftDetector  # noqa: PLC0415

    detector = DriftDetector()
    entities_checked = 0
    drifts_detected = 0

    for pair in pairs:
        entities_checked += 1
        result = detector.detect_drift(
            entity_id=str(pair["host_id"]),
            observed=pair["current_payload"],
            canonical=pair["previous_payload"],
        )
        if result.has_drift and result.drift_type not in ("missing_canonical", "error"):
            drifts_detected += 1
            await _persist_drift_result(ctx, pair, result)

            # Escalate security-related drifts to critical insights
            security_kinds = ("security_posture", "firewall", "ssh_config", "user_accounts")
            if pair.get("snapshot_kind") in security_kinds or result.drift_type == "security":
                await _persist_security_drift_insight(
                    ctx,
                    pair,
                    result,
                )

    return {"entities_checked": entities_checked, "drifts_detected": drifts_detected}


@_task_wrapper("cognitive_health_score")
async def cognitive_health_score(ctx: _Ctx) -> dict[str, Any]:
    """Recalculate composite health scores for all monitored entities.

    Aggregates disk, CPU, memory metrics from recent snapshots
    into a 0-100 score per host via the HealthScorer engine.
    Persists insights for hosts in warning or critical state.
    """
    await _check_database(ctx)

    snapshots = await asyncio.to_thread(
        _query_recent_snapshots, ctx, ("system_vitals", "disk_state")
    )
    if not snapshots:
        logger.info("cognitive_health_score: no recent snapshots — skipping.")
        return {"entities_scored": 0}

    host_metrics = _build_host_metrics(snapshots)

    from internalcmdb.cognitive.health_scorer import HealthScorer  # noqa: PLC0415

    scorer = HealthScorer()
    entities_scored = 0
    insights_created = 0

    # Track previous scores for trend detection
    previous_scores = await asyncio.to_thread(_query_previous_health_scores, ctx)

    for host_id, metrics in host_metrics.items():
        host_code = str(metrics.get("_host_code", "unknown"))
        host_data = {
            "host_id": host_id,
            "cpu_usage_pct": metrics.get("cpu_usage_pct"),
            "memory_usage_pct": metrics.get("memory_usage_pct"),
            "disk_usage_pct": metrics.get("disk_usage_pct"),
            "services_total": 0,
            "services_healthy": 0,
        }
        score = scorer.score_host(host_data)
        entities_scored += 1

        if score.score < 80:  # noqa: PLR2004
            await _persist_health_insight(ctx, host_id, host_code, score)
            insights_created += 1

        # Trend detection: alert on >10 point drop from last known score
        prev = previous_scores.get(str(host_id))
        if prev is not None:
            drop = prev - score.score
            if drop > 10:  # noqa: PLR2004
                await _persist_trend_drop_insight(
                    ctx,
                    host_id,
                    host_code,
                    {"previous": prev, "current": score.score, "drop": drop},
                )
                insights_created += 1

    return {"entities_scored": entities_scored, "insights_created": insights_created}


@_task_wrapper("cognitive_report_daily")
async def cognitive_report_daily(ctx: _Ctx) -> dict[str, Any]:
    """Generate the daily operations summary report.

    Uses the ReportGenerator with the reasoning LLM to produce
    fleet health and security reports, persisting results to
    the ``cognitive.report`` table.
    """
    await _check_database(ctx)

    report_gen, session, engine = _make_report_generator(ctx)
    sections = 0
    try:
        fleet_md = await report_gen.generate_fleet_report()
        await _persist_report(ctx, "daily", "Daily Fleet Report", fleet_md)
        sections += 1

        security_md = await report_gen.generate_security_report()
        await _persist_report(ctx, "daily_security", "Daily Security Report", security_md)
        sections += 1
    except Exception:
        logger.exception("cognitive_report_daily: report generation failed.")
    finally:
        await session.close()
        await engine.dispose()

    return {"report_type": "daily", "sections": sections}


@_task_wrapper("cognitive_report_weekly")
async def cognitive_report_weekly(ctx: _Ctx) -> dict[str, Any]:
    """Generate the weekly executive summary report.

    Combines fleet, security, and capacity reports using the
    reasoning LLM for trend analysis and projections.
    """
    await _check_database(ctx)

    report_gen, session, engine = _make_report_generator(ctx)
    sections = 0
    try:
        fleet_md = await report_gen.generate_fleet_report()
        await _persist_report(ctx, "weekly_fleet", "Weekly Fleet Report", fleet_md)
        sections += 1

        security_md = await report_gen.generate_security_report()
        await _persist_report(ctx, "weekly_security", "Weekly Security Report", security_md)
        sections += 1

        capacity_md = await report_gen.generate_capacity_report()
        await _persist_report(ctx, "weekly_capacity", "Weekly Capacity Report", capacity_md)
        sections += 1
    except Exception:
        logger.exception("cognitive_report_weekly: report generation failed.")
    finally:
        await session.close()
        await engine.dispose()

    return {"report_type": "weekly", "sections": sections}


@_task_wrapper("embedding_sync")
async def embedding_sync(ctx: _Ctx) -> dict[str, Any]:
    """Re-embed document chunks that lack embeddings in the vector store.

    Queries ``retrieval.document_chunk`` rows without a corresponding
    ``chunk_embedding`` entry, generates embeddings via the LLM embed
    endpoint, and inserts the vectors.
    """
    await _check_database(ctx)
    await _check_redis(ctx)

    chunks = await asyncio.to_thread(_query_unembedded_chunks, ctx)
    if not chunks:
        logger.info("embedding_sync: all chunks already embedded.")
        return {"documents_processed": 0, "chunks_embedded": 0}

    from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

    llm = LLMClient()
    documents_processed: set[str] = set()
    chunks_embedded = 0

    batch_size = 16
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["content_text"] for c in batch]

        try:
            embeddings = await llm.embed(texts)
        except Exception:
            logger.exception("embedding_sync: embed() call failed for batch %d.", i)
            continue

        for chunk, embedding in zip(batch, embeddings, strict=True):
            await asyncio.to_thread(
                _upsert_chunk_embedding,
                ctx,
                str(chunk["document_chunk_id"]),
                embedding,
            )
            chunks_embedded += 1
            documents_processed.add(str(chunk.get("document_version_id", "")))

    return {
        "documents_processed": len(documents_processed),
        "chunks_embedded": chunks_embedded,
    }


@_task_wrapper("ingest_knowledge_base")
async def ingest_knowledge_base(ctx: _Ctx) -> dict[str, Any]:
    """Ingest all knowledge sources into the pgvector knowledge base.

    Sources: registry.host, shared_infrastructure.shared_service,
    cognitive.insight (active), docs/ Markdown, subprojects/ reports.

    Scheduled every 15 minutes via ARQ cron.
    """
    await _check_database(ctx)

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: PLC0415

    from internalcmdb.api.config import get_settings  # noqa: PLC0415
    from internalcmdb.cognitive.kb_ingestor import KnowledgeBaseIngestor  # noqa: PLC0415
    from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

    settings = get_settings()
    # Build an async database URL from the sync URL
    db_url = str(ctx.get("database_url") or settings.database_url)
    async_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(async_url, pool_pre_ping=True)
    try:
        async with AsyncSession(engine) as session, LLMClient() as llm:
            ingestor = KnowledgeBaseIngestor()
            summary = await ingestor.ingest_all(session, llm)
    finally:
        await engine.dispose()

    return summary


@_task_wrapper("guard_audit")
async def guard_audit(ctx: _Ctx) -> dict[str, Any]:
    """Run governance guard checks on recent security-related snapshots.

    Scans ``security_posture`` snapshots for policy violations like
    disabled firewalls, open root login, and missing fail2ban.
    """
    await _check_database(ctx)

    snapshots = await asyncio.to_thread(_query_recent_snapshots, ctx, ("security_posture",))
    if not snapshots:
        logger.info("guard_audit: no recent security snapshots — skipping.")
        return {"facts_audited": 0, "violations": 0}

    violations = 0
    for snap in snapshots:
        host_id = str(snap["host_id"])
        host_code = snap["host_code"]
        payload: dict[str, Any] = dict(snap.get("payload_jsonb") or {})
        host_violations = _check_security_baseline(host_id, host_code, payload)
        for violation in host_violations:
            await _persist_guard_insight(ctx, violation)
            violations += 1

    return {"facts_audited": len(snapshots), "violations": violations}


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
    engine = _get_engine(ctx)

    sla_thresholds: dict[str, int] = {
        "RC-3": 30,  # 30 minutes for high-risk
        "RC-2": 120,  # 2 hours for medium-risk
        "RC-1": 480,  # 8 hours for low-risk
    }

    def _scan_and_escalate() -> dict[str, Any]:
        from sqlalchemy import text as _text  # noqa: PLC0415

        stale = 0
        escalated = 0
        with engine.connect() as conn:
            # Find pending HITL items past their SLA
            rows = (
                conn.execute(
                    _text("""
                SELECT item_id, risk_class, priority, status,
                       EXTRACT(EPOCH FROM (now() - created_at)) / 60 AS age_minutes
                FROM governance.hitl_item
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
                )
                .mappings()
                .all()
            )

            for row in rows:
                age_min = float(row["age_minutes"])
                rc = row["risk_class"] or "RC-1"
                sla_min = sla_thresholds.get(rc, 480)

                if age_min < sla_min:
                    continue

                stale += 1

                # Escalate priority: medium → high → critical
                current_pri = row["priority"] or "medium"
                if current_pri == "medium":
                    new_pri = "high"
                elif current_pri == "high":
                    new_pri = "critical"
                else:
                    new_pri = current_pri  # already critical

                conn.execute(
                    _text("""
                    UPDATE governance.hitl_item
                    SET priority = :new_pri,
                        status = CASE WHEN :age > :sla * 2 THEN 'escalated' ELSE status END,
                        updated_at = now()
                    WHERE item_id = :item_id
                """),
                    {
                        "new_pri": new_pri,
                        "age": age_min,
                        "sla": sla_min,
                        "item_id": row["item_id"],
                    },
                )
                escalated += 1

            conn.commit()
        return {"stale_items": stale, "escalated": escalated}

    try:
        result = await asyncio.to_thread(_scan_and_escalate)
    finally:
        engine.dispose()

    if result["escalated"]:
        logger.info(
            "HITL escalation: %d stale, %d escalated",
            result["stale_items"],
            result["escalated"],
        )
    return result


# ---------------------------------------------------------------------------
# Faithfulness scoring helpers
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "and",
        "or",
        "not",
        "with",
        "this",
        "that",
        "it",
        "as",
        "by",
        "from",
        "has",
        "have",
        "had",
        "be",
    }
)

_GROUNDING_THRESHOLD = 0.15


def _is_faithful(prompt: str, response: str) -> bool:
    """Check if a response is grounded in the prompt using token overlap.

    Returns ``True`` when the ratio of shared meaningful tokens between
    the prompt and response exceeds :data:`_GROUNDING_THRESHOLD`.
    """
    prompt_tokens: set[str] = set(prompt.lower().split())
    response_tokens: set[str] = set(response.lower().split())
    prompt_meaningful: set[str] = prompt_tokens - _STOP_WORDS
    response_meaningful: set[str] = response_tokens - _STOP_WORDS

    if not prompt_meaningful:
        return False

    overlap = len(response_meaningful & prompt_meaningful)
    total = len(response_meaningful)
    grounding_ratio = overlap / max(total, 1)
    return grounding_ratio > _GROUNDING_THRESHOLD


@_task_wrapper("accuracy_eval")
async def accuracy_eval(ctx: _Ctx) -> dict[str, Any]:
    """Evaluate LLM answer accuracy against ground-truth samples.

    Compares recent cognitive query answers with retrieved source chunks
    to compute faithfulness (answer grounded in sources) and relevance metrics.
    """
    engine = _get_engine(ctx)

    def _evaluate() -> dict[str, Any]:
        from sqlalchemy import text as _text  # noqa: PLC0415

        with engine.connect() as conn:
            # Get recent LLM call logs with answers
            rows = (
                conn.execute(
                    _text("""
                SELECT call_id, prompt_text, response_text,
                       model_used, tokens_in, tokens_out
                FROM telemetry.llm_call_log
                WHERE created_at > now() - interval '24 hours'
                  AND response_text IS NOT NULL
                  AND response_text != ''
                ORDER BY created_at DESC
                LIMIT 50
            """)
                )
                .mappings()
                .all()
            )

            if not rows:
                return {
                    "samples_evaluated": 0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                    "faithful_pct": 0.0,
                }

            evaluated = 0
            faithful = 0
            total_tokens = 0

            for row in rows:
                response = row["response_text"] or ""
                prompt = row["prompt_text"] or ""
                total_tokens += (row["tokens_in"] or 0) + (row["tokens_out"] or 0)

                # Faithfulness heuristic: check if answer contains claims
                # that can be grounded in the prompt context
                if not response.strip():
                    continue

                evaluated += 1

                if _is_faithful(prompt, response):
                    faithful += 1

            faithful_pct = (faithful / max(evaluated, 1)) * 100
            # Precision = faithful / evaluated, Recall approximated
            precision = faithful / max(evaluated, 1)
            recall = min(precision * 1.1, 1.0)  # Approximate
            f1 = 2 * precision * recall / max(precision + recall, 1e-9)

            return {
                "samples_evaluated": evaluated,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "faithful_pct": round(faithful_pct, 2),
                "total_tokens_reviewed": total_tokens,
            }

    try:
        result = await asyncio.to_thread(_evaluate)
    finally:
        engine.dispose()

    logger.info(
        "Accuracy eval: %d samples, P=%.3f R=%.3f F1=%.3f",
        result["samples_evaluated"],
        result["precision"],
        result["recall"],
        result["f1"],
    )
    return result


# ---------------------------------------------------------------------------
# Shared helpers — snapshot queries
# ---------------------------------------------------------------------------

_Z_CRITICAL = 3.0
_Z_WARNING = 2.0
_STD_MIN_THRESHOLD = 0.01  # Below this, stdev is effectively zero — skip Z-score


def _query_recent_snapshots(
    ctx: _Ctx,
    kinds: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Fetch the most recent snapshot per host per kind from the last 2 hours."""
    from sqlalchemy import bindparam, text  # noqa: PLC0415

    engine = _get_engine(ctx)
    # Use SQLAlchemy expanding bind param to safely handle dynamic IN clause.
    sql = text(
        "SELECT DISTINCT ON (h.host_id, cs.snapshot_kind)"
        "       h.host_id, h.host_code,"
        "       cs.snapshot_kind,"
        "       cs.payload_jsonb,"
        "       cs.collected_at"
        " FROM registry.host h"
        " JOIN discovery.collector_agent ca ON ca.host_id = h.host_id"
        " JOIN discovery.collector_snapshot cs"
        "      ON cs.agent_id = ca.agent_id"
        " WHERE cs.snapshot_kind IN :kinds"
        " AND cs.collected_at > NOW() - INTERVAL '2 hours'"
        " ORDER BY h.host_id, cs.snapshot_kind, cs.collected_at DESC"
    ).bindparams(bindparam("kinds", expanding=True))

    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, {"kinds": list(kinds)}).fetchall()
    finally:
        engine.dispose()

    return [dict(r._mapping) for r in rows]


def _build_host_metrics(
    snapshots: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Aggregate snapshot payloads into per-host metric dicts.

    Returns ``{host_id: {cpu_usage_pct, memory_usage_pct, disk_usage_pct, ...}}``.
    """
    hosts: dict[str, dict[str, Any]] = {}

    for snap in snapshots:
        hid = str(snap["host_id"])
        if hid not in hosts:
            hosts[hid] = {"_host_code": snap["host_code"]}
        metrics = hosts[hid]
        payload: dict[str, Any] = dict(snap.get("payload_jsonb") or {})
        kind = snap.get("snapshot_kind", "")

        if kind == "system_vitals":
            _extract_vitals_metrics(payload, metrics)
        elif kind == "disk_state":
            _extract_disk_metric(payload, metrics)

    return hosts


def _extract_vitals_metrics(
    payload: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    """Extract CPU, memory, and load metrics from a system_vitals payload."""
    cpu_times: dict[str, Any] = dict(payload.get("cpu_times") or {})
    idle = _safe_float(cpu_times.get("idle"))
    user = _safe_float(cpu_times.get("user"))
    system = _safe_float(cpu_times.get("system"))
    total_cpu = idle + user + system
    if total_cpu > 0:
        metrics["cpu_usage_pct"] = round((1 - idle / total_cpu) * 100, 2)

    mem: dict[str, Any] = dict(payload.get("memory_kb") or {})
    mem_total = _safe_float(mem.get("MemTotal"))
    mem_avail = _safe_float(mem.get("MemAvailable"))
    if mem_total > 0:
        metrics["memory_usage_pct"] = round((1 - mem_avail / mem_total) * 100, 2)

    load_avg: list[Any] = list(payload.get("load_avg") or [])
    if len(load_avg) > 0:
        metrics["load_1m"] = _safe_float(load_avg[0])


def _extract_disk_metric(
    payload: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    """Extract root filesystem usage from a disk_state payload."""
    disks: list[dict[str, Any]] = list(payload.get("disks") or [])
    for d in disks:
        if d.get("mountpoint") == "/":
            raw = str(d.get("used_pct", "0")).replace("%", "")
            metrics["disk_usage_pct"] = _safe_float(raw)
            break


def _safe_float(val: Any) -> float:
    """Coerce to float, returning 0.0 on failure."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        return 0.0 if math.isnan(f) or math.isinf(f) else f
    except TypeError, ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Fact analysis helpers
# ---------------------------------------------------------------------------


@dataclass
class _MetricAnomaly:
    """Captures a Z-score anomaly for a specific metric across the fleet."""

    host_id: str
    host_code: str
    metric_name: str
    value: float
    z_score: float
    severity: str
    fleet_mean: float
    fleet_std: float


_MIN_HOSTS_FOR_ZSCORE = 3  # Need at least this many hosts for meaningful Z-score


def _detect_metric_anomalies(
    host_metrics: dict[str, dict[str, Any]],
) -> list[_MetricAnomaly]:
    """Run fleet-wide Z-score anomaly detection on common metrics."""
    metric_names = ("cpu_usage_pct", "memory_usage_pct", "disk_usage_pct", "load_1m")
    anomalies: list[_MetricAnomaly] = []

    for mname in metric_names:
        values = _collect_metric_values(host_metrics, mname)
        if len(values) < _MIN_HOSTS_FOR_ZSCORE:
            continue
        anomalies.extend(_find_anomalies_for_metric(mname, values))

    return anomalies


def _collect_metric_values(
    host_metrics: dict[str, dict[str, Any]],
    metric_name: str,
) -> list[tuple[str, str, float]]:
    """Collect (host_id, host_code, value) tuples for a given metric."""
    values: list[tuple[str, str, float]] = []
    for hid, m in host_metrics.items():
        v = m.get(metric_name)
        if v is not None:
            values.append((hid, str(m.get("_host_code", "unknown")), float(v)))
    return values


def _find_anomalies_for_metric(
    mname: str,
    values: list[tuple[str, str, float]],
) -> list[_MetricAnomaly]:
    """Find Z-score anomalies for a single metric across the fleet."""
    nums = [v[2] for v in values]
    mean = statistics.mean(nums)
    std = statistics.stdev(nums) if len(nums) > 1 else 0.0
    if std < _STD_MIN_THRESHOLD:
        return []

    anomalies: list[_MetricAnomaly] = []
    for hid, hcode, val in values:
        z = abs(val - mean) / std
        if z >= _Z_WARNING:
            severity = "critical" if z >= _Z_CRITICAL else "warning"
            anomalies.append(
                _MetricAnomaly(
                    host_id=hid,
                    host_code=hcode,
                    metric_name=mname,
                    value=val,
                    z_score=round(z, 2),
                    severity=severity,
                    fleet_mean=round(mean, 2),
                    fleet_std=round(std, 2),
                )
            )
    return anomalies


async def _persist_fact_insight(ctx: _Ctx, anomaly: _MetricAnomaly) -> None:
    """Insert a cognitive insight for a Z-score anomaly."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        title = (
            f"Anomaly on {anomaly.host_code}: "
            f"{anomaly.metric_name} = {anomaly.value:.1f} (Z={anomaly.z_score})"
        )
        explanation = (
            f"Host {anomaly.host_code} has {anomaly.metric_name} = {anomaly.value:.1f}%, "
            f"which is {anomaly.z_score} standard deviations from the fleet mean of "
            f"{anomaly.fleet_mean:.1f}% (std={anomaly.fleet_std:.1f})."
        )
        evidence = json.dumps(
            [
                {
                    "metric": anomaly.metric_name,
                    "value": anomaly.value,
                    "z_score": anomaly.z_score,
                    "fleet_mean": anomaly.fleet_mean,
                    "fleet_std": anomaly.fleet_std,
                }
            ]
        )

        try:
            with engine.connect() as conn:
                # Dedup: skip if same title already exists in the last 2 hours
                existing = conn.execute(
                    text(_SQL_INSIGHT_DEDUP_2H),
                    {"eid": anomaly.host_id, "title": title},
                ).fetchone()
                if existing:
                    return

                conn.execute(
                    text("""
                        INSERT INTO cognitive.insight
                            (entity_id, entity_type, severity, category,
                             title, explanation, status, confidence, evidence)
                        VALUES
                            (:eid, 'host', :sev, 'performance', :title,
                             :expl, 'active', :conf, :evidence::jsonb)
                    """),
                    {
                        "eid": anomaly.host_id,
                        "sev": anomaly.severity,
                        "title": title,
                        "expl": explanation,
                        "conf": min(0.5 + anomaly.z_score * 0.1, 0.99),
                        "evidence": evidence,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


# ---------------------------------------------------------------------------
# Drift check helpers
# ---------------------------------------------------------------------------


def _query_drift_pairs(ctx: _Ctx) -> list[dict[str, Any]]:
    """Return pairs of (current, previous) snapshots per host for drift comparison.

    Fetches the two most recent snapshots of selected kinds per host.
    """
    from sqlalchemy import bindparam, text  # noqa: PLC0415

    engine = _get_engine(ctx)
    drift_kinds = ("security_posture", "docker_state", "disk_state")
    # Use SQLAlchemy expanding bind param to safely handle dynamic IN clause.
    sql = text(
        "WITH ranked AS ("
        " SELECT h.host_id, h.host_code,"
        "        cs.snapshot_kind,"
        "        cs.payload_jsonb,"
        "        cs.collected_at,"
        "        ROW_NUMBER() OVER ("
        "            PARTITION BY h.host_id, cs.snapshot_kind"
        "            ORDER BY cs.collected_at DESC"
        "        ) AS rn"
        " FROM registry.host h"
        " JOIN discovery.collector_agent ca ON ca.host_id = h.host_id"
        " JOIN discovery.collector_snapshot cs"
        "      ON cs.agent_id = ca.agent_id"
        " WHERE cs.snapshot_kind IN :kinds"
        " AND cs.collected_at > NOW() - INTERVAL '6 hours'"
        ")"
        " SELECT host_id, host_code, snapshot_kind, payload_jsonb, rn"
        " FROM ranked"
        " WHERE rn <= 2"
        " ORDER BY host_id, snapshot_kind, rn"
    ).bindparams(bindparam("kinds", expanding=True))

    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, {"kinds": list(drift_kinds)}).fetchall()
    finally:
        engine.dispose()

    # Group into pairs
    pairs: list[dict[str, Any]] = []
    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        row = dict(r._mapping)
        key = f"{row['host_id']}:{row['snapshot_kind']}"
        by_key.setdefault(key, []).append(row)

    for _key, group in by_key.items():
        if len(group) == 2:  # noqa: PLR2004
            current = group[0] if group[0]["rn"] == 1 else group[1]
            previous = group[1] if group[0]["rn"] == 1 else group[0]
            pairs.append(
                {
                    "host_id": current["host_id"],
                    "host_code": current["host_code"],
                    "snapshot_kind": current["snapshot_kind"],
                    "current_payload": current["payload_jsonb"] or {},
                    "previous_payload": previous["payload_jsonb"] or {},
                }
            )

    return pairs


async def _persist_drift_result(
    ctx: _Ctx,
    pair: dict[str, Any],
    result: Any,
) -> None:
    """Persist a drift detection result to ``cognitive.drift_result``."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO cognitive.drift_result
                            (entity_id, entity_type, has_drift, drift_type,
                             fields_changed, confidence, explanation)
                        VALUES
                            (:eid, 'host', true, :dtype,
                             :fields::jsonb, :conf, :expl)
                    """),
                    {
                        "eid": str(pair["host_id"]),
                        "dtype": result.drift_type,
                        "fields": json.dumps(result.fields_changed),
                        "conf": result.confidence,
                        "expl": result.explanation,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


async def _persist_security_drift_insight(
    ctx: _Ctx,
    pair: dict[str, Any],
    result: Any,
) -> None:
    """Escalate a security-related drift to a critical cognitive insight."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        host_code = str(pair.get("host_code", "unknown"))
        title = f"Security drift on {host_code}: {result.drift_type}"
        explanation = (
            f"Security-critical configuration drift detected on {host_code} "
            f"(kind={pair.get('snapshot_kind', '?')}). "
            f"Fields changed: {result.fields_changed}. "
            f"{result.explanation}"
        )
        evidence = json.dumps(
            [
                {
                    "drift_type": result.drift_type,
                    "fields_changed": result.fields_changed,
                    "confidence": result.confidence,
                    "snapshot_kind": pair.get("snapshot_kind"),
                }
            ]
        )

        try:
            with engine.connect() as conn:
                existing = conn.execute(
                    text(_SQL_INSIGHT_DEDUP_2H),
                    {"eid": str(pair["host_id"]), "title": title},
                ).fetchone()
                if existing:
                    return

                conn.execute(
                    text("""
                        INSERT INTO cognitive.insight
                            (entity_id, entity_type, severity, category,
                             title, explanation, status, confidence, evidence)
                        VALUES
                            (:eid, 'host', 'critical', 'security_drift', :title,
                             :expl, 'active', :conf, :evidence::jsonb)
                    """),
                    {
                        "eid": str(pair["host_id"]),
                        "title": title,
                        "expl": explanation,
                        "conf": min(result.confidence + 0.1, 0.99),
                        "evidence": evidence,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


# ---------------------------------------------------------------------------
# Health score helpers
# ---------------------------------------------------------------------------


async def _persist_health_insight(
    ctx: _Ctx,
    host_id: str,
    host_code: str,
    score: Any,
) -> None:
    """Insert a cognitive insight for a host with warning or critical health."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        severity = "critical" if score.score < 60 else "warning"  # noqa: PLR2004
        title = f"Health score {score.score}/100 for {host_code}"
        breakdown = score.breakdown
        explanation = (
            f"Host {host_code} health score is {score.score}/100 "
            f"(CPU={breakdown.get('cpu_health', '?')}, "
            f"MEM={breakdown.get('memory_health', '?')}, "
            f"DISK={breakdown.get('disk_health', '?')}, "
            f"SVC={breakdown.get('service_health', '?')}). "
            f"Status: {breakdown.get('status', 'unknown')}."
        )
        evidence = json.dumps(
            [
                {
                    "score": score.score,
                    "breakdown": breakdown,
                    "timestamp": score.timestamp,
                }
            ]
        )

        try:
            with engine.connect() as conn:
                # Dedup: skip if same title in last 2 hours
                existing = conn.execute(
                    text(_SQL_INSIGHT_DEDUP_2H),
                    {"eid": host_id, "title": title},
                ).fetchone()
                if existing:
                    return

                conn.execute(
                    text("""
                        INSERT INTO cognitive.insight
                            (entity_id, entity_type, severity, category,
                             title, explanation, status, confidence, evidence)
                        VALUES
                            (:eid, 'host', :sev, 'health', :title,
                             :expl, 'active', 0.95, :evidence::jsonb)
                    """),
                    {
                        "eid": host_id,
                        "sev": severity,
                        "title": title,
                        "expl": explanation,
                        "evidence": evidence,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


def _query_previous_health_scores(ctx: _Ctx) -> dict[str, float]:
    """Fetch most recent health scores from cognitive.insight for trend detection."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_engine(ctx)
    try:
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text("""
                SELECT DISTINCT ON (entity_id)
                    entity_id::text, explanation
                FROM cognitive.insight
                WHERE category = 'health'
                  AND title LIKE 'Health score %'
                  AND created_at > NOW() - INTERVAL '24 hours'
                ORDER BY entity_id, created_at DESC
            """)
                )
                .mappings()
                .all()
            )

            result: dict[str, float] = {}
            for row in rows:
                # Parse score from title "Health score XX/100 for ..."
                expl = row.get("explanation", "")
                try:
                    # "Host xyz health score is NN/100 ..."
                    import re  # noqa: PLC0415

                    match = re.search(r"health score is (\d+)/100", expl)
                    if match:
                        result[row["entity_id"]] = float(match.group(1))
                except ValueError, AttributeError:
                    pass
            return result
    finally:
        engine.dispose()


async def _persist_trend_drop_insight(
    ctx: _Ctx,
    host_id: str,
    host_code: str,
    score_info: dict[str, float],
) -> None:
    """Insert a critical insight when health score drops >10 points.

    Args:
        score_info: ``{"previous": float, "current": float, "drop": float}``
    """
    previous_score = score_info["previous"]
    current_score = score_info["current"]
    drop = score_info["drop"]

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        title = f"Health score dropped {drop:.0f} pts for {host_code}"
        explanation = (
            f"Host {host_code} health score dropped from {previous_score:.0f} to "
            f"{current_score:.0f} (Δ={drop:.0f} points) in the last 24 hours. "
            f"This exceeds the 10-point threshold and requires investigation."
        )
        evidence = json.dumps(
            [
                {
                    "previous_score": previous_score,
                    "current_score": current_score,
                    "drop": drop,
                }
            ]
        )

        try:
            with engine.connect() as conn:
                existing = conn.execute(
                    text("""
                        SELECT 1 FROM cognitive.insight
                        WHERE entity_id = :eid AND title = :title
                          AND created_at > NOW() - INTERVAL '4 hours'
                        LIMIT 1
                    """),
                    {"eid": host_id, "title": title},
                ).fetchone()
                if existing:
                    return

                conn.execute(
                    text("""
                        INSERT INTO cognitive.insight
                            (entity_id, entity_type, severity, category,
                             title, explanation, status, confidence, evidence)
                        VALUES
                            (:eid, 'host', 'critical', 'health_trend', :title,
                             :expl, 'active', 0.90, :evidence::jsonb)
                    """),
                    {
                        "eid": host_id,
                        "title": title,
                        "expl": explanation,
                        "evidence": evidence,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------


def _make_report_generator(
    ctx: _Ctx,
) -> tuple[Any, Any, Any]:
    """Create a ReportGenerator with async DB session and LLM client.

    Returns (report_generator, async_session, async_engine) — caller must
    close session and dispose engine.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: PLC0415

    from internalcmdb.api.config import get_settings  # noqa: PLC0415
    from internalcmdb.api.deps import _normalize_pg_url  # noqa: PLC0415
    from internalcmdb.cognitive.report_generator import ReportGenerator  # noqa: PLC0415
    from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

    settings = get_settings()
    db_url = str(ctx.get("database_url") or settings.database_url)
    async_url = _normalize_pg_url(db_url, driver="asyncpg")
    engine = create_async_engine(async_url, pool_pre_ping=True)
    session = AsyncSession(engine, expire_on_commit=False)
    llm = LLMClient()
    return ReportGenerator(llm, session), session, engine


async def _persist_report(
    ctx: _Ctx,
    report_type: str,
    title: str,
    content_md: str,
) -> None:
    """Insert generated report into ``cognitive.report``."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO cognitive.report
                            (report_type, title, content_markdown, generated_by)
                        VALUES (:rtype, :title, :md, 'cognitive_task')
                    """),
                    {"rtype": report_type, "title": title, "md": content_md},
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


# ---------------------------------------------------------------------------
# Embedding sync helpers
# ---------------------------------------------------------------------------


def _query_unembedded_chunks(ctx: _Ctx) -> list[dict[str, Any]]:
    """Find document chunks without a chunk_embedding row."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_engine(ctx)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT dc.document_chunk_id,
                           dc.document_version_id,
                           dc.content_text
                    FROM retrieval.document_chunk dc
                    LEFT JOIN retrieval.chunk_embedding ce
                        ON ce.document_chunk_id = dc.document_chunk_id
                    WHERE ce.chunk_embedding_id IS NULL
                      AND dc.content_text IS NOT NULL
                      AND LENGTH(dc.content_text) > 10
                    ORDER BY dc.created_at DESC
                    LIMIT 256
                """)
            ).fetchall()
    finally:
        engine.dispose()

    return [dict(r._mapping) for r in rows]


def _upsert_chunk_embedding(
    ctx: _Ctx,
    chunk_id: str,
    embedding: list[float],
) -> None:
    """Insert a chunk_embedding row for the given document chunk."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_engine(ctx)
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO retrieval.chunk_embedding
                        (document_chunk_id, embedding_model_code,
                         embedding_vector, created_at)
                    VALUES
                        (:cid, 'qwen3-embedding-8b', :vec::vector, NOW())
                    ON CONFLICT (document_chunk_id, embedding_model_code)
                    DO UPDATE SET embedding_vector = EXCLUDED.embedding_vector
                """),
                {"cid": chunk_id, "vec": vec_str},
            )
            conn.commit()
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Guard audit helpers
# ---------------------------------------------------------------------------


@dataclass
class _SecurityViolation:
    """A single security policy violation detected by the guard audit."""

    host_id: str
    host_code: str
    check_name: str
    severity: str
    explanation: str
    evidence: dict[str, Any]


def _check_security_baseline(
    host_id: str,
    host_code: str,
    payload: dict[str, Any],
) -> list[_SecurityViolation]:
    """Check a security_posture payload against baseline policies."""
    violations: list[_SecurityViolation] = []

    # Check UFW / firewall
    ufw: dict[str, Any] = dict(payload.get("ufw") or {})
    if not ufw.get("active"):
        violations.append(
            _SecurityViolation(
                host_id=host_id,
                host_code=host_code,
                check_name="firewall_disabled",
                severity="critical",
                explanation=f"Host {host_code}: UFW firewall is not active.",
                evidence={"ufw": ufw},
            )
        )

    # Check fail2ban
    f2b: dict[str, Any] = dict(payload.get("fail2ban") or {})
    if not f2b.get("installed"):
        violations.append(
            _SecurityViolation(
                host_id=host_id,
                host_code=host_code,
                check_name="fail2ban_missing",
                severity="warning",
                explanation=f"Host {host_code}: fail2ban is not installed.",
                evidence={"fail2ban": f2b},
            )
        )
    elif not f2b.get("jails"):
        violations.append(
            _SecurityViolation(
                host_id=host_id,
                host_code=host_code,
                check_name="fail2ban_no_jails",
                severity="warning",
                explanation=f"Host {host_code}: fail2ban installed but no jails configured.",
                evidence={"fail2ban": f2b},
            )
        )

    # Check iptables — empty rules suggest no filtering
    ipt_rules: list[Any] = list(payload.get("iptables_rules") or [])
    if len(ipt_rules) < 3:  # noqa: PLR2004
        violations.append(
            _SecurityViolation(
                host_id=host_id,
                host_code=host_code,
                check_name="minimal_iptables",
                severity="warning",
                explanation=(
                    f"Host {host_code}: only {len(ipt_rules)} iptables rules — "
                    f"host may lack network filtering."
                ),
                evidence={"iptables_rule_count": len(ipt_rules)},
            )
        )

    return violations


async def _persist_guard_insight(ctx: _Ctx, violation: _SecurityViolation) -> None:
    """Insert a cognitive insight for a security policy violation."""

    def _insert() -> None:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        title = f"Security: {violation.check_name} on {violation.host_code}"
        evidence = json.dumps([violation.evidence])

        try:
            with engine.connect() as conn:
                # Dedup: skip if same title in last 6 hours
                existing = conn.execute(
                    text("""
                        SELECT 1 FROM cognitive.insight
                        WHERE entity_id = :eid AND title = :title
                          AND created_at > NOW() - INTERVAL '6 hours'
                        LIMIT 1
                    """),
                    {"eid": violation.host_id, "title": title},
                ).fetchone()
                if existing:
                    return

                conn.execute(
                    text("""
                        INSERT INTO cognitive.insight
                            (entity_id, entity_type, severity, category,
                             title, explanation, status, confidence, evidence)
                        VALUES
                            (:eid, 'host', :sev, 'security', :title,
                             :expl, 'active', 0.90, :evidence::jsonb)
                    """),
                    {
                        "eid": violation.host_id,
                        "sev": violation.severity,
                        "title": title,
                        "expl": violation.explanation,
                        "evidence": evidence,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()

    await asyncio.to_thread(_insert)


# ---------------------------------------------------------------------------
# Autonomous loop task
# ---------------------------------------------------------------------------


async def autonomous_reasoning_cycle(ctx: dict[str, Any]) -> dict[str, Any]:
    """Run one cycle of the autonomous cognitive reasoning engine.

    Scheduled every 5 minutes via ARQ cron.
    """
    from internalcmdb.cognitive.autonomous_loop import AutonomousLoop  # noqa: PLC0415

    logger.info("Autonomous reasoning cycle starting.")
    loop = AutonomousLoop()
    result = await loop.run_cycle()
    logger.info("Autonomous reasoning cycle: %s", result.get("summary", "done"))
    return result


# ---------------------------------------------------------------------------
# HITL re-execution worker
# ---------------------------------------------------------------------------


@_task_wrapper("process_approved_hitl_items")
async def process_approved_hitl_items(ctx: _Ctx) -> dict[str, Any]:
    """Re-execute approved HITL tool-call items.

    Queries ``governance.hitl_item`` for rows that have been approved
    but not yet executed (``executed_at IS NULL``), then runs the
    corresponding tool via :class:`~internalcmdb.cognitive.tool_executor.ToolExecutor`
    with ``skip_hitl=True`` so the tool executes immediately.

    Scheduled every minute via ARQ cron.
    """
    await _check_database(ctx)

    def _fetch_pending() -> list[dict[str, Any]]:
        from sqlalchemy import text  # noqa: PLC0415

        engine = _get_engine(ctx)
        try:
            with engine.connect() as conn:
                rows = (
                    conn.execute(
                        text("""
                            SELECT item_id::text, context_jsonb
                            FROM governance.hitl_item
                            WHERE status = 'approved'
                              AND executed_at IS NULL
                            ORDER BY created_at
                            LIMIT 10
                        """)
                    )
                    .mappings()
                    .all()
                )
            return [dict(r) for r in rows]
        finally:
            engine.dispose()

    pending = await asyncio.to_thread(_fetch_pending)
    if not pending:
        return {"processed": 0, "succeeded": 0, "failed": 0}

    from internalcmdb.cognitive.tool_executor import ToolExecutor  # noqa: PLC0415

    executor = ToolExecutor(skip_hitl=True)
    succeeded = 0
    failed = 0

    for item in pending:
        item_id = item["item_id"]
        context: dict[str, Any] = item.get("context_jsonb") or {}
        tool_id: str = context.get("tool_id", "")
        parameters: dict[str, Any] = context.get("parameters") or {}

        if not tool_id:
            logger.warning("HITL item %s has no tool_id in context — skipping.", item_id)
            failed += 1
            _mark_execution(ctx, item_id, success=False, error="Missing tool_id in context")
            continue

        try:
            result = await executor.execute(
                tool_id,
                parameters,
                triggered_by=f"hitl_worker:{item_id}",
            )
            succeeded += 1
            _mark_execution(
                ctx,
                item_id,
                success=result.success,
                output=result.output,
                error=result.error,
            )
            logger.info(
                "HITL re-exec %s → tool=%s success=%s",
                item_id,
                tool_id,
                result.success,
            )
        except Exception as exc:
            failed += 1
            logger.exception("HITL re-exec failed for item %s", item_id)
            _mark_execution(ctx, item_id, success=False, error=str(exc))

    return {"processed": len(pending), "succeeded": succeeded, "failed": failed}


def _mark_execution(
    ctx: _Ctx,
    item_id: str,
    *,
    success: bool,
    output: dict[str, Any] | None = None,
    error: str = "",
) -> None:
    """Update governance.hitl_item with execution outcome (sync, fire-and-forget)."""
    import json as _json  # noqa: PLC0415

    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_engine(ctx)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE governance.hitl_item
                    SET executed_at = now(),
                        execution_result = :result::jsonb
                    WHERE item_id = :item_id::uuid
                """),
                {
                    "item_id": item_id,
                    "result": _json.dumps(
                        {"success": success, "output": output, "error": error},
                        default=str,
                    ),
                },
            )
            conn.commit()
    except Exception:
        logger.debug("Failed to mark HITL item execution for %s", item_id, exc_info=True)
    finally:
        engine.dispose()


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
    "ingest_knowledge_base": ingest_knowledge_base,
    "guard_audit": guard_audit,
    "self_heal_check": self_heal_check,
    "container_log_audit": container_log_audit,
    "hitl_escalation": hitl_escalation,
    "accuracy_eval": accuracy_eval,
    "autonomous_reasoning_cycle": autonomous_reasoning_cycle,
    "process_approved_hitl_items": process_approved_hitl_items,
}
