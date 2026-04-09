"""Tests for scripts.reindex_embeddings."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.scripts.reindex_embeddings import (
    _build_url,
    _embed_batch,
    _fetch_stale_rows,
    _persist_vectors,
    _update_embedding,
)

# ---------------------------------------------------------------------------
# _build_url
# ---------------------------------------------------------------------------


def test_build_url_constructs_postgres_url(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "db-host")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "cmdb")
    monkeypatch.setenv("POSTGRES_USER", "admin")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    with patch("internalcmdb.scripts.reindex_embeddings.load_dotenv"):
        url = _build_url()
    assert "db-host" in url
    assert "cmdb" in url
    assert "admin" in url


def test_build_url_default_port(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.setenv("POSTGRES_DB", "testdb")
    monkeypatch.setenv("POSTGRES_USER", "user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pass")
    with patch("internalcmdb.scripts.reindex_embeddings.load_dotenv"):
        url = _build_url()
    assert ":5432/" in url


# ---------------------------------------------------------------------------
# _fetch_stale_rows
# ---------------------------------------------------------------------------


def test_fetch_stale_rows_returns_list():
    conn = MagicMock()
    rows = [
        {"chunk_embedding_id": "id-1", "content_text": "hello world"},
        {"chunk_embedding_id": "id-2", "content_text": "foo bar"},
    ]
    conn.execute.return_value.mappings.return_value.all.return_value = rows
    result = _fetch_stale_rows(conn, batch_size=10)
    assert len(result) == 2
    assert result[0]["chunk_embedding_id"] == "id-1"


def test_fetch_stale_rows_empty():
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []
    assert _fetch_stale_rows(conn, batch_size=10) == []


# ---------------------------------------------------------------------------
# _update_embedding
# ---------------------------------------------------------------------------


def test_update_embedding_calls_execute():
    conn = MagicMock()
    _update_embedding(conn, "chunk-id-1", [0.1, 0.2, 0.3])
    conn.execute.assert_called_once()


# ---------------------------------------------------------------------------
# _embed_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_batch_success():
    llm = AsyncMock()
    vectors = [[0.1, 0.2], [0.3, 0.4]]
    llm.embed = AsyncMock(return_value=vectors)
    result, failures = await _embed_batch(
        llm, ["text1", "text2"], batch_num=1, consecutive_failures=0
    )
    assert result == vectors
    assert failures == 0


@pytest.mark.asyncio
async def test_embed_batch_llm_failure():
    llm = AsyncMock()
    llm.embed = AsyncMock(side_effect=RuntimeError("LLM down"))
    result, failures = await _embed_batch(llm, ["text1"], batch_num=1, consecutive_failures=0)
    assert result is None
    assert failures == 1


@pytest.mark.asyncio
async def test_embed_batch_count_mismatch():
    llm = AsyncMock()
    llm.embed = AsyncMock(return_value=[[0.1]])  # 1 vector for 2 texts
    result, failures = await _embed_batch(
        llm, ["text1", "text2"], batch_num=1, consecutive_failures=0
    )
    assert result is None
    assert failures == 1


@pytest.mark.asyncio
async def test_embed_batch_increments_existing_failures():
    llm = AsyncMock()
    llm.embed = AsyncMock(side_effect=RuntimeError("down"))
    _, failures = await _embed_batch(llm, ["text1"], batch_num=1, consecutive_failures=2)
    assert failures == 3


# ---------------------------------------------------------------------------
# _persist_vectors
# ---------------------------------------------------------------------------


def test_persist_vectors_correct_dim():
    from internalcmdb.scripts.reindex_embeddings import _TARGET_DIM  # noqa: PLC0415

    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    vectors = [[float(i % 10) for i in range(_TARGET_DIM)]]
    updated, skipped = _persist_vectors(engine, ["id-1"], vectors)
    assert updated == 1
    assert skipped == 0


def test_persist_vectors_wrong_dim():
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    updated, skipped = _persist_vectors(engine, ["id-1"], [[0.1, 0.2, 0.3]])
    assert updated == 0
    assert skipped == 1


def test_persist_vectors_mixed_dim():
    from internalcmdb.scripts.reindex_embeddings import _TARGET_DIM  # noqa: PLC0415

    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    correct = [float(i % 10) for i in range(_TARGET_DIM)]
    updated, skipped = _persist_vectors(engine, ["id-1", "id-2"], [correct, [0.1, 0.2]])
    assert updated == 1
    assert skipped == 1
