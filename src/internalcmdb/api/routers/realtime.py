"""Router: realtime — WebSocket streams and SSE for live data push."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from internalcmdb.auth.revocation import is_revoked
from internalcmdb.auth.security import decode_access_token

from ..middleware import rbac as _rbac_module
from ..middleware.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])

_HEARTBEAT_INTERVAL = 30
_METRICS_PUSH_INTERVAL = 5
_EVENTS_PUSH_INTERVAL = 3
_INSIGHTS_PUSH_INTERVAL = 10
_HITL_PUSH_INTERVAL = 5
_MAX_SEEN_IDS = 500


# ---------------------------------------------------------------------------
# WS Auth
# ---------------------------------------------------------------------------


async def _authenticate_ws(ws: WebSocket) -> bool:
    """Validate WS auth via session cookie, query param token, or first message.

    In AUTH_DEV_MODE, accepts all connections.  In production, checks the
    ``cmdb_session`` cookie first, then the ``token`` query parameter.
    """
    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    if _rbac_module.AUTH_DEV_MODE:
        return True

    settings = get_settings()
    token: str | None = ws.cookies.get(settings.jwt_cookie_name)
    if not token:
        token = ws.query_params.get("token")

    if not token:
        await ws.close(code=4001, reason="Missing auth token")
        return False

    try:
        payload = decode_access_token(token)
        if is_revoked(payload.jti):
            await ws.close(code=4003, reason="Session revoked")
            return False
    except Exception:
        await ws.close(code=4003, reason="Invalid auth token")
        return False

    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _ws_heartbeat(ws: WebSocket) -> None:
    """Send periodic pings to keep the connection alive."""
    while True:
        try:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            await ws.send_json({"type": "ping", "ts": time.time()})
        except Exception:
            break


def _safe_json(row: Any) -> dict[str, Any]:
    mapping = row._mapping
    result: dict[str, Any] = {}
    for k, v in mapping.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif hasattr(v, "__str__") and not isinstance(
            v, (str, int, float, bool, type(None), dict, list)
        ):
            result[k] = str(v)
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# WS /ws/metrics — live fleet metrics
# ---------------------------------------------------------------------------


@router.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket) -> None:
    """Push fleet health metrics at regular intervals."""
    await ws.accept()
    if not await _authenticate_ws(ws):
        return
    heartbeat_task = asyncio.create_task(_ws_heartbeat(ws))

    try:
        while True:
            try:
                from ..deps import _get_async_session_factory  # noqa: PLC0415

                factory = _get_async_session_factory()
                async with factory() as session:
                    result = await session.execute(
                        text("""
                        SELECT
                            COUNT(*) FILTER (WHERE ca.status = 'online')  AS online,
                            COUNT(*) FILTER (WHERE ca.status = 'degraded') AS degraded,
                            COUNT(*) FILTER (WHERE ca.status = 'offline') AS offline,
                            COUNT(*) AS total
                        FROM collectors.collector_agent ca
                        WHERE ca.is_active = true
                    """)
                    )
                    row = result.fetchone()
                    data = (
                        _safe_json(row)
                        if row
                        else {"online": 0, "degraded": 0, "offline": 0, "total": 0}
                    )

                await ws.send_json({"type": "metrics", "data": data, "ts": time.time()})
            except WebSocketDisconnect:
                break
            except Exception:
                logger.debug("ws_metrics push error", exc_info=True)

            await asyncio.sleep(_METRICS_PUSH_INTERVAL)
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()


# ---------------------------------------------------------------------------
# WS /ws/events — EventBus tap with filters
# ---------------------------------------------------------------------------


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket) -> None:
    """Stream audit / governance events with optional filters."""
    await ws.accept()
    if not await _authenticate_ws(ws):
        return
    heartbeat_task = asyncio.create_task(_ws_heartbeat(ws))

    filters: dict[str, str] = {}

    try:
        # Accept initial filter configuration
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=2.0)
            filters = json.loads(raw)
        except Exception:
            logger.debug(
                "No WS filter message received within timeout, proceeding unfiltered",
                exc_info=True,
            )

        while True:
            try:
                from ..deps import _get_async_session_factory  # noqa: PLC0415

                factory = _get_async_session_factory()
                async with factory() as session:
                    q = """
                        SELECT event_id, event_type, actor, action,
                               entity_type, entity_id, risk_level, created_at
                        FROM audit.event_log
                        ORDER BY created_at DESC
                        LIMIT 20
                    """
                    result = await session.execute(text(q))
                    rows = [_safe_json(r) for r in result.fetchall()]

                event_type_filter = filters.get("event_type")
                if event_type_filter:
                    rows = [r for r in rows if r.get("event_type") == event_type_filter]

                await ws.send_json({"type": "events", "data": rows, "ts": time.time()})
            except WebSocketDisconnect:
                break
            except Exception:
                logger.debug("ws_events push error", exc_info=True)

            await asyncio.sleep(_EVENTS_PUSH_INTERVAL)
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()


# ---------------------------------------------------------------------------
# WS /ws/insights — new insights push
# ---------------------------------------------------------------------------


def _filter_new_insights(rows: Sequence[Any], seen_ids: deque[str]) -> list[dict[str, Any]]:
    """Return only insight rows not already seen, updating *seen_ids* in-place."""
    new_items: list[dict[str, Any]] = []
    for r in rows:
        d = _safe_json(r)
        iid = d.get("insight_id", "")
        if iid and iid not in seen_ids:
            seen_ids.append(iid)
            new_items.append(d)
    return new_items


@router.websocket("/ws/insights")
async def ws_insights(ws: WebSocket) -> None:
    """Push new cognitive insights as they appear."""
    await ws.accept()
    if not await _authenticate_ws(ws):
        return
    heartbeat_task = asyncio.create_task(_ws_heartbeat(ws))
    seen_ids: deque[str] = deque(maxlen=_MAX_SEEN_IDS)

    try:
        while True:
            try:
                from ..deps import _get_async_session_factory  # noqa: PLC0415

                factory = _get_async_session_factory()
                async with factory() as session:
                    result = await session.execute(
                        text("""
                        SELECT insight_id, severity, category, title, description,
                               entity_id, entity_type, status, created_at
                        FROM cognitive.insight
                        WHERE status = 'active'
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
                    )
                    rows = result.fetchall()

                new_items = _filter_new_insights(rows, seen_ids)
                if new_items:
                    await ws.send_json({"type": "insights", "data": new_items, "ts": time.time()})
                else:
                    await ws.send_json({"type": "heartbeat", "ts": time.time()})
            except WebSocketDisconnect:
                break
            except Exception:
                logger.debug("ws_insights push error", exc_info=True)

            await asyncio.sleep(_INSIGHTS_PUSH_INTERVAL)
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()


