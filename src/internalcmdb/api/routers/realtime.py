"""Router: realtime — WebSocket streams and SSE for live data push."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_async_session
from ..middleware.rate_limit import limiter

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
    """Validate WS auth via query param token or first message.

    In dev mode (RBAC_DEV_MODE=true / ZITADEL_ISSUER unset), accepts all
    connections.  In production, checks the ``token`` query parameter.
    """
    from ..middleware.rbac import _DEV_MODE, _decode_jwt_claims  # noqa: PLC0415

    if _DEV_MODE:
        return True

    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing auth token")
        return False

    claims = _decode_jwt_claims(token)
    if not claims:
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
        elif hasattr(v, "__str__") and not isinstance(v, (str, int, float, bool, type(None), dict, list)):
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
                    result = await session.execute(text("""
                        SELECT
                            COUNT(*) FILTER (WHERE ca.status = 'online')  AS online,
                            COUNT(*) FILTER (WHERE ca.status = 'degraded') AS degraded,
                            COUNT(*) FILTER (WHERE ca.status = 'offline') AS offline,
                            COUNT(*) AS total
                        FROM collectors.collector_agent ca
                        WHERE ca.is_active = true
                    """))
                    row = result.fetchone()
                    data = _safe_json(row) if row else {"online": 0, "degraded": 0, "offline": 0, "total": 0}

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
        # ``asyncio.TimeoutError`` is ``TimeoutError`` ⊂ ``Exception`` (S5713).
        except Exception:
            pass

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


def _filter_new_insights(rows: list[Any], seen_ids: deque[str]) -> list[dict[str, Any]]:
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
                    result = await session.execute(text("""
                        SELECT insight_id, severity, category, title, description,
                               entity_id, entity_type, status, created_at
                        FROM cognitive.insight
                        WHERE status = 'active'
                        ORDER BY created_at DESC
                        LIMIT 20
                    """))
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
                    result = await session.execute(text("""
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
                    """))
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
@limiter.limit("10/minute")
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

                yield f"data: {json.dumps({'type': 'sources', 'sources': result.sources, 'confidence': result.confidence, 'tokens_used': result.tokens_used})}\n\n"
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
