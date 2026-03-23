"""internalCMDB — Governance Notification Dispatcher (Phase 4, F4.7).

Sends notifications for HITL events via configured channels:
    - Webhook (generic HTTP POST)
    - Slack (incoming webhook)
    - Log-only fallback (always active)

Configuration via environment variables::

    HITL_WEBHOOK_URL       — generic webhook endpoint
    HITL_SLACK_WEBHOOK_URL — Slack incoming webhook URL
    HITL_NOTIFY_RETRIES    — retry count on transient failures (default 2)
    HITL_NOTIFY_TIMEOUT    — HTTP timeout seconds (default 5)

Public surface::

    from internalcmdb.governance.notifications import notify_hitl_event

    await notify_hitl_event("escalated", {...})
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_WEBHOOK_URL = os.getenv("HITL_WEBHOOK_URL", "")
_SLACK_WEBHOOK_URL = os.getenv("HITL_SLACK_WEBHOOK_URL", "")
_RETRIES = int(os.getenv("HITL_NOTIFY_RETRIES", "2"))
_TIMEOUT = float(os.getenv("HITL_NOTIFY_TIMEOUT", "5"))

_SLACK_COLORS: dict[str, str] = {
    "submitted": "#2196F3",
    "escalated": "#FF9800",
    "blocked": "#F44336",
    "approved": "#4CAF50",
    "rejected": "#9E9E9E",
}


async def notify_hitl_event(
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Dispatch a HITL notification to all configured channels.

    Always logs the event.  Webhook/Slack failures are logged but never
    propagate — notification delivery is best-effort and must not block
    the governance pipeline.
    """
    item_id = payload.get("item_id", "unknown")
    risk_class = payload.get("risk_class", "?")
    priority = payload.get("priority", "?")

    logger.info(
        "HITL notification: event=%s item=%s risk=%s priority=%s",
        event_type, item_id, risk_class, priority,
    )

    if _WEBHOOK_URL:
        await _send_webhook(event_type, payload)

    if _SLACK_WEBHOOK_URL:
        await _send_slack(event_type, payload)

    if not _WEBHOOK_URL and not _SLACK_WEBHOOK_URL:
        logger.warning(
            "No notification channels configured "
            "(set HITL_WEBHOOK_URL or HITL_SLACK_WEBHOOK_URL)"
        )


async def _send_webhook(event_type: str, payload: dict[str, Any]) -> None:
    body = {"event": event_type, **payload}
    for attempt in range(1, _RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(_WEBHOOK_URL, json=body)
                resp.raise_for_status()
                logger.debug("Webhook delivered: %s (attempt %d)", event_type, attempt)
                return
        except Exception:
            logger.warning(
                "Webhook delivery failed (attempt %d/%d) for event=%s",
                attempt, _RETRIES, event_type,
                exc_info=True,
            )
    logger.error("Webhook delivery exhausted all %d retries for event=%s", _RETRIES, event_type)


async def _send_slack(event_type: str, payload: dict[str, Any]) -> None:
    item_id = payload.get("item_id", "?")
    risk_class = payload.get("risk_class", "?")
    priority = payload.get("priority", "?")
    status = payload.get("status", event_type)
    color = _SLACK_COLORS.get(event_type, "#607D8B")

    slack_body = {
        "attachments": [
            {
                "color": color,
                "title": f"HITL {event_type.upper()}: {risk_class} / {priority}",
                "fields": [
                    {"title": "Item ID", "value": str(item_id), "short": True},
                    {"title": "Risk Class", "value": risk_class, "short": True},
                    {"title": "Priority", "value": priority, "short": True},
                    {"title": "Status", "value": status, "short": True},
                ],
                "footer": "internalCMDB Guard Gate",
            }
        ]
    }

    for attempt in range(1, _RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(_SLACK_WEBHOOK_URL, json=slack_body)
                resp.raise_for_status()
                logger.debug("Slack notification sent: %s (attempt %d)", event_type, attempt)
                return
        except Exception:
            logger.warning(
                "Slack delivery failed (attempt %d/%d) for event=%s",
                attempt, _RETRIES, event_type,
                exc_info=True,
            )
    logger.error("Slack delivery exhausted all %d retries for event=%s", _RETRIES, event_type)
