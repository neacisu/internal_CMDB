"""F0.5 — Embedding Re-indexing: batch migration from 1536-dim to 4096-dim.

Connects to the InternalCMDB PostgreSQL database, identifies ChunkEmbedding
rows whose embedding vector is NULL or has the wrong dimension (≠ 4096),
and re-embeds them in batches of 100 using the Ollama embed endpoint
(Qwen3-Embedding-8B, dim=4096) via LLMClient.

Designed to be run standalone::

    python -m internalcmdb.scripts.reindex_embeddings

Fully idempotent — rows that already have a 4096-dim vector are skipped.
Progress is printed to stdout after each batch.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any

import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy import text

from internalcmdb.llm.client import LLMClient
from internalcmdb.models.retrieval import _EMBEDDING_DIM

_BATCH_SIZE = 100

# Target dimension must match the model and the migration (0006).
_TARGET_DIM = _EMBEDDING_DIM  # 4096


def _build_url() -> str:
    load_dotenv()
    host = os.environ["POSTGRES_HOST"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def _fetch_stale_rows(
    conn: sa.engine.Connection,
    batch_size: int,
) -> list[dict[str, Any]]:
    """Return chunk_embedding rows needing re-indexing.

    A row qualifies when:
      - embedding_vector IS NULL, OR
      - the stored vector has a dimension different from _TARGET_DIM
        (detected via vector_dims() when pgvector is available, or
        by counting comma-separated elements in the TEXT fallback).
    """
    query = text("""
        SELECT ce.chunk_embedding_id,
               dc.content_text
        FROM   retrieval.chunk_embedding ce
        JOIN   retrieval.document_chunk  dc
               ON dc.document_chunk_id = ce.document_chunk_id
        WHERE  ce.embedding_vector IS NULL
           OR  vector_dims(ce.embedding_vector) <> :target_dim
        ORDER  BY ce.created_at
        LIMIT  :batch_size
    """)
    rows = conn.execute(query, {"target_dim": _TARGET_DIM, "batch_size": batch_size}).mappings().all()
    return [dict(r) for r in rows]


def _update_embedding(
    conn: sa.engine.Connection,
    chunk_embedding_id: Any,
    vector: list[float],
) -> None:
    vec_literal = "[" + ",".join(str(v) for v in vector) + "]"
    stmt = text("""
        UPDATE retrieval.chunk_embedding
        SET    embedding_vector = :vec::vector,
               embedding_model_code = :model_code
        WHERE  chunk_embedding_id = :id
    """)
    conn.execute(
        stmt,
        {
            "vec": vec_literal,
            "model_code": "qwen3-embedding-8b-q5km",
            "id": chunk_embedding_id,
        },
    )


_MAX_CONSECUTIVE_FAILURES = 3


async def _embed_batch(
    llm: LLMClient,
    texts: list[str],
    batch_num: int,
    consecutive_failures: int,
) -> tuple[list[list[float]] | None, int]:
    """Call the LLM embed endpoint and return (vectors, updated_failure_count).

    Returns ``None`` for vectors when the embed call fails or the response
    count does not match the request count.
    """
    try:
        vectors = await llm.embed(texts)
    except Exception as exc:
        consecutive_failures += 1
        print(
            f"[BATCH {batch_num}] Embed call failed ({consecutive_failures}/"
            f"{_MAX_CONSECUTIVE_FAILURES}): {exc}",
            file=sys.stderr,
        )
        return None, consecutive_failures

    if len(vectors) != len(texts):
        consecutive_failures += 1
        print(
            f"[BATCH {batch_num}] Count mismatch ({consecutive_failures}/"
            f"{_MAX_CONSECUTIVE_FAILURES}): "
            f"sent {len(texts)} texts, got {len(vectors)} vectors",
            file=sys.stderr,
        )
        return None, consecutive_failures

    return vectors, 0


def _persist_vectors(
    engine: sa.engine.Engine,
    ids: list[Any],
    vectors: list[list[float]],
) -> tuple[int, int]:
    """Write vectors to the database. Returns (updated, skipped)."""
    updated = 0
    skipped = 0
    with engine.connect() as conn:
        for cid, vec in zip(ids, vectors):
            if len(vec) != _TARGET_DIM:
                print(f"  SKIP {cid}: vector dim {len(vec)} != {_TARGET_DIM}", file=sys.stderr)
                skipped += 1
                continue
            _update_embedding(conn, cid, vec)
            updated += 1
        conn.commit()
    return updated, skipped


async def _reindex(engine: sa.engine.Engine) -> None:
    """Main re-indexing loop: fetch stale rows -> embed -> update -> repeat."""
    async with LLMClient() as llm:
        total_processed = 0
        total_skipped = 0
        batch_num = 0
        consecutive_failures = 0

        while True:
            with engine.connect() as conn:
                rows = _fetch_stale_rows(conn, _BATCH_SIZE)
            if not rows:
                break

            batch_num += 1
            texts = [r["content_text"] for r in rows]
            ids = [r["chunk_embedding_id"] for r in rows]

            t0 = time.perf_counter()
            vectors, consecutive_failures = await _embed_batch(
                llm, texts, batch_num, consecutive_failures,
            )

            if vectors is None:
                total_skipped += len(rows)
                if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                    print("Aborting: too many consecutive failures", file=sys.stderr)
                    break
                continue

            elapsed = time.perf_counter() - t0
            updated, skipped = _persist_vectors(engine, ids, vectors)
            total_processed += updated
            total_skipped += skipped

            print(
                f"[BATCH {batch_num}] Updated {updated}/{len(rows)} rows "
                f"(total: {total_processed}, skipped: {total_skipped}) "
                f"-- embed took {elapsed:.2f}s"
            )

        print(
            f"\nDone. Total rows re-indexed: {total_processed}, "
            f"skipped: {total_skipped}"
        )


def main() -> None:
    url = _build_url()
    engine = sa.create_engine(url)

    print(f"Re-indexing embeddings to {_TARGET_DIM}-dim vectors")
    print(f"Database: {engine.url.database}")
    print()

    asyncio.run(_reindex(engine))
    engine.dispose()


if __name__ == "__main__":
    main()
