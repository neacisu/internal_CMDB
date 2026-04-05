"""Teste pentru KnowledgeBase (F6.1) — embed, search, reembed."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.cognitive.knowledge_base import KnowledgeBase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(existing_chunk: bool = False) -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    call_count = 0

    async def execute_se(stmt, params=None):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if existing_chunk:
            result.fetchone.return_value = ("existing-chunk-id",)
        else:
            result.fetchone.return_value = None
        result.fetchall.return_value = []
        return result

    session.execute = execute_se
    return session


def _make_llm(vectors: list[list[float]] | None = None, fail: bool = False) -> MagicMock:
    llm = MagicMock()
    if fail:
        llm.embed = AsyncMock(side_effect=RuntimeError("embed failed"))
    else:
        default_vec = [0.1] * 4096
        llm.embed = AsyncMock(return_value=vectors or [default_vec])
    return llm


def _make_chunker_text(n_chunks: int = 2) -> list[MagicMock]:
    chunks = []
    for i in range(n_chunks):
        c = MagicMock()
        c.content = f"chunk {i} content"
        c.content_hash = f"hash{i:04d}"
        c.index = i
        c.token_count = 50
        c.section_path = f"section/{i}"
        c.embedding_model_code = "qwen3-embed"
        chunks.append(c)
    return chunks


# ---------------------------------------------------------------------------
# KnowledgeBase.embed_document
# ---------------------------------------------------------------------------


class TestEmbedDocument:
    @pytest.mark.asyncio
    async def test_empty_content_returns_empty_list(self) -> None:
        session = _make_session()
        llm = _make_llm()
        kb = KnowledgeBase(session, llm)
        result = await kb.embed_document("", {})
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_empty(self) -> None:
        session = _make_session()
        llm = _make_llm()
        kb = KnowledgeBase(session, llm)
        result = await kb.embed_document("   \n\t   ", {})
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_failure_skips_batch(self) -> None:
        session = _make_session()
        llm = _make_llm(fail=True)
        kb = KnowledgeBase(session, llm)
        with patch.object(
            kb._chunker, "chunk", return_value=_make_chunker_text(1)
        ):
            result = await kb.embed_document("some content", {})
        assert result == []

    @pytest.mark.asyncio
    async def test_duplicate_chunk_skipped(self) -> None:
        session = _make_session(existing_chunk=True)
        llm = _make_llm()
        kb = KnowledgeBase(session, llm)
        with patch.object(
            kb._chunker, "chunk", return_value=_make_chunker_text(1)
        ):
            result = await kb.embed_document("some content", {})
        assert result == []

    @pytest.mark.asyncio
    async def test_new_chunks_stored_and_committed(self) -> None:
        session = _make_session(existing_chunk=False)
        llm = _make_llm(vectors=[[0.1] * 4096, [0.2] * 4096])
        kb = KnowledgeBase(session, llm)
        with patch.object(
            kb._chunker, "chunk", return_value=_make_chunker_text(2)
        ):
            result = await kb.embed_document("doc content", {"source": "test"})
        assert len(result) == 2
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_document_version_id_accepted(self) -> None:
        session = _make_session()
        llm = _make_llm()
        kb = KnowledgeBase(session, llm)
        dvid = uuid.uuid4()
        with patch.object(
            kb._chunker, "chunk", return_value=_make_chunker_text(1)
        ):
            result = await kb.embed_document("content", {}, document_version_id=dvid)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# KnowledgeBase.search
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self) -> None:
        session = _make_session()
        llm = _make_llm()
        kb = KnowledgeBase(session, llm)
        result = await kb.search("")
        assert result == []

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_empty(self) -> None:
        session = _make_session()
        llm = _make_llm(fail=True)
        kb = KnowledgeBase(session, llm)
        result = await kb.search("some query")
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_vector_returns_empty(self) -> None:
        session = _make_session()
        llm = MagicMock()
        llm.embed = AsyncMock(return_value=[])
        kb = KnowledgeBase(session, llm)
        result = await kb.search("query")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_formatted_results(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        row = MagicMock()
        row.__getitem__ = lambda self, i: [
            "chunk-id-1", "content text", "section/path", {}, 0.85
        ][i]
        db_result = MagicMock()
        db_result.fetchall.return_value = [row]
        session.execute = AsyncMock(return_value=db_result)

        llm = _make_llm()
        kb = KnowledgeBase(session, llm)
        result = await kb.search("query", top_k=3)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# KnowledgeBase.reembed_document
# ---------------------------------------------------------------------------


class TestReembedDocument:
    @pytest.mark.asyncio
    async def test_reembed_calls_delete_then_embed(self) -> None:
        session = _make_session()
        llm = _make_llm()
        kb = KnowledgeBase(session, llm)
        dvid = uuid.uuid4()
        with patch.object(
            kb._chunker, "chunk", return_value=_make_chunker_text(1)
        ):
            await kb.reembed_document(dvid, "new content", {"src": "updated"})

        assert session.commit.called
