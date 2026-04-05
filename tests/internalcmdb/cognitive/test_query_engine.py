"""Teste pentru QueryEngine (F2.4) — pipeline RAG complet."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from internalcmdb.cognitive.query_engine import QueryEngine, QueryResult

_EMBED_DIM = 4096


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm(
    vectors: list[list[float]] | None = None,
    fail_embed: bool = False,
    reason_response: dict[str, Any] | None = None,
) -> MagicMock:
    llm = MagicMock()
    if fail_embed:
        llm.embed = AsyncMock(side_effect=RuntimeError("embed error"))
    else:
        llm.embed = AsyncMock(return_value=vectors or [[0.1] * _EMBED_DIM])

    llm.reason = AsyncMock(return_value=reason_response or {
        "choices": [{"message": {"content": "The answer is 42."}}],
        "usage": {"total_tokens": 100},
    })
    return llm


def _make_session(rows: list[Any] | None = None) -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    if rows is not None:
        result.mappings.return_value.all.return_value = rows
    else:
        result.mappings.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    return session


def _source_row(
    chunk_id: str = "chunk-1",
    content: str = "content text",
    section: str = "section/a",
    token_count: int = 50,
    distance: float = 0.2,
) -> dict[str, Any]:
    return {
        "document_chunk_id": chunk_id,
        "content_text": content,
        "section_path_text": section,
        "token_count": token_count,
        "chunk_index": 0,
        "embedding_model_code": "qwen3-embed",
        "distance": distance,
    }


# ---------------------------------------------------------------------------
# QueryEngine.query — edge cases
# ---------------------------------------------------------------------------


class TestQueryEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_question_returns_empty_message(self) -> None:
        engine = QueryEngine(_make_llm(), _make_session())
        result = await engine.query("")
        assert result.answer == "Empty question provided."
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_question_returns_empty_message(self) -> None:
        engine = QueryEngine(_make_llm(), _make_session())
        result = await engine.query("   ")
        assert result.answer == "Empty question provided."

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_error_message(self) -> None:
        engine = QueryEngine(_make_llm(fail_embed=True), _make_session())
        result = await engine.query("some question?")
        assert "Failed to generate" in result.answer
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_wrong_embedding_dim_returns_error(self) -> None:
        llm = _make_llm(vectors=[[0.1] * 128])
        engine = QueryEngine(llm, _make_session())
        result = await engine.query("question")
        assert "Failed to generate" in result.answer

    @pytest.mark.asyncio
    async def test_no_sources_returns_no_documents_message(self) -> None:
        engine = QueryEngine(_make_llm(), _make_session(rows=[]))
        result = await engine.query("question about disk usage")
        assert "No relevant documents" in result.answer
        assert result.confidence == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_normal_flow_returns_answer_with_sources(self) -> None:
        rows = [_source_row() for _ in range(3)]
        session = _make_session(rows=rows)
        llm = _make_llm()
        engine = QueryEngine(llm, session, top_k=3)
        result = await engine.query("Which hosts have the highest disk usage?")
        assert "42" in result.answer
        assert len(result.sources) == 3
        assert result.confidence > 0.0
        assert result.tokens_used > 0

    @pytest.mark.asyncio
    async def test_reason_failure_returns_error_answer(self) -> None:
        rows = [_source_row()]
        session = _make_session(rows=rows)
        llm = _make_llm()
        llm.reason = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        engine = QueryEngine(llm, session)
        result = await engine.query("what is the status?")
        assert "error" in result.answer.lower()


# ---------------------------------------------------------------------------
# QueryEngine._assemble_context
# ---------------------------------------------------------------------------


class TestAssembleContext:
    def test_empty_sources_returns_empty_string(self) -> None:
        result = QueryEngine._assemble_context([])
        assert result == ""

    def test_sources_included_in_order(self) -> None:
        sources = [
            {"section": "a", "content": "text A", "distance": 0.1},
            {"section": "b", "content": "text B", "distance": 0.2},
        ]
        ctx = QueryEngine._assemble_context(sources)
        assert "[Source 1]" in ctx
        assert "[Source 2]" in ctx

    def test_token_budget_respected(self) -> None:
        big_content = "x" * 400
        sources = [
            {"section": "s", "content": big_content, "distance": 0.1}
            for _ in range(100)
        ]
        ctx = QueryEngine._assemble_context(sources, max_tokens=500)
        assert len(ctx) < 500 * 4 * 5


# ---------------------------------------------------------------------------
# QueryEngine._estimate_confidence
# ---------------------------------------------------------------------------


class TestEstimateConfidence:
    def test_no_sources_returns_zero(self) -> None:
        assert QueryEngine._estimate_confidence([], "answer") == 0.0

    def test_no_answer_returns_zero(self) -> None:
        assert QueryEngine._estimate_confidence([_source_row()], "") == 0.0

    def test_confidence_between_zero_and_one(self) -> None:
        sources = [_source_row(distance=0.1) for _ in range(8)]
        conf = QueryEngine._estimate_confidence(sources, "A " * 100)
        assert 0.0 <= conf <= 1.0

    def test_low_distance_higher_confidence(self) -> None:
        close_sources = [_source_row(distance=0.05) for _ in range(8)]
        far_sources = [_source_row(distance=0.9) for _ in range(8)]
        answer = "A detailed answer " * 15
        conf_close = QueryEngine._estimate_confidence(close_sources, answer)
        conf_far = QueryEngine._estimate_confidence(far_sources, answer)
        assert conf_close > conf_far
