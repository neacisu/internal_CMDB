"""Tests for internalcmdb.governance.hitl_workflow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from internalcmdb.governance.hitl_workflow import HITLWorkflow, _json_or_none


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workflow() -> tuple[HITLWorkflow, AsyncMock]:
    session = AsyncMock()
    wf = HITLWorkflow(session)
    return wf, session


def _mock_execute_returning(session: AsyncMock, rows: list[Any]) -> None:
    result = MagicMock()
    result.fetchone.return_value = rows[0] if rows else None
    result.rowcount = len(rows)
    session.execute = AsyncMock(return_value=result)


# ---------------------------------------------------------------------------
# Tests: _json_or_none helper
# ---------------------------------------------------------------------------


class TestJsonOrNone:
    def test_none_returns_none(self) -> None:
        assert _json_or_none(None) is None

    def test_string_returned_as_is(self) -> None:
        assert _json_or_none('{"key": "value"}') == '{"key": "value"}'

    def test_dict_serialized_to_json(self) -> None:
        result = _json_or_none({"key": "value"})
        assert result is not None
        assert '"key"' in result

    def test_list_serialized_to_json(self) -> None:
        result = _json_or_none([1, 2, 3])
        assert result is not None
        assert "1" in result


# ---------------------------------------------------------------------------
# Tests: submit
# ---------------------------------------------------------------------------


class TestSubmit:
    @pytest.mark.asyncio
    async def test_submit_returns_uuid_string(self) -> None:
        wf, session = _make_workflow()

        with patch("internalcmdb.governance.hitl_workflow._notify", new=AsyncMock()):
            item_id = await wf.submit({
                "item_type": "action_review",
                "risk_class": "RC-3",
                "source_event_id": "evt-001",
                "correlation_id": "corr-001",
            })

        assert isinstance(item_id, str)
        assert len(item_id) == 36
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_uses_default_risk_class(self) -> None:
        wf, session = _make_workflow()

        with patch("internalcmdb.governance.hitl_workflow._notify", new=AsyncMock()):
            item_id = await wf.submit({"item_type": "action_review"})

        assert isinstance(item_id, str)
        call_args = session.execute.call_args
        params = call_args[0][1]
        assert params["risk_class"] == "RC-2"
        assert params["priority"] == "medium"

    @pytest.mark.asyncio
    async def test_submit_rc4_uses_critical_priority(self) -> None:
        wf, session = _make_workflow()

        with patch("internalcmdb.governance.hitl_workflow._notify", new=AsyncMock()):
            await wf.submit({"risk_class": "RC-4"})

        params = session.execute.call_args[0][1]
        assert params["priority"] == "critical"

    @pytest.mark.asyncio
    async def test_submit_rc3_uses_high_priority(self) -> None:
        wf, session = _make_workflow()

        with patch("internalcmdb.governance.hitl_workflow._notify", new=AsyncMock()):
            await wf.submit({"risk_class": "RC-3"})

        params = session.execute.call_args[0][1]
        assert params["priority"] == "high"

    @pytest.mark.asyncio
    async def test_submit_notifies(self) -> None:
        wf, session = _make_workflow()
        notify_mock = AsyncMock()

        with patch("internalcmdb.governance.hitl_workflow._notify", new=notify_mock):
            await wf.submit({"risk_class": "RC-2"})

        notify_mock.assert_awaited_once()
        event_type = notify_mock.call_args[0][0]
        assert event_type == "submitted"


# ---------------------------------------------------------------------------
# Tests: approve
# ---------------------------------------------------------------------------


class TestApprove:
    @pytest.mark.asyncio
    async def test_approve_returns_true_on_success(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.fetchone.return_value = ("item-001",)
        session.execute = AsyncMock(return_value=result_mock)

        with patch.object(wf, "_record_feedback", new=AsyncMock()):
            ok = await wf.approve("item-001", decided_by="alice", reason="LGTM")

        assert ok is True
        session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_approve_returns_false_when_not_found(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.fetchone.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        ok = await wf.approve("nonexistent-id", decided_by="alice", reason="reason")

        assert ok is False


# ---------------------------------------------------------------------------
# Tests: reject
# ---------------------------------------------------------------------------


class TestReject:
    @pytest.mark.asyncio
    async def test_reject_returns_true_on_success(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.fetchone.return_value = ("item-002",)
        session.execute = AsyncMock(return_value=result_mock)

        with patch.object(wf, "_record_feedback", new=AsyncMock()):
            ok = await wf.reject("item-002", decided_by="bob", reason="not safe")

        assert ok is True

    @pytest.mark.asyncio
    async def test_reject_returns_false_when_not_found(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.fetchone.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        ok = await wf.reject("nonexistent-id", decided_by="bob", reason="reason")

        assert ok is False


# ---------------------------------------------------------------------------
# Tests: modify
# ---------------------------------------------------------------------------


class TestModify:
    @pytest.mark.asyncio
    async def test_modify_calls_decide_with_modifications(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.fetchone.return_value = ("item-003",)
        session.execute = AsyncMock(return_value=result_mock)

        with patch.object(wf, "_record_feedback", new=AsyncMock()):
            ok = await wf.modify(
                "item-003",
                decided_by="carol",
                reason="updated params",
                modifications={"param_a": "new_value"},
            )

        assert ok is True


# ---------------------------------------------------------------------------
# Tests: escalate
# ---------------------------------------------------------------------------


class TestEscalate:
    @pytest.mark.asyncio
    async def test_escalate_returns_true_when_row_updated(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.fetchone.return_value = (1, "escalated", "RC-3")
        session.execute = AsyncMock(return_value=result_mock)

        with patch("internalcmdb.governance.hitl_workflow._notify", new=AsyncMock()):
            ok = await wf.escalate("item-004")

        assert ok is True
        session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_escalate_returns_false_when_no_row(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.fetchone.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        ok = await wf.escalate("nonexistent")

        assert ok is False
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: check_escalations
# ---------------------------------------------------------------------------


class TestCheckEscalations:
    @pytest.mark.asyncio
    async def test_returns_zero_when_nothing_to_escalate(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.rowcount = 0
        session.execute = AsyncMock(return_value=result_mock)

        count = await wf.check_escalations()

        assert count == 0
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_count_and_commits_when_escalated(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.rowcount = 2
        session.execute = AsyncMock(return_value=result_mock)

        with patch("internalcmdb.governance.hitl_workflow._notify", new=AsyncMock()):
            count = await wf.check_escalations()

        assert count == 6
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_escalations_queries_all_risk_classes(self) -> None:
        wf, session = _make_workflow()

        result_mock = MagicMock()
        result_mock.rowcount = 0
        session.execute = AsyncMock(return_value=result_mock)

        await wf.check_escalations()

        assert session.execute.call_count == 3


# ---------------------------------------------------------------------------
# Tests: _decide with invalid decision
# ---------------------------------------------------------------------------


class TestDecideInvalidDecision:
    @pytest.mark.asyncio
    async def test_invalid_decision_returns_false(self) -> None:
        wf, session = _make_workflow()

        ok = await wf._decide("item-001", "invalid_decision", "user", "reason")

        assert ok is False
        session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: _sanitize_log (log injection prevention, S5145)
# ---------------------------------------------------------------------------


from internalcmdb.governance.hitl_workflow import _sanitize_log  # noqa: E402


class TestSanitizeLog:
    """Verify that _sanitize_log prevents log injection attacks (S5145)."""

    def test_clean_value_unchanged(self) -> None:
        assert _sanitize_log("RC-3") == "RC-3"

    def test_clean_uuid_unchanged(self) -> None:
        uuid_val = "550e8400-e29b-41d4-a716-446655440000"
        assert _sanitize_log(uuid_val) == uuid_val

    def test_newline_replaced_with_question_mark(self) -> None:
        result = _sanitize_log("item-001\nFAKE LOG ENTRY — admin escalated")
        assert "\n" not in result
        assert "?" in result

    def test_carriage_return_replaced(self) -> None:
        result = _sanitize_log("item\r\ninjected")
        assert "\r" not in result
        assert "\n" not in result

    def test_null_byte_replaced(self) -> None:
        result = _sanitize_log("val\x00ue")
        assert "\x00" not in result

    def test_ansi_escape_replaced(self) -> None:
        # ANSI escape sequences could forge colored "CRITICAL" log entries
        result = _sanitize_log("\x1b[31mFAKE-CRITICAL\x1b[0m")
        assert "\x1b" not in result

    def test_long_value_truncated(self) -> None:
        long_val = "A" * 300
        result = _sanitize_log(long_val)
        assert result.endswith("...[truncated]")
        assert len(result) <= 214  # 200 chars + len("...[truncated]") = 214

    def test_long_value_custom_max_len(self) -> None:
        result = _sanitize_log("A" * 50, max_len=10)
        assert result.endswith("...[truncated]")

    def test_non_string_int_converted(self) -> None:
        assert _sanitize_log(42) == "42"

    def test_non_string_none_converted(self) -> None:
        assert _sanitize_log(None) == "None"

    def test_tab_character_replaced(self) -> None:
        # Tab is \x09 (control char) — should be sanitized
        result = _sanitize_log("val\tue")
        assert "\t" not in result

    def test_multi_control_chars_all_replaced(self) -> None:
        result = _sanitize_log("\x01\x02\x03\x0a\x0d\x1f")
        assert all(c == "?" for c in result)
