"""F2.4 — RAG Query Engine: embed → search → assemble → reason → respond.

Implements the full Retrieval-Augmented Generation pipeline for the cognitive
brain.  Given a natural-language question, the engine:

  1. Embeds the question via LLMClient (Qwen3-Embedding-8B, dim=4096).
  2. Performs pgvector cosine-distance search on ``retrieval.chunk_embedding``.
  3. Assembles retrieved chunks as an evidence context.
  4. Sends the evidence + question to the reasoning LLM for synthesis.
  5. Returns a structured :class:`QueryResult`.

Usage::

    from internalcmdb.cognitive.query_engine import QueryEngine

    engine = QueryEngine(llm_client, db_session)
    result = await engine.query("Which hosts have the highest disk usage?")
    print(result.answer)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.llm.client import LLMClient
from internalcmdb.models.retrieval import _EMBEDDING_DIM

logger = logging.getLogger(__name__)

_TOP_K = 8
_CHARS_PER_TOKEN = 4
_MAX_CONTEXT_TOKENS = 6000


@dataclass(frozen=True)
class QueryResult:
    """Result of a RAG query.

    Attributes:
        answer:      The synthesised answer text from the reasoning model.
        sources:     List of source chunk metadata used to build the answer.
        confidence:  0.0-1.0 confidence estimate (based on source count and
                     model-reported finish reason).
        tokens_used: Approximate total token count consumed (prompt + completion).
    """

    answer: str
    sources: list[dict[str, Any]] = field(default_factory=lambda: [])
    confidence: float = 0.0
    tokens_used: int = 0


class QueryEngine:
    """RAG query engine backed by LLMClient and pgvector.

    Args:
        llm:     An :class:`LLMClient` instance with ``embed`` and ``reason``
                 methods.
        session: An ``AsyncSession`` connected to the InternalCMDB database.
        top_k:   Number of nearest chunks to retrieve (default 8).
    """

    def __init__(
        self,
        llm: LLMClient,
        session: AsyncSession,
        *,
        top_k: int = _TOP_K,
    ) -> None:
        self._llm = llm
        self._session = session
        self._top_k = top_k

    async def query(self, question: str) -> QueryResult:
        """Execute the full RAG pipeline for *question*.

        First attempts a direct SQL answer for fleet-aggregate queries (e.g.
        "how many hosts are online?") so users get instant accurate counts even
        before the knowledge base is populated.  Falls back to the full RAG
        pipeline for all other questions.

        Returns a :class:`QueryResult` with the synthesised answer and
        provenance metadata.
        """
        if not question or not question.strip():
            return QueryResult(answer="Empty question provided.", confidence=0.0)

        # Step 0 — Try direct fleet answer before expensive RAG pipeline
        direct = await self._direct_fleet_answer(question)
        if direct is not None:
            return direct

        # Step 1 — Embed the question
        try:
            vectors = await self._llm.embed([question])
        except Exception:
            logger.exception("Embedding generation failed for query")
            return QueryResult(
                answer="Failed to generate a valid embedding for the question.",
                confidence=0.0,
            )

        if not vectors or len(vectors[0]) != _EMBEDDING_DIM:
            return QueryResult(
                answer="Failed to generate a valid embedding for the question.",
                confidence=0.0,
            )

        query_vec = vectors[0]

        # Step 2 — pgvector search
        sources = await self._vector_search(query_vec)

        if not sources:
            return QueryResult(
                answer="No relevant documents found in the knowledge base.",
                sources=[],
                confidence=0.1,
            )

        # Step 3 — Assemble evidence context (with token budget)
        context_text = self._assemble_context(sources, max_tokens=_MAX_CONTEXT_TOKENS)

        # Step 4 — LLM reasoning
        answer, tokens_used = await self._reason(question, context_text)

        # Step 5 — Compute confidence
        confidence = self._estimate_confidence(sources, answer)

        return QueryResult(
            answer=answer,
            sources=sources,
            confidence=confidence,
            tokens_used=tokens_used,
        )

    async def _vector_search(
        self,
        query_vec: list[float],
    ) -> list[dict[str, Any]]:
        """Retrieve the top-K nearest chunks via pgvector cosine distance."""
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"

        stmt = text("""
            SELECT dc.document_chunk_id,
                   dc.content_text,
                   dc.section_path_text,
                   dc.metadata_jsonb,
                   dc.token_count,
                   dc.chunk_index,
                   ce.embedding_model_code,
                   (ce.embedding_vector <=> CAST(:vec AS vector)) AS distance
            FROM   retrieval.chunk_embedding ce
            JOIN   retrieval.document_chunk  dc
                   ON dc.document_chunk_id = ce.document_chunk_id
            WHERE  ce.embedding_vector IS NOT NULL
            ORDER  BY ce.embedding_vector <=> CAST(:vec AS vector)
            LIMIT  :top_k
        """)

        try:
            result = await self._session.execute(stmt, {"vec": vec_literal, "top_k": self._top_k})
            rows = result.mappings().all()
        except Exception:
            logger.exception("pgvector search failed — returning empty result set")
            return []

        return [
            {
                "chunk_id": str(r["document_chunk_id"]),
                "content": r["content_text"],
                "section": r["section_path_text"] or "",
                "metadata": dict(r["metadata_jsonb"]) if r["metadata_jsonb"] else {},
                "token_count": r["token_count"] or 0,
                "chunk_index": r["chunk_index"],
                "model": r["embedding_model_code"],
                "distance": float(r["distance"]),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Direct fleet-query short-circuit  (TODO 3.1)
    # ------------------------------------------------------------------

    #: Keywords that indicate a fleet-aggregate (count/status) intent.
    _FLEET_KEYWORDS: frozenset[str] = frozenset(
        {
            "how many", "count", "total", "number of",
            "hosts", "servers", "nodes", "machines",
            "online", "offline", "status", "healthy", "unhealthy",
            "critical", "warning", "ok", "available", "unavailable",
            "environment", "env", "production", "staging", "dev",
            "service", "services",
        }
    )

    async def _direct_fleet_answer(self, question: str) -> QueryResult | None:
        """Return a QueryResult built from live SQL if the question is a fleet query.

        Detects fleet-aggregate intent by checking for keyword overlap with
        _FLEET_KEYWORDS.  If matched, executes lightweight SQL against
        ``registry.host`` and returns a formatted answer without RAG.

        Returns ``None`` when the question is not fleet-related so the caller
        falls back to the full RAG pipeline.
        """
        q_lower = question.lower()
        matched = sum(1 for kw in self._FLEET_KEYWORDS if kw in q_lower)
        if matched < 2:  # require at least 2 fleet keywords to trigger  # noqa: PLR2004
            return None

        try:
            result = await self._session.execute(
                text("""
                    SELECT
                        COUNT(*)                                           AS total,
                        COUNT(DISTINCT h.environment_term_id)             AS env_count,
                        COUNT(DISTINCT h.lifecycle_term_id)               AS lifecycle_count
                    FROM registry.host h
                """)
            )
            row = result.mappings().first()
        except Exception:
            logger.debug("_direct_fleet_answer: SQL failed — falling back to RAG", exc_info=True)
            import contextlib  # noqa: PLC0415

            with contextlib.suppress(Exception):
                await self._session.rollback()
            return None

        if row is None:
            return None

        total = row["total"] or 0
        if total == 0:
            return None  # empty fleet — fall through to RAG

        answer = (
            f"Fleet summary (live data from CMDB): "
            f"{total} total host(s) registered, "
            f"spanning {row['env_count']} distinct environment(s) "
            f"and {row['lifecycle_count']} lifecycle state(s)."
        )
        return QueryResult(
            answer=answer,
            sources=[{
                "chunk_id": "sql:registry.host",
                "content": answer,
                "section": "fleet_summary",
                "distance": 0.0,
            }],
            confidence=0.95,
            tokens_used=0,
        )

    @staticmethod
    def _assemble_context(
        sources: list[dict[str, Any]],
        *,
        max_tokens: int = _MAX_CONTEXT_TOKENS,
    ) -> str:
        """Build a numbered evidence block from retrieved chunks.

        Enforces a token budget so assembled context does not overflow the
        model's context window.  Sources are included in order (best match
        first); once the budget is exhausted, remaining sources are dropped.
        """
        parts: list[str] = []
        tokens_used = 0

        for i, src in enumerate(sources, 1):
            section = src.get("section") or "unknown"
            content = src.get("content", "")
            block = (
                f"[Source {i}] (section: {section}, distance: {src.get('distance', 0):.4f})\n"
                f"{content}"
            )
            block_tokens = len(block) // _CHARS_PER_TOKEN
            if tokens_used + block_tokens > max_tokens and parts:
                logger.info(
                    "Context budget reached at source %d/%d (%d tokens used of %d)",
                    i,
                    len(sources),
                    tokens_used,
                    max_tokens,
                )
                break
            parts.append(block)
            tokens_used += block_tokens

        return "\n\n---\n\n".join(parts)

    async def _reason(
        self,
        question: str,
        context: str,
    ) -> tuple[str, int]:
        """Send the question + evidence context to the reasoning LLM.

        Returns (answer_text, approximate_tokens_used).
        """
        system_prompt = (
            "You are the InternalCMDB cognitive brain. Answer the user's question "
            "based ONLY on the evidence provided below. If the evidence is insufficient, "
            "say so clearly. Be precise, cite source numbers, and avoid speculation.\n\n"
            f"--- EVIDENCE ---\n{context}\n--- END EVIDENCE ---"
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        try:
            response = await self._llm.reason(messages, temperature=0.1, max_tokens=2048)
        except Exception:
            logger.exception("Reasoning LLM call failed")
            return "An error occurred while generating the answer.", 0

        choices = response.get("choices", [])
        if not choices:
            return "The model returned an empty response.", 0

        answer = choices[0].get("message", {}).get("content", "")
        usage = response.get("usage", {})
        tokens_used = usage.get("total_tokens", 0)

        if not tokens_used:
            prompt_tokens = len(system_prompt + question) // _CHARS_PER_TOKEN
            completion_tokens = len(answer) // _CHARS_PER_TOKEN
            tokens_used = prompt_tokens + completion_tokens

        return answer, tokens_used

    @staticmethod
    def _estimate_confidence(
        sources: list[dict[str, Any]],
        answer: str,
    ) -> float:
        """Heuristic confidence estimate based on source quality and answer length."""
        if not sources or not answer:
            return 0.0

        avg_distance = sum(s.get("distance", 1.0) for s in sources) / len(sources)
        distance_score = max(0.0, 1.0 - avg_distance)

        source_count_score = min(1.0, len(sources) / _TOP_K)

        answer_length_score = min(1.0, len(answer) / 200.0)

        confidence = distance_score * 0.5 + source_count_score * 0.3 + answer_length_score * 0.2
        return round(min(1.0, max(0.0, confidence)), 4)
