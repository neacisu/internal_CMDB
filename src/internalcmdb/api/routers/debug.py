"""Router: debug — traces, LLM calls, errors, slow queries, guard blocks, event bus stats.

All endpoints require ``platform_admin`` role.  The entire router can be
disabled by setting ``DEBUG_ENABLED=false`` in the environment.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_async_session
from ..middleware.rbac import require_role

_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/debug",
    tags=["debug"],
    dependencies=[Depends(require_role("platform_admin"))],
)

_SINCE_QUERY_DESCRIPTION = "ISO timestamp lower bound"


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TraceEntry(BaseModel):
    event_id: str | None = None
    event_type: str | None = None
    actor: str | None = None
    action: str | None = None
    correlation_id: str | None = None
    duration_ms: int | None = None
    status: str | None = None
    created_at: str | None = None


class LLMCallEntry(BaseModel):
    event_id: str | None = None
    model: str | None = None
    action: str | None = None
    status: str | None = None
    duration_ms: int | None = None
    correlation_id: str | None = None
    created_at: str | None = None


class ErrorEntry(BaseModel):
    event_id: str | None = None
    action: str | None = None
    status: str | None = None
    correlation_id: str | None = None
    severity: str | None = None
    created_at: str | None = None


class SlowQueryEntry(BaseModel):
    event_id: str | None = None
    action: str | None = None
    duration_ms: int | None = None
    correlation_id: str | None = None
    created_at: str | None = None


class GuardBlockEntry(BaseModel):
    item_id: str | None = None
    item_type: str | None = None
    risk_class: str | None = None
    status: str | None = None
    decision: str | None = None
    created_at: str | None = None


class EventBusStats(BaseModel):
    stream_count: int = 0
    total_events: int = 0
    consumer_groups: int = 0
    streams: list[dict[str, Any]] | None = None


class ReplayResult(BaseModel):
    correlation_id: str
    dry_run: bool = True
    events_found: int = 0
    events: list[dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: Any) -> dict[str, Any]:
    mapping = row._mapping
    return {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in mapping.items()}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/traces/{correlation_id}", response_model=list[TraceEntry])
async def get_traces(
    correlation_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[dict[str, Any]]:
    """Full cross-service trace for a correlation ID."""
    result = await session.execute(
        text("""
            SELECT event_id, event_type, actor, action,
                   correlation_id, duration_ms, status, created_at
              FROM governance.audit_event
             WHERE correlation_id = :cid
             ORDER BY created_at ASC
        """),
        {"cid": correlation_id},
    )
    rows = result.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="No traces found for correlation ID")
    return [_row_to_dict(r) for r in rows]


@router.get("/llm-calls", response_model=list[LLMCallEntry])
async def list_llm_calls(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    model: str | None = Query(None, description="Filter by model name"),
    status: str | None = Query(None, description="Filter by status"),
    since: str | None = Query(None, description=_SINCE_QUERY_DESCRIPTION),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """LLM calls recorded in audit_event with filters."""
    filters = ["event_type = 'llm_call'"]
    params: dict[str, Any] = {"lim": limit}

    if model:
        filters.append("action LIKE '%' || :model || '%'")
        params["model"] = model
    if status:
        filters.append("status = :status")
        params["status"] = status
    if since:
        filters.append("created_at >= :since::timestamptz")
        params["since"] = since

    where = " AND ".join(filters)
    result = await session.execute(
        text(f"""
            SELECT event_id, action AS model, action, status,
                   duration_ms, correlation_id, created_at
              FROM governance.audit_event
             WHERE {where}
             ORDER BY created_at DESC
             LIMIT :lim
        """),
        params,
    )
    return [_row_to_dict(r) for r in result.fetchall()]


@router.get("/errors", response_model=list[ErrorEntry])
async def list_errors(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    since: str | None = Query(None, description=_SINCE_QUERY_DESCRIPTION),
    severity: str | None = Query(None, description="Minimum severity (error, critical)"),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Aggregated errors from audit_event."""
    filters = ["status >= '400'"]
    params: dict[str, Any] = {"lim": limit}

    if since:
        filters.append("created_at >= :since::timestamptz")
        params["since"] = since
    if severity == "critical":
        filters.append("status >= '500'")

    where = " AND ".join(filters)
    result = await session.execute(
        text(f"""
            SELECT event_id, action, status, correlation_id,
                   CASE WHEN status::int >= 500 THEN 'critical'
                        WHEN status::int >= 400 THEN 'error'
                        ELSE 'warning'
                   END AS severity,
                   created_at
              FROM governance.audit_event
             WHERE {where}
             ORDER BY created_at DESC
             LIMIT :lim
        """),
        params,
    )
    return [_row_to_dict(r) for r in result.fetchall()]


