"""Router: metrics_live — live telemetry, GPU, LLM, and fleet health endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_async_session

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _row_to_dict(row: Any) -> dict[str, Any]:
    mapping = row._mapping
    return {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in mapping.items()}


def _add_staleness(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate each metric with age_seconds and a stale flag (>5 min = stale)."""
    now = datetime.now(UTC)
    for m in metrics:
        collected = m.get("collected_at")
        if collected:
            try:
                dt = datetime.fromisoformat(collected) if isinstance(collected, str) else collected
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                age = (now - dt).total_seconds()
                m["age_seconds"] = round(age, 1)
                m["stale"] = age > 300  # noqa: PLR2004
            except ValueError, TypeError:
                m["age_seconds"] = None
                m["stale"] = True
    return metrics


@router.get("/hosts/{code}/live")
async def host_metrics_live(
    code: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Snapshot of current metrics for a host."""
    result = await session.execute(
        text("""
            SELECT h.host_id, h.host_code, h.hostname
              FROM registry.host h
             WHERE h.host_code = :code
        """),
        {"code": code},
    )
    host_row = result.fetchone()
    if host_row is None:
        raise HTTPException(status_code=404, detail="Host not found")

    host = _row_to_dict(host_row)

    metrics_result = await session.execute(
        text("""
            SELECT DISTINCT ON (metric_name)
                   metric_name, metric_value, labels_jsonb, collected_at
              FROM telemetry.metric_point
             WHERE host_id = :host_id
             ORDER BY metric_name, collected_at DESC
        """),
        {"host_id": host["host_id"]},
    )
    metrics = _add_staleness([_row_to_dict(r) for r in metrics_result.fetchall()])

    return {"host": host, "metrics": metrics}


@router.get("/hosts/{code}/series")
async def host_metrics_series(
    code: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    metric_name: str = Query(..., description="Metric name to query"),
    limit: int = Query(500, ge=1, le=5000),
    before: str | None = Query(
        None, description="Cursor: return points collected before this ISO timestamp"
    ),
) -> dict[str, Any]:
    """Time series data for a specific metric on a host (cursor-paginated)."""
    result = await session.execute(
        text("SELECT host_id FROM registry.host WHERE host_code = :code"),
        {"code": code},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Host not found")

    host_id = row[0]

    if before:
        query = text("""
            SELECT metric_value, labels_jsonb, collected_at
              FROM telemetry.metric_point
             WHERE host_id = :host_id
               AND metric_name = :metric_name
               AND collected_at < :before
             ORDER BY collected_at DESC
             LIMIT :limit
        """)
        params: dict[str, Any] = {
            "host_id": str(host_id),
            "metric_name": metric_name,
            "limit": limit,
            "before": before,
        }
    else:
        query = text("""
            SELECT metric_value, labels_jsonb, collected_at
              FROM telemetry.metric_point
             WHERE host_id = :host_id
               AND metric_name = :metric_name
             ORDER BY collected_at DESC
             LIMIT :limit
        """)
        params = {"host_id": str(host_id), "metric_name": metric_name, "limit": limit}

    series_result = await session.execute(query, params)
    points = [_row_to_dict(r) for r in series_result.fetchall()]

    next_cursor = points[-1]["collected_at"] if points else None
    return {
        "host_code": code,
        "metric_name": metric_name,
        "points": points,
        "next_before": next_cursor,
    }


@router.get("/gpu/live")
async def gpu_live(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[dict[str, Any]]:
    """All GPU metrics across the fleet — latest snapshot per host."""
    result = await session.execute(
        text("""
            SELECT g.host_id, h.hostname, h.host_code,
                   g.gpu_index, g.model_name,
                   g.memory_total_mb, g.memory_used_mb,
                   g.utilization_gpu_pct, g.temperature_celsius,
                   g.power_draw_watts
              FROM registry.gpu_device g
              JOIN registry.host h ON h.host_id = g.host_id
             ORDER BY h.hostname, g.gpu_index
        """)
    )
    return [_row_to_dict(r) for r in result.fetchall()]


@router.get("/llm/live")
async def llm_live(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """LLM model latency, tokens, and queue depth from recent call logs."""
    result = await session.execute(
        text("""
            SELECT
                model_id,
                COUNT(*)                                              AS call_count,
                ROUND(AVG(latency_ms)::numeric, 2)                   AS avg_latency_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
                SUM(input_tokens)                                     AS total_input_tokens,
                SUM(output_tokens)                                    AS total_output_tokens,
                COUNT(*) FILTER (WHERE status != 'ok')                AS error_count
              FROM telemetry.llm_call_log
             WHERE called_at >= NOW() - INTERVAL '1 hour'
             GROUP BY model_id
             ORDER BY call_count DESC
        """)
    )
    models = [_row_to_dict(r) for r in result.fetchall()]
    return {"window": "1h", "models": models}


@router.get("/llm/calls")
async def llm_calls(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Last N LLM calls from the call log."""
    result = await session.execute(
        text("""
            SELECT call_id, correlation_id, model_id, endpoint,
                   input_tokens, output_tokens, latency_ms,
                   status, error_detail, called_at
              FROM telemetry.llm_call_log
             ORDER BY called_at DESC
             LIMIT :limit
        """),
        {"limit": limit},
    )
    return [_row_to_dict(r) for r in result.fetchall()]


@router.get("/fleet/matrix")
async def fleet_matrix(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    """Fleet health matrix — latest key metrics per host."""
    result = await session.execute(
        text("""
            WITH latest AS (
                SELECT DISTINCT ON (host_id, metric_name)
                       host_id, metric_name, metric_value, collected_at
                  FROM telemetry.metric_point
                 WHERE collected_at >= NOW() - INTERVAL '10 minutes'
                 ORDER BY host_id, metric_name, collected_at DESC
            )
            SELECT h.host_code, h.hostname,
                   jsonb_object_agg(l.metric_name, l.metric_value) AS metrics,
                   MAX(l.collected_at) AS last_seen
              FROM latest l
              JOIN registry.host h ON h.host_id = l.host_id
             GROUP BY h.host_code, h.hostname
             ORDER BY h.hostname
             LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = [_row_to_dict(r) for r in result.fetchall()]
    return {"hosts": rows, "total": len(rows), "limit": limit}
