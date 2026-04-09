"""internalCMDB — Notification Dispatcher (Phase 4, F4.7).

Multi-channel notification system for HITL events and escalations.

Supported channels:
    - **webhook**: POST JSON payload to a configurable URL.
    - **email**: placeholder (logs intent; requires SMTP configuration).
    - **slack**: placeholder (logs intent; requires Slack webhook URL).

All channels implement retry logic with exponential backoff (max 3 attempts).

Public surface::

    from internalcmdb.motor.notifications import NotificationDispatcher

    dispatcher = NotificationDispatcher()
    ok = await dispatcher.notify(hitl_item, channel="webhook", config={"url": "..."})
    ok = await dispatcher.escalate_notify(hitl_item, escalation_level=2)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # seconds


# ---------------------------------------------------------------------------
# Channel notifiers
# ---------------------------------------------------------------------------


class WebhookNotifier:
    """Sends JSON payloads to an HTTP webhook endpoint."""

    async def send(self, payload: dict[str, Any], config: dict[str, Any]) -> bool:
        url = config.get("url")
        if not url:
            logger.warning("Webhook URL not configured — skipping notification")
            return False

        headers = {"Content-Type": "application/json"}
        extra_headers = config.get("headers")
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)

        timeout = float(config.get("timeout", 10))

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    logger.info("Webhook delivered to %s (attempt %d)", url, attempt)
                    return True
            except Exception:
                logger.warning(
                    "Webhook attempt %d/%d to %s failed",
                    attempt,
                    _MAX_RETRIES,
                    url,
                    exc_info=True,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_BACKOFF_BASE**attempt)

        logger.error("Webhook delivery to %s failed after %d attempts", url, _MAX_RETRIES)
        return False


class EmailNotifier:
    """Placeholder email notifier — logs the intent until SMTP is configured."""

    async def send(self, payload: dict[str, Any], config: dict[str, Any]) -> bool:
        await asyncio.sleep(0)
        to = config.get("to", "unspecified")
        subject = payload.get("subject", "HITL Notification")
        logger.info(
            "[EMAIL-PLACEHOLDER] Would send to=%s subject='%s' body_keys=%s",
            to,
            subject,
            list(payload.keys()),
        )
        return True


class SlackNotifier:
    """Placeholder Slack notifier — logs the intent until webhook URL is set."""

    async def send(self, payload: dict[str, Any], config: dict[str, Any]) -> bool:
        await asyncio.sleep(0)
        channel = config.get("channel", "#hitl-alerts")
        logger.info(
            "[SLACK-PLACEHOLDER] Would post to channel=%s text='%s'",
            channel,
            payload.get("text", "(no text)"),
        )
        return True


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_CHANNELS: dict[str, WebhookNotifier | EmailNotifier | SlackNotifier] = {
    "webhook": WebhookNotifier(),
    "email": EmailNotifier(),
    "slack": SlackNotifier(),
}


class NotificationDispatcher:
    """Routes notifications to the appropriate channel."""

    async def notify(
        self,
        hitl_item: dict[str, Any],
        channel: str,
        config: dict[str, Any],
    ) -> bool:
        """Send a notification for *hitl_item* over *channel*.

        Returns ``True`` on successful delivery, ``False`` on failure or
        unknown channel.
        """
        notifier = _CHANNELS.get(channel)
        if notifier is None:
            logger.error("Unknown notification channel: %s", channel)
            return False

        payload = _build_payload(hitl_item, event_type="hitl_notification")
        return await notifier.send(payload, config)

    async def escalate_notify(
        self,
        hitl_item: dict[str, Any],
        escalation_level: int,
    ) -> bool:
        """Send escalation notifications across all configured channels.

        Higher escalation levels trigger broader notification fanout:
            level 1  → webhook only
            level 2  → webhook + email
            level 3+ → webhook + email + slack
        """
        payload = _build_payload(hitl_item, event_type="hitl_escalation")
        payload["escalation_level"] = escalation_level

        channels_to_notify: list[str] = ["webhook"]
        if escalation_level >= 2:  # noqa: PLR2004
            channels_to_notify.append("email")
        if escalation_level >= 3:  # noqa: PLR2004
            channels_to_notify.append("slack")

        results: list[bool] = []
        for ch in channels_to_notify:
            notifier = _CHANNELS.get(ch)
            if notifier is None:
                continue
            config = _default_config_for(ch, hitl_item)
            ok = await notifier.send(payload, config)
            results.append(ok)

        return any(results)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_payload(hitl_item: dict[str, Any], *, event_type: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "item_id": str(hitl_item.get("item_id", "")),
        "item_type": hitl_item.get("item_type"),
        "risk_class": hitl_item.get("risk_class"),
        "priority": hitl_item.get("priority"),
        "status": hitl_item.get("status"),
        "subject": f"HITL {event_type}: {hitl_item.get('risk_class')} — {hitl_item.get('item_type')}",  # noqa: E501
        "text": (
            f"HITL item {hitl_item.get('item_id')} ({hitl_item.get('risk_class')}) "
            f"requires attention. Status: {hitl_item.get('status')}"
        ),
        "context": hitl_item.get("context_jsonb"),
    }


def _default_config_for(channel: str, hitl_item: dict[str, Any]) -> dict[str, Any]:
    """Return default configuration for a channel (from env or placeholders)."""
    import os  # noqa: PLC0415

    if channel == "webhook":
        return {"url": os.getenv("HITL_WEBHOOK_URL", "")}
    if channel == "email":
        default_to = os.getenv("HITL_EMAIL_TO", "platform-team@internal")
        to = hitl_item.get("notify_to") or hitl_item.get("assignee_email") or default_to
        return {"to": str(to) if to else default_to}
    if channel == "slack":
        ch = hitl_item.get("slack_channel") or os.getenv("HITL_SLACK_CHANNEL", "#hitl-alerts")
        return {"channel": str(ch)}
    return {}