@router.get("/slow-queries", response_model=list[SlowQueryEntry])
async def list_slow_queries(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    threshold_ms: int = Query(1000, ge=100, description="Minimum duration in ms"),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Slow DB/API queries exceeding the threshold."""
    result = await session.execute(
        text("""
            SELECT event_id, action, duration_ms, correlation_id, created_at
              FROM governance.audit_event
             WHERE duration_ms >= :threshold
             ORDER BY duration_ms DESC
             LIMIT :lim
        """),
        {"threshold": threshold_ms, "lim": limit},
    )
    return [_row_to_dict(r) for r in result.fetchall()]


@router.get("/guard-blocks", response_model=list[GuardBlockEntry])
async def list_guard_blocks(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    since: str | None = Query(None, description=_SINCE_QUERY_DESCRIPTION),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Guard decisions that blocked actions (HITL items with status='blocked')."""
    params: dict[str, Any] = {"lim": limit}
    since_filter = ""
    if since:
        since_filter = "AND created_at >= :since::timestamptz"
        params["since"] = since

    result = await session.execute(
        text(f"""
            SELECT item_id, item_type, risk_class, status,
                   decision, created_at
              FROM governance.hitl_item
             WHERE status IN ('blocked', 'rejected')
                   {since_filter}
             ORDER BY created_at DESC
             LIMIT :lim
        """),
        params,
    )
    return [_row_to_dict(r) for r in result.fetchall()]


@router.get("/event-bus/stats", response_model=EventBusStats)
async def event_bus_stats(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """EventBus statistics: stream lengths, consumer lag."""
    try:
        import redis.asyncio as aioredis  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            info = await r.info("stream")  # type: ignore[arg-type]
        except Exception:
            _logger.warning("Redis STREAM info unavailable", exc_info=True)
            info = {}

        streams: list[dict[str, Any]] = []
        stream_keys = [k for k in (info or {}) if isinstance(k, str)]

        return {
            "stream_count": len(stream_keys),
            "total_events": sum(
                info[k].get("length", 0) for k in stream_keys if isinstance(info.get(k), dict)
            ),
            "consumer_groups": sum(
                info[k].get("groups", 0) for k in stream_keys if isinstance(info.get(k), dict)
            ),
            "streams": streams,
        }
    except Exception:
        _logger.warning("event-bus stats failed", exc_info=True)
        return {
            "stream_count": 0,
            "total_events": 0,
            "consumer_groups": 0,
            "streams": None,
        }


@router.get("/replay/{correlation_id}", response_model=ReplayResult)
async def replay_request(
    correlation_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    """Replay a request by correlation ID (dry-run read-only view)."""
    result = await session.execute(
        text("""
            SELECT event_id, event_type, actor, action,
                   correlation_id, duration_ms, status, created_at
              FROM governance.audit_event
             WHERE correlation_id = :cid
             ORDER BY created_at ASC
             LIMIT :lim
        """),
        {"cid": correlation_id, "lim": limit},
    )
    rows = result.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="No events found for correlation ID")

    events = [_row_to_dict(r) for r in rows]
    return {
        "correlation_id": correlation_id,
        "dry_run": True,
        "events_found": len(events),
        "events": events,
    }
