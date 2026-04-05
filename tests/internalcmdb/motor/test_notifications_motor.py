"""Tests for internalcmdb.motor.notifications."""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.motor.notifications import (
    EmailNotifier,
    NotificationDispatcher,
    SlackNotifier,
    WebhookNotifier,
    _build_payload,
    _default_config_for,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hitl_item(
    item_id: str = "item-001",
    item_type: str = "action_review",
    risk_class: str = "RC-3",
    priority: str = "high",
    status: str = "pending",
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "item_type": item_type,
        "risk_class": risk_class,
        "priority": priority,
        "status": status,
        "context_jsonb": {"plan_id": "plan-42"},
    }


# ---------------------------------------------------------------------------
# Tests: WebhookNotifier
# ---------------------------------------------------------------------------


class TestWebhookNotifier:
    @pytest.mark.asyncio
    async def test_webhook_no_url_returns_false(self) -> None:
        notifier = WebhookNotifier()
        result = await notifier.send({"key": "value"}, config={})
        assert result is False

    @pytest.mark.asyncio
    async def test_webhook_no_url_key_returns_false(self) -> None:
        notifier = WebhookNotifier()
        result = await notifier.send({"key": "value"}, config={"url": ""})
        assert result is False

    @pytest.mark.asyncio
    async def test_webhook_success_returns_true(self) -> None:
        notifier = WebhookNotifier()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("internalcmdb.motor.notifications.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await notifier.send(
                {"event": "test"},
                config={"url": "http://hook.example.com/notify"},
            )

        assert result is True
        mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_webhook_retry_on_failure_returns_false(self) -> None:
        notifier = WebhookNotifier()

        with patch("internalcmdb.motor.notifications.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("internalcmdb.motor.notifications.asyncio.sleep", new=AsyncMock()):
                result = await notifier.send(
                    {"event": "test"},
                    config={"url": "http://hook.example.com/notify"},
                )

        assert result is False
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_webhook_uses_custom_headers(self) -> None:
        notifier = WebhookNotifier()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("internalcmdb.motor.notifications.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await notifier.send(
                {"event": "test"},
                config={
                    "url": "http://hook.example.com/notify",
                    "headers": {"Authorization": "Bearer token123"},
                },
            )

        assert result is True
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer token123"

    @pytest.mark.asyncio
    async def test_webhook_http_error_triggers_retry(self) -> None:
        notifier = WebhookNotifier()
        import httpx as httpx_module

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx_module.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=MagicMock(),
        )

        with patch("internalcmdb.motor.notifications.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("internalcmdb.motor.notifications.asyncio.sleep", new=AsyncMock()):
                result = await notifier.send(
                    {"event": "test"},
                    config={"url": "http://hook.example.com/notify"},
                )

        assert result is False


# ---------------------------------------------------------------------------
# Tests: EmailNotifier
# ---------------------------------------------------------------------------


class TestEmailNotifier:
    @pytest.mark.asyncio
    async def test_email_placeholder_returns_true(self) -> None:
        notifier = EmailNotifier()
        result = await notifier.send(
            {"subject": "HITL alert", "body": "details"},
            config={"to": "team@example.com"},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_email_unspecified_to_still_returns_true(self) -> None:
        notifier = EmailNotifier()
        result = await notifier.send({"subject": "Test"}, config={})
        assert result is True


# ---------------------------------------------------------------------------
# Tests: SlackNotifier
# ---------------------------------------------------------------------------


class TestSlackNotifier:
    @pytest.mark.asyncio
    async def test_slack_placeholder_returns_true(self) -> None:
        notifier = SlackNotifier()
        result = await notifier.send(
            {"text": "HITL item needs review"},
            config={"channel": "#ops-alerts"},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_slack_no_channel_still_returns_true(self) -> None:
        notifier = SlackNotifier()
        result = await notifier.send({"text": "Test notification"}, config={})
        assert result is True


# ---------------------------------------------------------------------------
# Tests: _build_payload
# ---------------------------------------------------------------------------


class TestBuildPayload:
    def test_build_payload_structure(self) -> None:
        item = _make_hitl_item()
        payload = _build_payload(item, event_type="hitl_notification")

        assert payload["event_type"] == "hitl_notification"
        assert payload["item_id"] == "item-001"
        assert payload["item_type"] == "action_review"
        assert payload["risk_class"] == "RC-3"
        assert payload["priority"] == "high"
        assert payload["status"] == "pending"

    def test_build_payload_subject_format(self) -> None:
        item = _make_hitl_item(risk_class="RC-4", item_type="emergency_action")
        payload = _build_payload(item, event_type="hitl_escalation")

        assert "RC-4" in payload["subject"]
        assert "emergency_action" in payload["subject"]

    def test_build_payload_text_contains_item_id(self) -> None:
        item = _make_hitl_item(item_id="item-999")
        payload = _build_payload(item, event_type="hitl_notification")

        assert "item-999" in payload["text"]

    def test_build_payload_context_preserved(self) -> None:
        item = _make_hitl_item()
        item["context_jsonb"] = {"plan_id": "plan-007"}
        payload = _build_payload(item, event_type="hitl_notification")

        assert payload["context"] == {"plan_id": "plan-007"}

    def test_build_payload_escalation_event_type(self) -> None:
        item = _make_hitl_item()
        payload = _build_payload(item, event_type="hitl_escalation")

        assert payload["event_type"] == "hitl_escalation"


# ---------------------------------------------------------------------------
# Tests: _default_config_for
# ---------------------------------------------------------------------------


class TestDefaultConfigFor:
    def test_webhook_uses_env_variable(self) -> None:
        item = _make_hitl_item()

        with patch.dict(os.environ, {"HITL_WEBHOOK_URL": "http://env-hook.example.com/"}):
            config = _default_config_for("webhook", item)

        assert config["url"] == "http://env-hook.example.com/"

    def test_webhook_empty_when_no_env(self) -> None:
        item = _make_hitl_item()

        env = {k: v for k, v in os.environ.items() if k != "HITL_WEBHOOK_URL"}
        with patch.dict(os.environ, env, clear=True):
            config = _default_config_for("webhook", item)

        assert "url" in config

    def test_email_uses_item_notify_to(self) -> None:
        item = _make_hitl_item()
        item["notify_to"] = "ops-lead@example.com"

        config = _default_config_for("email", item)

        assert config["to"] == "ops-lead@example.com"

    def test_email_falls_back_to_env(self) -> None:
        item = _make_hitl_item()

        with patch.dict(os.environ, {"HITL_EMAIL_TO": "platform@example.com"}):
            config = _default_config_for("email", item)

        assert config["to"] == "platform@example.com"

    def test_slack_uses_item_slack_channel(self) -> None:
        item = _make_hitl_item()
        item["slack_channel"] = "#custom-channel"

        config = _default_config_for("slack", item)

        assert config["channel"] == "#custom-channel"

    def test_slack_falls_back_to_default(self) -> None:
        item = _make_hitl_item()
        env = {k: v for k, v in os.environ.items() if k != "HITL_SLACK_CHANNEL"}

        with patch.dict(os.environ, env, clear=True):
            config = _default_config_for("slack", item)

        assert "channel" in config

    def test_unknown_channel_returns_empty_dict(self) -> None:
        item = _make_hitl_item()
        config = _default_config_for("sms", item)
        assert config == {}


# ---------------------------------------------------------------------------
# Tests: NotificationDispatcher
# ---------------------------------------------------------------------------


class TestNotificationDispatcher:
    @pytest.mark.asyncio
    async def test_dispatcher_unknown_channel_returns_false(self) -> None:
        dispatcher = NotificationDispatcher()
        item = _make_hitl_item()

        result = await dispatcher.notify(item, channel="unknown_channel", config={})

        assert result is False

    @pytest.mark.asyncio
    async def test_dispatcher_notify_webhook_calls_send(self) -> None:
        dispatcher = NotificationDispatcher()
        item = _make_hitl_item()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("internalcmdb.motor.notifications.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await dispatcher.notify(
                item,
                channel="webhook",
                config={"url": "http://hook.example.com/notify"},
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_dispatcher_email_returns_true(self) -> None:
        dispatcher = NotificationDispatcher()
        item = _make_hitl_item()

        result = await dispatcher.notify(item, channel="email", config={"to": "ops@example.com"})

        assert result is True

    @pytest.mark.asyncio
    async def test_dispatcher_slack_returns_true(self) -> None:
        dispatcher = NotificationDispatcher()
        item = _make_hitl_item()

        result = await dispatcher.notify(item, channel="slack", config={"channel": "#alerts"})

        assert result is True


# ---------------------------------------------------------------------------
# Tests: escalate_notify
# ---------------------------------------------------------------------------


class TestEscalateNotify:
    @pytest.mark.asyncio
    async def test_escalate_level1_only_webhook(self) -> None:
        dispatcher = NotificationDispatcher()
        item = _make_hitl_item()

        from internalcmdb.motor.notifications import _CHANNELS
        original_webhook = _CHANNELS["webhook"]
        original_email = _CHANNELS["email"]
        original_slack = _CHANNELS["slack"]
        _CHANNELS["webhook"] = MagicMock()
        _CHANNELS["webhook"].send = AsyncMock(return_value=True)
        _CHANNELS["email"] = MagicMock()
        _CHANNELS["email"].send = AsyncMock(return_value=True)
        _CHANNELS["slack"] = MagicMock()
        _CHANNELS["slack"].send = AsyncMock(return_value=True)

        try:
            with patch.dict(os.environ, {"HITL_WEBHOOK_URL": "http://hook.example.com/"}):
                result = await dispatcher.escalate_notify(item, escalation_level=1)

            assert result is True
            _CHANNELS["webhook"].send.assert_awaited_once()
            _CHANNELS["email"].send.assert_not_awaited()
            _CHANNELS["slack"].send.assert_not_awaited()
        finally:
            _CHANNELS["webhook"] = original_webhook
            _CHANNELS["email"] = original_email
            _CHANNELS["slack"] = original_slack

    @pytest.mark.asyncio
    async def test_escalate_level2_webhook_and_email(self) -> None:
        dispatcher = NotificationDispatcher()
        item = _make_hitl_item()

        from internalcmdb.motor.notifications import _CHANNELS
        orig_webhook = _CHANNELS["webhook"]
        orig_email = _CHANNELS["email"]
        orig_slack = _CHANNELS["slack"]
        _CHANNELS["webhook"] = MagicMock()
        _CHANNELS["webhook"].send = AsyncMock(return_value=True)
        _CHANNELS["email"] = MagicMock()
        _CHANNELS["email"].send = AsyncMock(return_value=True)
        _CHANNELS["slack"] = MagicMock()
        _CHANNELS["slack"].send = AsyncMock(return_value=True)

        try:
            with patch.dict(os.environ, {"HITL_WEBHOOK_URL": "http://hook.example.com/", "HITL_EMAIL_TO": "ops@example.com"}):
                result = await dispatcher.escalate_notify(item, escalation_level=2)

            assert result is True
            _CHANNELS["webhook"].send.assert_awaited_once()
            _CHANNELS["email"].send.assert_awaited_once()
            _CHANNELS["slack"].send.assert_not_awaited()
        finally:
            _CHANNELS["webhook"] = orig_webhook
            _CHANNELS["email"] = orig_email
            _CHANNELS["slack"] = orig_slack

    @pytest.mark.asyncio
    async def test_escalate_level3_all_channels(self) -> None:
        dispatcher = NotificationDispatcher()
        item = _make_hitl_item()

        from internalcmdb.motor.notifications import _CHANNELS
        orig_webhook = _CHANNELS["webhook"]
        orig_email = _CHANNELS["email"]
        orig_slack = _CHANNELS["slack"]
        _CHANNELS["webhook"] = MagicMock()
        _CHANNELS["webhook"].send = AsyncMock(return_value=True)
        _CHANNELS["email"] = MagicMock()
        _CHANNELS["email"].send = AsyncMock(return_value=True)
        _CHANNELS["slack"] = MagicMock()
        _CHANNELS["slack"].send = AsyncMock(return_value=True)

        try:
            with patch.dict(os.environ, {
                "HITL_WEBHOOK_URL": "http://hook.example.com/",
                "HITL_EMAIL_TO": "ops@example.com",
                "HITL_SLACK_CHANNEL": "#hitl-alerts",
            }):
                result = await dispatcher.escalate_notify(item, escalation_level=3)

            assert result is True
            _CHANNELS["webhook"].send.assert_awaited_once()
            _CHANNELS["email"].send.assert_awaited_once()
            _CHANNELS["slack"].send.assert_awaited_once()
        finally:
            _CHANNELS["webhook"] = orig_webhook
            _CHANNELS["email"] = orig_email
            _CHANNELS["slack"] = orig_slack

    @pytest.mark.asyncio
    async def test_escalate_payload_includes_level(self) -> None:
        dispatcher = NotificationDispatcher()
        item = _make_hitl_item()

        from internalcmdb.motor.notifications import _CHANNELS
        orig_webhook = _CHANNELS["webhook"]
        _CHANNELS["webhook"] = MagicMock()
        captured_payload: list[dict] = []

        async def _capture_send(payload, config):
            await asyncio.sleep(0)
            captured_payload.append(payload)
            return True

        _CHANNELS["webhook"].send = _capture_send

        try:
            with patch.dict(os.environ, {"HITL_WEBHOOK_URL": "http://hook.example.com/"}):
                await dispatcher.escalate_notify(item, escalation_level=2)

            assert len(captured_payload) == 1
            assert captured_payload[0]["escalation_level"] == 2
            assert captured_payload[0]["event_type"] == "hitl_escalation"
        finally:
            _CHANNELS["webhook"] = orig_webhook

    @pytest.mark.asyncio
    async def test_escalate_returns_false_when_all_fail(self) -> None:
        dispatcher = NotificationDispatcher()
        item = _make_hitl_item()

        from internalcmdb.motor.notifications import _CHANNELS
        orig_webhook = _CHANNELS["webhook"]
        _CHANNELS["webhook"] = MagicMock()
        _CHANNELS["webhook"].send = AsyncMock(return_value=False)

        try:
            with patch.dict(os.environ, {"HITL_WEBHOOK_URL": ""}):
                result = await dispatcher.escalate_notify(item, escalation_level=1)

            assert result is False
        finally:
            _CHANNELS["webhook"] = orig_webhook
