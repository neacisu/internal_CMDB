"""Router: events — Alertmanager webhook receiver for the nervous-system EventBus."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from internalcmdb.nervous.event_bus import Event, EventBus

from ..config import get_settings
from ..openapi_responses import RESP_400, RESP_403, merge_responses

router = APIRouter(prefix="/events", tags=["events"])

logger = logging.getLogger(__name__)

_STREAM_CONSCIOUSNESS_ALERT = "consciousness:alert"
_ALLOWED_CLIENTS = frozenset({"127.0.0.1", "::1"})


def _severity_to_risk_class(severity: str) -> str:
    normalized = severity.strip().lower()
    if normalized in {"critical", "security"}:
        return "RC-4"
    if normalized in {"warning", "governance"}:
        return "RC-3"
    if normalized == "info":
        return "RC-1"
    return "RC-2"


@router.post("/alert", include_in_schema=False, responses=merge_responses(RESP_403, RESP_400))
async def alertmanager_webhook(request: Request) -> dict[str, str]:
    """Receive Alertmanager webhook payloads and publish them to the EventBus."""
    client_host = request.client.host if request.client else ""
    if client_host not in _ALLOWED_CLIENTS:
        raise HTTPException(status_code=403, detail="Alert webhook restricted to localhost")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        raise HTTPException(status_code=400, detail="Missing alerts array")

    settings = get_settings()
    bus = EventBus(settings.redis_url)
    published = 0

    try:
        for alert in alerts:
            if not isinstance(alert, dict):
                continue

            labels = alert.get("labels") or {}
            if not isinstance(labels, dict):
                labels = {}

            severity = str(labels.get("severity", "info"))
            event = Event(
                event_type="alertmanager.alert",
                source="alertmanager",
                payload={
                    "status": alert.get("status"),
                    "labels": labels,
                    "annotations": alert.get("annotations") or {},
                    "starts_at": alert.get("startsAt"),
                    "ends_at": alert.get("endsAt"),
                    "fingerprint": alert.get("fingerprint"),
                    "generator_url": alert.get("generatorURL"),
                    "group_key": payload.get("groupKey"),
                    "receiver": payload.get("receiver"),
                    "external_url": payload.get("externalURL"),
                },
                risk_class=_severity_to_risk_class(severity),
            )
            await bus.publish(_STREAM_CONSCIOUSNESS_ALERT, event)
            published += 1
    finally:
        await bus.close()

    logger.info(
        "Alertmanager webhook accepted %d alert(s) from %s",
        published,
        client_host,
    )
    return {"status": "ok", "published": str(published)}
