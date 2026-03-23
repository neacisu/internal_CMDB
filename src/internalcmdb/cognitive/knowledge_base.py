"""F6.1 — Knowledge Base Embeddings: chunk, embed, store, and search documents.

Uses :class:`~internalcmdb.retrieval.chunker.Chunker` for deterministic splitting,
:class:`~internalcmdb.llm.client.LLMClient` for embedding generation, and pgvector
for cosine-similarity search against ``retrieval.chunk_embedding``.

Usage::

    from internalcmdb.cognitive.knowledge_base import KnowledgeBase

    async with LLMClient() as llm:
        kb = KnowledgeBase(async_session, llm)
        chunk_ids = await kb.embed_document(content, {"source": "ops-runbook"})
        results  = await kb.search("TLS certificate rotation", top_k=5)
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.llm.client import LLMClient
from internalcmdb.retrieval.chunker import Chunker, ChunkerConfig

logger = logging.getLogger(__name__)

_EMBEDDING_DIM: int = 4096
_EMBED_BATCH_SIZE: int = 8


@dataclass(frozen=True)
class SearchResult:
    """A single search hit from the knowledge base."""

    chunk_id: str
    content: str
    section_path: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeBase:
    """Async document embedding and semantic search against pgvector.

    Args:
        session: Async SQLAlchemy session connected to InternalCMDB.
        llm:     LLMClient instance (must have an active connection pool).
        config:  Optional chunker configuration override.
    """

    def __init__(
        self,
        session: AsyncSession,
        llm: LLMClient,
        config: ChunkerConfig | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._chunker = Chunker(config or ChunkerConfig())

    async def embed_document(
        self,
        content: str,
        metadata: dict[str, Any],
        document_version_id: uuid.UUID | None = None,
    ) -> list[str]:
        """Chunk *content*, embed every chunk, and upsert into the DB.

        Returns a list of ``document_chunk_id`` strings for the stored chunks.
        """
        if not content or not content.strip():
            return []

        text_chunks = self._chunker.chunk(content)
        if not text_chunks:
            return []

        doc_version_id = document_version_id or uuid.uuid4()
        chunk_ids: list[str] = []

        for batch_start in range(0, len(text_chunks), _EMBED_BATCH_SIZE):
            batch = text_chunks[batch_start : batch_start + _EMBED_BATCH_SIZE]
            texts = [tc.content for tc in batch]

            try:
                vectors = await self._llm.embed(texts)
            except Exception:
                logger.exception("Embedding batch failed (offset=%d)", batch_start)
                continue

            for tc, vec in zip(batch, vectors, strict=False):
                chunk_id = str(uuid.uuid4())
                content_hash = tc.content_hash

                existing = await self._session.execute(
                    text("""
                        SELECT document_chunk_id FROM retrieval.document_chunk
                         WHERE chunk_hash = :hash AND document_version_id = :dvid
                         LIMIT 1
                    """),
                    {"hash": content_hash, "dvid": str(doc_version_id)},
                )
                if existing.fetchone():
                    logger.debug("Skipping duplicate chunk hash=%s", content_hash[:16])
                    continue

                await self._session.execute(
                    text("""
                        INSERT INTO retrieval.document_chunk
                            (document_chunk_id, document_version_id, chunk_index,
                             chunk_hash, content_text, token_count, section_path_text,
                             metadata_jsonb)
                        VALUES
                            (:cid, :dvid, :idx, :hash, :content, :tokens,
                             :section, :meta::jsonb)
                    """),
                    {
                        "cid": chunk_id,
                        "dvid": str(doc_version_id),
                        "idx": tc.index,
                        "hash": content_hash,
                        "content": tc.content,
                        "tokens": tc.token_count,
                        "section": tc.section_path,
                        "meta": _json_dumps(metadata),
                    },
                )

                vec_literal = "[" + ",".join(str(v) for v in vec) + "]"
                await self._session.execute(
                    text("""
                        INSERT INTO retrieval.chunk_embedding
                            (chunk_embedding_id, document_chunk_id,
                             embedding_model_code, embedding_vector,
                             lexical_tsv, metadata_jsonb)
                        VALUES
                            (:eid, :cid, :model, :vec::vector,
                             to_tsvector('english', :content), :meta::jsonb)
                    """),
                    {
                        "eid": str(uuid.uuid4()),
                        "cid": chunk_id,
                        "model": tc.embedding_model_code,
                        "vec": vec_literal,
                        "content": tc.content,
                        "meta": _json_dumps(metadata),
                    },
                )

                chunk_ids.append(chunk_id)

        await self._session.commit()
        logger.info("Embedded %d chunks for document", len(chunk_ids))
        return chunk_ids

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Semantic search — embed *query* then rank by cosine similarity.

        Returns a list of dicts with keys: chunk_id, content, section_path,
        score, metadata.
        """
        if not query or not query.strip():
            return []

        try:
            vectors = await self._llm.embed([query])
        except Exception:
            logger.exception("Query embedding failed")
            return []

        if not vectors:
            return []

        vec = vectors[0]
        vec_literal = "[" + ",".join(str(v) for v in vec) + "]"

        result = await self._session.execute(
            text("""
                SELECT dc.document_chunk_id,
                       dc.content_text,
                       dc.section_path_text,
                       dc.metadata_jsonb,
                       1 - (ce.embedding_vector <=> :vec::vector) AS score
                  FROM retrieval.chunk_embedding ce
                  JOIN retrieval.document_chunk dc
                    ON dc.document_chunk_id = ce.document_chunk_id
                 ORDER BY ce.embedding_vector <=> :vec::vector
                 LIMIT :k
            """),
            {"vec": vec_literal, "k": top_k},
        )

        rows = result.fetchall()
        return [
            {
                "chunk_id": str(r[0]),
                "content": r[1],
                "section_path": r[2] or "",
                "score": float(r[4]) if r[4] is not None else 0.0,
                "metadata": r[3] or {},
            }
            for r in rows
        ]

    async def reembed_document(
        self,
        document_version_id: uuid.UUID,
        content: str,
        metadata: dict[str, Any],
    ) -> list[str]:
        """Delete existing chunks for *document_version_id* and re-embed."""
        await self._session.execute(
            text("""
                DELETE FROM retrieval.chunk_embedding
                 WHERE document_chunk_id IN (
                     SELECT document_chunk_id FROM retrieval.document_chunk
                      WHERE document_version_id = :dvid
                 )
            """),
            {"dvid": str(document_version_id)},
        )
        await self._session.execute(
            text("""
                DELETE FROM retrieval.document_chunk
                 WHERE document_version_id = :dvid
            """),
            {"dvid": str(document_version_id)},
        )
        return await self.embed_document(content, metadata, document_version_id)


def _json_dumps(obj: Any) -> str:
    import json  # noqa: PLC0415

    return json.dumps(obj, default=str)
