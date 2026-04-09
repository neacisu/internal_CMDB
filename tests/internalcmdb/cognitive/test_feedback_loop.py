"""Teste pentru FeedbackLoop (F6.2) — înregistrare feedback, statistici, clasificare."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from internalcmdb.cognitive.feedback_loop import (
    FeedbackLoop,
    _classify_correction,
    _redact_pii,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(
    item_exists: bool = True,
    dup_feedback: Any = None,
    stats_row: Any = None,
    correction_rows: list[Any] | None = None,
) -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()

    call_count = 0

    async def execute_side_effect(stmt, params=None):
        await asyncio.sleep(0)
        nonlocal call_count
        call_count += 1
        result = MagicMock()

        if call_count == 1:
            result.fetchone.return_value = (1,) if item_exists else None
        elif call_count == 2:
            result.fetchone.return_value = dup_feedback
        elif call_count == 3:
            result.fetchone.return_value = None
        elif call_count == 4:
            result.fetchone.return_value = stats_row
        elif call_count == 5:
            result.fetchall.return_value = correction_rows or []
        else:
            result.fetchone.return_value = None
            result.fetchall.return_value = []
        return result

    session.execute = execute_side_effect
    return session


def _stats_row(
    total: int = 10,
    agreed: int = 8,
    disagreed: int = 2,
    unknown: int = 0,
    rate: float = 0.8,
) -> MagicMock:
    row = MagicMock()
    row._mapping = {
        "total": total,
        "agreed": agreed,
        "disagreed": disagreed,
        "unknown": unknown,
        "agreement_rate": rate,
    }
    return row


# ---------------------------------------------------------------------------
# _redact_pii
# ---------------------------------------------------------------------------


class TestRedactPii:
    def test_redacts_email(self) -> None:
        result = _redact_pii("contact user@example.com now")
        assert "user@example.com" not in result
        assert "REDACTED" in result

    def test_redacts_ip(self) -> None:
        result = _redact_pii("IP is 192.168.1.1")
        assert "192.168.1.1" not in result

    def test_redacts_password_field(self) -> None:
        result = _redact_pii('{"password": "s3cr3t"}')
        assert "s3cr3t" not in result

    def test_dict_redacted_recursively(self) -> None:
        obj = {"user": "admin@corp.com", "nested": {"ip": "10.0.0.1"}}
        result = _redact_pii(obj)
        assert "admin@corp.com" not in str(result)
        assert "10.0.0.1" not in str(result)

    def test_non_string_passthrough(self) -> None:
        assert _redact_pii(42) == 42
        assert _redact_pii(None) is None


# ---------------------------------------------------------------------------
# _classify_correction
# ---------------------------------------------------------------------------


class TestClassifyCorrection:
    def test_false_positive(self) -> None:
        llm = {"decision": "approved"}
        human = {"decision": "rejected"}
        assert _classify_correction(llm, human) == "false_positive"

    def test_false_negative(self) -> None:
        llm = {"decision": "rejected"}
        human = {"decision": "approved"}
        assert _classify_correction(llm, human) == "false_negative"

    def test_partial_correction(self) -> None:
        llm = {"decision": "approved"}
        human = {"decision": "approved_with_modifications"}
        assert _classify_correction(llm, human) == "partial_correction"

    def test_other_correction(self) -> None:
        llm = {"decision": "deferred"}
        human = {"decision": "escalated"}
        assert _classify_correction(llm, human) == "other"


# ---------------------------------------------------------------------------
# FeedbackLoop._validate_feedback_input
# ---------------------------------------------------------------------------


class TestValidateFeedbackInput:
    def test_llm_not_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="llm_suggestion must be a dict"):
            FeedbackLoop._validate_feedback_input("not-a-dict", {"decision": "approved"})  # type: ignore[arg-type]

    def test_human_not_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="human_decision must be a dict"):
            FeedbackLoop._validate_feedback_input({}, "not-a-dict")  # type: ignore[arg-type]

    def test_missing_decision_key_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required keys"):
            FeedbackLoop._validate_feedback_input({}, {"note": "ok"})

    def test_valid_input_no_exception(self) -> None:
        FeedbackLoop._validate_feedback_input({"decision": "approved"}, {"decision": "rejected"})


# ---------------------------------------------------------------------------
# FeedbackLoop.record_feedback
# ---------------------------------------------------------------------------


class TestRecordFeedback:
    @pytest.mark.asyncio
    async def test_item_not_found_raises_value_error(self) -> None:
        session = _make_session(item_exists=False)
        fl = FeedbackLoop(session)
        with pytest.raises(ValueError, match="does not exist"):
            await fl.record_feedback(
                "non-existent-id",
                {"decision": "approved"},
                {"decision": "approved"},
            )

    @pytest.mark.asyncio
    async def test_duplicate_feedback_returns_existing_id(self) -> None:
        dup_row = MagicMock()
        dup_row.__getitem__ = lambda self, i: "existing-fb-id"

        session = MagicMock()
        session.commit = AsyncMock()
        call_count = 0

        async def execute_se(stmt, params=None):
            await asyncio.sleep(0)
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.fetchone.return_value = (1,)
            elif call_count == 2:
                row = MagicMock()
                row.__getitem__ = lambda self, i: "existing-fb-id"
                result.fetchone.return_value = row
            else:
                result.fetchone.return_value = None
            return result

        session.execute = execute_se
        fl = FeedbackLoop(session)
        fb_id = await fl.record_feedback(
            "item-1",
            {"decision": "approved"},
            {"decision": "approved"},
        )
        assert fb_id == "existing-fb-id"

    @pytest.mark.asyncio
    async def test_new_feedback_committed_and_id_returned(self) -> None:
        session = _make_session(item_exists=True, dup_feedback=None)
        fl = FeedbackLoop(session)
        fb_id = await fl.record_feedback(
            "item-1",
            {"decision": "approved"},
            {"decision": "approved"},
        )
        assert isinstance(fb_id, str)
        assert len(fb_id) == 36


# ---------------------------------------------------------------------------
# FeedbackLoop.get_accuracy_stats
# ---------------------------------------------------------------------------


class TestGetAccuracyStats:
    @pytest.mark.asyncio
    async def test_returns_stats_structure(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        call_n = 0

        async def execute_se(stmt, params=None):
            await asyncio.sleep(0)
            nonlocal call_n
            call_n += 1
            result = MagicMock()
            if call_n == 1:
                row = MagicMock()
                row._mapping = {
                    "total": 10,
                    "agreed": 8,
                    "disagreed": 2,
                    "unknown": 0,
                    "agreement_rate": 0.8,
                }
                result.fetchone.return_value = row
            else:
                result.fetchall.return_value = [("false_positive", 2)]
            return result

        session.execute = execute_se
        fl = FeedbackLoop(session)
        stats = await fl.get_accuracy_stats()
        assert stats["total"] == 10
        assert stats["agreed"] == 8
        assert "correction_types" in stats