# ---------------------------------------------------------------------------
# WS /ws/hitl — new HITL items + countdown
# ---------------------------------------------------------------------------


@router.websocket("/ws/hitl")
async def ws_hitl(ws: WebSocket) -> None:
    """Push pending HITL items with expiry countdown."""
    await ws.accept()
    if not await _authenticate_ws(ws):
        return
    heartbeat_task = asyncio.create_task(_ws_heartbeat(ws))

    try:
        while True:
            try:
                from ..deps import _get_async_session_factory  # noqa: PLC0415

                factory = _get_async_session_factory()
                async with factory() as session:
                    result = await session.execute(
                        text("""
                        SELECT item_id, item_type, risk_class, priority,
                               status, llm_confidence, created_at, expires_at,
                               EXTRACT(EPOCH FROM (expires_at - NOW())) AS seconds_remaining
                        FROM governance.hitl_item
                        WHERE status IN ('pending', 'escalated')
                        ORDER BY
                            CASE priority
                                WHEN 'critical' THEN 1
                                WHEN 'high' THEN 2
                                WHEN 'medium' THEN 3
                                ELSE 4
                            END,
                            created_at ASC
                        LIMIT 50
                    """)
                    )
                    rows = [_safe_json(r) for r in result.fetchall()]

                await ws.send_json({"type": "hitl", "data": rows, "ts": time.time()})
            except WebSocketDisconnect:
                break
            except Exception:
                logger.debug("ws_hitl push error", exc_info=True)

            await asyncio.sleep(_HITL_PUSH_INTERVAL)
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()


