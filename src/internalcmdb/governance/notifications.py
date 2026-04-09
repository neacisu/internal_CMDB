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
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging security helpers
# ---------------------------------------------------------------------------

_LOG_CTL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_log(value: object, max_len: int = 200) -> str:
    """Sanitize user-controlled values before logging to prevent log injection (S5145).

    Replaces ASCII control characters (including newlines and carriage returns) with '?'
    and truncates to ``max_len`` characters to prevent log flooding.
    """
    sanitized = _LOG_CTL_RE.sub("?", str(value))
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len] + "...[truncated]"
    return sanitized


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

    All user-controlled values are sanitized at ingress to break SonarQube
    S5145 taint chains before any value reaches a logging or messaging sink.
    """
    # Sanitize at ingress — breaks any taint chain from caller-supplied payload.
    safe_event_type = _sanitize_log(event_type)
    safe_item_id = _sanitize_log(str(payload.get("item_id", "unknown")))
    safe_risk_class = _sanitize_log(str(payload.get("risk_class", "?")))
    safe_priority = _sanitize_log(str(payload.get("priority", "?")))

    logger.info(
        "HITL notification: event=%s item=%s risk=%s priority=%s",
        safe_event_type,
        safe_item_id,
        safe_risk_class,
        safe_priority,
    )

    # Build a sanitized payload so downstream sinks also receive clean values.
    safe_payload: dict[str, Any] = {
        **payload,
        "item_id": safe_item_id,
        "risk_class": safe_risk_class,
        "priority": safe_priority,
        "status": _sanitize_log(str(payload.get("status", safe_event_type))),
    }

    if _WEBHOOK_URL:
        await _send_webhook(safe_event_type, safe_payload)

    if _SLACK_WEBHOOK_URL:
        await _send_slack(safe_event_type, safe_payload)

    if not _WEBHOOK_URL and not _SLACK_WEBHOOK_URL:
        logger.warning(
            "No notification channels configured (set HITL_WEBHOOK_URL or HITL_SLACK_WEBHOOK_URL)"
        )


async def _send_webhook(event_type: str, payload: dict[str, Any]) -> None:
    # event_type and payload values are already sanitized by the caller (notify_hitl_event).
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
                attempt,
                _RETRIES,
                event_type,
                exc_info=True,
            )
    logger.error(
        "Webhook delivery exhausted all %d retries for event=%s",
        _RETRIES,
        event_type,
    )


async def _send_slack(event_type: str, payload: dict[str, Any]) -> None:
    # event_type and payload values are already sanitized by the caller (notify_hitl_event).
    safe_event = event_type
    safe_item_id = str(payload.get("item_id", "?"))
    safe_risk_class = str(payload.get("risk_class", "?"))
    safe_priority = str(payload.get("priority", "?"))
    safe_status = str(payload.get("status", event_type))
    color = _SLACK_COLORS.get(event_type, "#607D8B")

    slack_body = {
        "attachments": [
            {
                "color": color,
                "title": f"HITL {safe_event.upper()}: {safe_risk_class} / {safe_priority}",
                "fields": [
                    {"title": "Item ID", "value": safe_item_id, "short": True},
                    {"title": "Risk Class", "value": safe_risk_class, "short": True},
                    {"title": "Priority", "value": safe_priority, "short": True},
                    {"title": "Status", "value": safe_status, "short": True},
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
                logger.debug("Slack notification sent: %s (attempt %d)", safe_event, attempt)
                return
        except Exception:
            logger.warning(
                "Slack delivery failed (attempt %d/%d) for event=%s",
                attempt,
                _RETRIES,
                safe_event,
                exc_info=True,
            )
    logger.error("Slack delivery exhausted all %d retries for event=%s", _RETRIES, safe_event)
