"""Tests for governance.notifications."""
from __future__ import annotations
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_notify_no_channels_logs_warning(caplog):
    with patch("internalcmdb.governance.notifications._WEBHOOK_URL", ""), \
         patch("internalcmdb.governance.notifications._SLACK_WEBHOOK_URL", ""):
        from internalcmdb.governance.notifications import notify_hitl_event
        with caplog.at_level(logging.WARNING):
            await notify_hitl_event("submitted", {"item_id": "i1", "risk_class": "RC-2", "priority": "high"})
    assert any("No notification channels" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_notify_webhook_success():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_response
    with patch("internalcmdb.governance.notifications._WEBHOOK_URL", "http://example.com/hook"), \
         patch("internalcmdb.governance.notifications._SLACK_WEBHOOK_URL", ""), \
         patch("httpx.AsyncClient", return_value=mock_client):
        from internalcmdb.governance.notifications import notify_hitl_event
        await notify_hitl_event("approved", {"item_id": "i2", "risk_class": "RC-1", "priority": "low"})
    mock_client.post.assert_called_once()
    body = mock_client.post.call_args[1]["json"]
    assert body["event"] == "approved" and body["item_id"] == "i2"


@pytest.mark.asyncio
async def test_notify_webhook_failure_retries():
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.side_effect = RuntimeError("connection refused")
    with patch("internalcmdb.governance.notifications._WEBHOOK_URL", "http://example.com/hook"), \
         patch("internalcmdb.governance.notifications._SLACK_WEBHOOK_URL", ""), \
         patch("internalcmdb.governance.notifications._RETRIES", 2), \
         patch("httpx.AsyncClient", return_value=mock_client):
        from internalcmdb.governance.notifications import notify_hitl_event
        await notify_hitl_event("escalated", {"item_id": "i3", "risk_class": "RC-3", "priority": "high"})
    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_notify_slack_success():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_response
    with patch("internalcmdb.governance.notifications._WEBHOOK_URL", ""), \
         patch("internalcmdb.governance.notifications._SLACK_WEBHOOK_URL", "http://hooks.slack.com/test"), \
         patch("httpx.AsyncClient", return_value=mock_client):
        from internalcmdb.governance.notifications import notify_hitl_event
        await notify_hitl_event("blocked", {"item_id": "i4", "risk_class": "RC-4", "priority": "critical", "status": "blocked"})
    body = mock_client.post.call_args[1]["json"]
    assert "attachments" in body and "BLOCKED" in body["attachments"][0]["title"]


@pytest.mark.asyncio
async def test_notify_slack_approved_color():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_response
    with patch("internalcmdb.governance.notifications._WEBHOOK_URL", ""), \
         patch("internalcmdb.governance.notifications._SLACK_WEBHOOK_URL", "http://hooks.slack.com/test"), \
         patch("httpx.AsyncClient", return_value=mock_client):
        from internalcmdb.governance.notifications import notify_hitl_event
        await notify_hitl_event("approved", {"item_id": "i", "risk_class": "RC-1", "priority": "low"})
    body = mock_client.post.call_args[1]["json"]
    assert body["attachments"][0]["color"] == "#4CAF50"


@pytest.mark.asyncio
async def test_notify_slack_unknown_event_color():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_response
    with patch("internalcmdb.governance.notifications._WEBHOOK_URL", ""), \
         patch("internalcmdb.governance.notifications._SLACK_WEBHOOK_URL", "http://hooks.slack.com/test"), \
         patch("httpx.AsyncClient", return_value=mock_client):
        from internalcmdb.governance.notifications import notify_hitl_event
        await notify_hitl_event("unknown_evt", {"item_id": "i", "risk_class": "RC-1", "priority": "low"})
    body = mock_client.post.call_args[1]["json"]
    assert body["attachments"][0]["color"] == "#607D8B"


# ---------------------------------------------------------------------------
# Tests: _sanitize_log (log injection prevention, S5145)
# ---------------------------------------------------------------------------


from internalcmdb.governance.notifications import _sanitize_log  # noqa: E402


def test_sanitize_log_clean_value_unchanged() -> None:
    assert _sanitize_log("submitted") == "submitted"


def test_sanitize_log_newline_stripped() -> None:
    result = _sanitize_log("item-001\nFAKE LOG ENTRY")
    assert "\n" not in result
    assert "?" in result


def test_sanitize_log_carriage_return_stripped() -> None:
    result = _sanitize_log("item\r\ninjected")
    assert "\r" not in result
    assert "\n" not in result


def test_sanitize_log_truncates_long_values() -> None:
    result = _sanitize_log("X" * 300)
    assert result.endswith("...[truncated]")


@pytest.mark.asyncio
async def test_notify_log_injection_sanitized(caplog) -> None:
    """Verify that user-controlled payload values are sanitized before logging (S5145)."""
    with patch("internalcmdb.governance.notifications._WEBHOOK_URL", ""), \
         patch("internalcmdb.governance.notifications._SLACK_WEBHOOK_URL", ""):
        from internalcmdb.governance.notifications import notify_hitl_event
        with caplog.at_level(logging.INFO):
            await notify_hitl_event(
                "submitted",
                {
                    "item_id": "evil-id\nFAKE LOG ENTRY — privilege escalation",
                    "risk_class": "RC-2\rFAKED",
                    "priority": "high\x00null-byte",
                },
            )
    # No raw control characters should appear in any log record message
    for record in caplog.records:
        msg = record.getMessage()
        assert "\n" not in msg, f"Newline found in log message: {msg!r}"
        assert "\r" not in msg, f"CR found in log message: {msg!r}"
        assert "\x00" not in msg, f"Null byte found in log message: {msg!r}"