# ---------------------------------------------------------------------------
# SSE /cognitive/chat/stream — chat streaming
# ---------------------------------------------------------------------------


@router.get("/cognitive/chat/stream")
@rate_limit("10/minute")
async def chat_stream(
    request: Request,
    question: str = Query(..., min_length=1, max_length=2000),
) -> StreamingResponse:
    """Server-Sent Events stream for cognitive chat responses."""

    async def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'question': question})}\n\n"

        try:
            from internalcmdb.cognitive.query_engine import QueryEngine  # noqa: PLC0415
            from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

            from ..deps import _get_async_session_factory  # noqa: PLC0415

            llm = LLMClient()
            factory = _get_async_session_factory()
            async with factory() as session:
                engine = QueryEngine(llm, session)
                result = await engine.query(question)

                # Stream the answer in chunks to simulate streaming
                words = result.answer.split()
                chunk_size = 5
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i : i + chunk_size])
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk + ' '})}\n\n"
                    await asyncio.sleep(0.05)

                _sources_payload = {
                    "type": "sources",
                    "sources": result.sources,
                    "confidence": result.confidence,
                    "tokens_used": result.tokens_used,
                }
                yield f"data: {json.dumps(_sources_payload)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# SSE /sse/vitals — real-time fleet vitals push
# ---------------------------------------------------------------------------

_VITALS_CHANNEL = "infraq:cmdb:vitals"
_SSE_VITALS_HEARTBEAT = 15  # seconds between keepalive pings
_SSE_RECONNECT_MS = 3_000  # browsers retry after 3 s on disconnect


def _auth_sse(request: Request) -> bool:
    """Validate SSE request via session cookie or ?token= query param.

    In AUTH_DEV_MODE, accepts all requests.
    """
    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    if _rbac_module.AUTH_DEV_MODE:
        return True

    settings = get_settings()
    token: str | None = request.cookies.get(settings.jwt_cookie_name)
    if not token:
        token = request.query_params.get("token")

    if not token:
        return False

    try:
        payload = decode_access_token(token)
        if is_revoked(payload.jti):
            return False
    except Exception:
        return False

    return True


async def _sse_fetch_payload(session: Any, agent_id: Any, kind: str) -> dict | None:
    """Fetch the most recent payload_jsonb for (agent_id, kind); returns None if absent."""
    from sqlalchemy import select  # noqa: PLC0415

    from internalcmdb.models.collectors import CollectorSnapshot  # noqa: PLC0415

    row = await session.execute(
        select(CollectorSnapshot.payload_jsonb)
        .where(
            CollectorSnapshot.agent_id == agent_id,
            CollectorSnapshot.snapshot_kind == kind,
        )
        .order_by(CollectorSnapshot.collected_at.desc())
        .limit(1)
    )
    val = row.scalar()
    return val if isinstance(val, dict) else None


