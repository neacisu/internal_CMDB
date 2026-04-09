"""Teste pentru PromptEvolutionEngine (F6.3) — evaluate_prompts, propose_improvement."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from internalcmdb.cognitive.prompt_evolution import (
    PromptEvolutionEngine,
    _build_improvement_context,
    _extract_response_text,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm(improved_text: str = "improved prompt text") -> MagicMock:
    llm = MagicMock()
    llm.reason = AsyncMock(
        return_value={
            "choices": [{"message": {"content": improved_text}}],
        }
    )
    llm.guard_input = AsyncMock(return_value={"is_valid": True, "results": []})
    return llm


def _row_mock(values: list[Any]) -> MagicMock:
    row = MagicMock()

    def _getitem(_self: Any, idx: int) -> Any:
        return values[idx]

    def _iter(_self: Any) -> Iterator[Any]:
        return iter(values)

    row.__getitem__ = _getitem
    row.__iter__ = _iter
    return row


def _make_execute_response(
    call_count: int,
    template_rows: list[Any] | None,
    stats_row: tuple[Any, ...] | None,
    corrections: list[tuple[Any, ...]] | None,
    feedback_rows: list[Any] | None,
    improvement_row: tuple[Any, ...] | None,
) -> MagicMock:
    """Build a mock DB result for the given sequential call number."""
    result = MagicMock()
    if call_count == 1:
        result.fetchall.return_value = template_rows or []
        result.fetchone.return_value = improvement_row
    elif call_count == 2:
        if stats_row:
            result.fetchone.return_value = _row_mock(list(stats_row))
        else:
            result.fetchone.return_value = None
    elif call_count == 3:
        result.fetchall.return_value = list(corrections) if corrections else []
    elif call_count == 4:
        result.fetchone.return_value = improvement_row if improvement_row else None
    else:
        result.fetchone.return_value = stats_row
        result.fetchall.return_value = feedback_rows or []
    return result


def _make_session(
    template_rows: list[Any] | None = None,
    stats_row: tuple[Any, ...] | None = None,
    corrections: list[tuple[Any, ...]] | None = None,
    feedback_rows: list[Any] | None = None,
    improvement_row: tuple[Any, ...] | None = None,
) -> MagicMock:
    session = MagicMock()
    call_count = 0

    def execute_se(stmt: Any, params: Any = None) -> MagicMock:
        nonlocal call_count
        call_count += 1
        return _make_execute_response(
            call_count, template_rows, stats_row, corrections, feedback_rows, improvement_row
        )

    session.execute = AsyncMock(side_effect=execute_se)
    return session


def _tmpl_row(tid: str = "tid-1", code: str = "tmpl-code", version: str = "1.0") -> MagicMock:
    return _row_mock([tid, code, version])


# ---------------------------------------------------------------------------
# evaluate_prompts
# ---------------------------------------------------------------------------


class TestEvaluatePrompts:
    @pytest.mark.asyncio
    async def test_empty_templates_returns_empty_list(self) -> None:
        session = _make_session(template_rows=[])
        llm = _make_llm()
        engine = PromptEvolutionEngine(session, llm)
        result = await engine.evaluate_prompts()
        assert result == []

    @pytest.mark.asyncio
    async def test_single_template_above_threshold_no_improvement(self) -> None:
        session = MagicMock()
        call_n = 0

        def execute_se(stmt: Any, params: Any = None) -> MagicMock:
            nonlocal call_n
            call_n += 1
            result = MagicMock()
            if call_n == 1:
                result.fetchall.return_value = [_tmpl_row()]
            elif call_n == 2:
                result.fetchone.return_value = _row_mock([20, 0.95])
            else:
                result.fetchall.return_value = []
            return result

        session.execute = AsyncMock(side_effect=execute_se)
        llm = _make_llm()
        engine = PromptEvolutionEngine(session, llm, accuracy_threshold=0.80)
        evaluations = await engine.evaluate_prompts()
        assert len(evaluations) == 1
        assert evaluations[0].needs_improvement is False

    @pytest.mark.asyncio
    async def test_template_with_low_accuracy_needs_improvement(self) -> None:
        session = MagicMock()
        call_n = 0

        def execute_se(stmt: Any, params: Any = None) -> MagicMock:
            nonlocal call_n
            call_n += 1
            result = MagicMock()
            if call_n == 1:
                result.fetchall.return_value = [_tmpl_row()]
            elif call_n == 2:
                result.fetchone.return_value = _row_mock([15, 0.50])
            else:
                result.fetchall.return_value = []
            return result

        session.execute = AsyncMock(side_effect=execute_se)
        llm = _make_llm()
        engine = PromptEvolutionEngine(session, llm, accuracy_threshold=0.80)
        evaluations = await engine.evaluate_prompts()
        assert evaluations[0].needs_improvement is True

    @pytest.mark.asyncio
    async def test_template_insufficient_samples_no_improvement(self) -> None:
        session = MagicMock()
        call_n = 0

        def execute_se(stmt: Any, params: Any = None) -> MagicMock:
            nonlocal call_n
            call_n += 1
            result = MagicMock()
            if call_n == 1:
                result.fetchall.return_value = [_tmpl_row()]
            elif call_n == 2:
                result.fetchone.return_value = _row_mock([3, 0.40])
            else:
                result.fetchall.return_value = []
            return result

        session.execute = AsyncMock(side_effect=execute_se)
        llm = _make_llm()
        engine = PromptEvolutionEngine(session, llm)
        evaluations = await engine.evaluate_prompts()
        assert evaluations[0].needs_improvement is False

    @pytest.mark.asyncio
    async def test_sorted_by_accuracy_ascending(self) -> None:
        session = MagicMock()
        call_n = 0
        accuracies = [0.9, 0.5, 0.7]
        total = 20

        tmpl_rows = [_tmpl_row(f"tid-{i}", f"code-{i}") for i in range(3)]

        def execute_se(stmt: Any, params: Any = None) -> MagicMock:
            nonlocal call_n
            call_n += 1
            result = MagicMock()
            if call_n == 1:
                result.fetchall.return_value = tmpl_rows
            elif call_n % 2 == 0:
                idx = (call_n - 2) // 2
                acc = accuracies[idx] if idx < len(accuracies) else 1.0
                result.fetchone.return_value = _row_mock([total, acc])
            else:
                result.fetchall.return_value = []
            return result

        session.execute = AsyncMock(side_effect=execute_se)
        llm = _make_llm()
        engine = PromptEvolutionEngine(session, llm)
        evaluations = await engine.evaluate_prompts()
        accs = [e.accuracy for e in evaluations]
        assert accs == sorted(accs)


# ---------------------------------------------------------------------------
# propose_improvement
# ---------------------------------------------------------------------------


class TestProposeImprovement:
    @pytest.mark.asyncio
    async def test_template_not_found_raises_key_error(self) -> None:
        session = MagicMock()
        result = MagicMock()
        result.fetchone.return_value = None
        session.execute = AsyncMock(return_value=result)
        llm = _make_llm()
        engine = PromptEvolutionEngine(session, llm)
        with pytest.raises(KeyError, match="No active template"):
            await engine.propose_improvement("non-existent-code")

    @pytest.mark.asyncio
    async def test_insufficient_samples_raises_value_error(self) -> None:
        session = MagicMock()
        call_n = 0

        def execute_se(stmt: Any, params: Any = None) -> MagicMock:
            nonlocal call_n
            call_n += 1
            result = MagicMock()
            if call_n == 1:
                result.fetchone.return_value = _row_mock(["prompt text", "v1", "task", "tmpl-code"])
            elif call_n == 2:
                result.fetchone.return_value = _row_mock([3, 0.5])
            else:
                result.fetchall.return_value = []
            return result

        session.execute = AsyncMock(side_effect=execute_se)
        llm = _make_llm()
        engine = PromptEvolutionEngine(session, llm)
        with pytest.raises(ValueError, match="Insufficient feedback samples"):
            await engine.propose_improvement("tmpl-code")

    @pytest.mark.asyncio
    async def test_success_path_returns_improved_text(self) -> None:
        session = MagicMock()
        call_n = 0

        def execute_se(stmt: Any, params: Any = None) -> MagicMock:
            nonlocal call_n
            call_n += 1
            result = MagicMock()
            if call_n == 1:
                result.fetchone.return_value = _row_mock(["prompt text", "v1", "task", "tmpl-code"])
            elif call_n == 2:
                result.fetchone.return_value = _row_mock([20, 0.60])
            elif call_n in {3, 4}:
                result.fetchall.return_value = []
            else:
                result.fetchone.return_value = None
                result.fetchall.return_value = []
            return result

        session.execute = AsyncMock(side_effect=execute_se)
        llm = _make_llm(improved_text="new improved prompt")
        engine = PromptEvolutionEngine(session, llm)
        out = await engine.propose_improvement("tmpl-code", submit_hitl=False)
        assert out["improved_text"] == "new improved prompt"
        assert out["template_code"] == "tmpl-code"
        assert out["rejected"] is False

    @pytest.mark.asyncio
    async def test_guard_rejection_returns_rejected_flag(self) -> None:
        session = MagicMock()
        call_n = 0

        def execute_se(stmt: Any, params: Any = None) -> MagicMock:
            nonlocal call_n
            call_n += 1
            result = MagicMock()
            if call_n == 1:
                result.fetchone.return_value = _row_mock(["prompt text", "v1", "task", "tmpl-code"])
            elif call_n == 2:
                result.fetchone.return_value = _row_mock([20, 0.60])
            else:
                result.fetchall.return_value = []
            return result

        session.execute = AsyncMock(side_effect=execute_se)
        llm = _make_llm()
        llm.guard_input = AsyncMock(return_value={"is_valid": False, "results": ["toxic"]})
        engine = PromptEvolutionEngine(session, llm)
        out = await engine.propose_improvement("tmpl-code", submit_hitl=False)
        assert out["rejected"] is True
        assert out["improved_text"] is None


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_extract_response_text_with_choices(self) -> None:
        response = {"choices": [{"message": {"content": "hello world"}}]}
        assert _extract_response_text(response) == "hello world"

    def test_extract_response_text_empty(self) -> None:
        assert _extract_response_text({}) == ""

    def test_build_improvement_context_includes_code(self) -> None:
        ctx = _build_improvement_context("my-template", "v2", "prompt text", [])
        assert "my-template" in ctx
        assert "v2" in ctx