async def _sse_vitals_initial_snapshot() -> list[dict]:
    """Fetch the current fleet vitals from the DB for the initial SSE snapshot."""
    try:
        from sqlalchemy import select  # noqa: PLC0415

        from internalcmdb.api.routers.collectors import (  # noqa: PLC0415
            _parse_vital_disk,
            _parse_vital_docker,
            _parse_vital_gpu,
        )
        from internalcmdb.collectors.fleet_health import derive_agent_status  # noqa: PLC0415
        from internalcmdb.models.collectors import (  # noqa: PLC0415
            CollectorAgent,
            CollectorSnapshot,
        )

        from ..deps import _get_async_session_factory  # noqa: PLC0415

        factory = _get_async_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(CollectorAgent).where(
                    CollectorAgent.is_active.is_(True),
                    CollectorAgent.status != "retired",
                )
            )
            agents = result.scalars().all()

            rows: list[dict] = []
            for agent in agents:
                sv_row = await session.execute(
                    select(CollectorSnapshot.payload_jsonb, CollectorSnapshot.collected_at)
                    .where(
                        CollectorSnapshot.agent_id == agent.agent_id,
                        CollectorSnapshot.snapshot_kind == "system_vitals",
                    )
                    .order_by(CollectorSnapshot.collected_at.desc())
                    .limit(1)
                )
                sv_first = sv_row.first()
                sv: dict = sv_first[0] if sv_first else {}

                disk_payload = await _sse_fetch_payload(session, agent.agent_id, "disk_state")
                gpu_payload = await _sse_fetch_payload(session, agent.agent_id, "gpu_state")
                docker_payload = await _sse_fetch_payload(session, agent.agent_id, "docker_state")

                mem = sv.get("memory_kb") or {}
                mem_total = float(mem.get("MemTotal") or 0)
                mem_avail = float(mem.get("MemAvailable") or mem.get("MemFree") or 0)
                mem_pct = (
                    round((mem_total - mem_avail) / mem_total * 100, 1) if mem_total > 0 else None
                )
                mem_total_gb = round(mem_total / (1024 * 1024), 1) if mem_total else None

                containers_total, containers_running = _parse_vital_docker(docker_payload)

                rows.append(
                    {
                        "agent_id": str(agent.agent_id),
                        "host_code": agent.host_code,
                        "status": derive_agent_status(agent),
                        "last_heartbeat_at": (
                            str(agent.last_heartbeat_at) if agent.last_heartbeat_at else None
                        ),
                        "load_avg": sv.get("load_avg", []),
                        "cpu_pct": sv.get("cpu_pct"),
                        "memory_pct": mem_pct,
                        "memory_total_gb": mem_total_gb,
                        "disk_root_pct": _parse_vital_disk(disk_payload),
                        "containers_running": containers_running,
                        "containers_total": containers_total,
                        "gpu_pct": _parse_vital_gpu(gpu_payload),
                        "vitals_at": str(sv_first[1]) if sv_first else None,
                    }
                )

            rows.sort(key=lambda x: str(x.get("host_code", "")))
            return rows
    except Exception:
        logger.debug("SSE vitals initial snapshot failed", exc_info=True)
        return []


@router.get("/sse/vitals")
async def sse_vitals(request: Request) -> StreamingResponse:
    """Server-Sent Events stream for real-time fleet vitals.

    Protocol:
    - ``event: snapshot`` — full array on connect and on periodic refresh
    - ``event: vital``    — single FleetVital object when any agent pushes new data
    - ``event: ping``     — keepalive every 15 s (no data payload)
    """
    if not _auth_sse(request):
        from fastapi.responses import PlainTextResponse  # noqa: PLC0415

        return PlainTextResponse("Unauthorized", status_code=401)  # type: ignore[return-value]

    async def event_generator():
        yield f"retry: {_SSE_RECONNECT_MS}\n\n"

        # ── Initial snapshot ──────────────────────────────────────────────
        snapshot = await _sse_vitals_initial_snapshot()
        yield f"event: snapshot\ndata: {json.dumps(snapshot)}\n\n"

        # ── Subscribe to Redis pub/sub ─────────────────────────────────────
        try:
            import redis.asyncio as _aioredis  # noqa: PLC0415
        except ImportError:
            logger.warning("redis.asyncio not available — SSE vitals stream closing")
            return

        from internalcmdb.api.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        r = _aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(_VITALS_CHANNEL)

        heartbeat_deadline = time.monotonic() + _SSE_VITALS_HEARTBEAT

        try:
            while True:
                if await request.is_disconnected():
                    break

                # Non-blocking read with 100 ms timeout so we can check disconnect
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if msg and msg.get("type") == "message":
                    yield f"event: vital\ndata: {msg['data']}\n\n"
                    heartbeat_deadline = time.monotonic() + _SSE_VITALS_HEARTBEAT

                if time.monotonic() >= heartbeat_deadline:
                    yield "event: ping\ndata: {}\n\n"
                    heartbeat_deadline = time.monotonic() + _SSE_VITALS_HEARTBEAT

                await asyncio.sleep(0)  # yield control to event loop
        finally:
            await pubsub.unsubscribe(_VITALS_CHANNEL)
            await pubsub.aclose()
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
