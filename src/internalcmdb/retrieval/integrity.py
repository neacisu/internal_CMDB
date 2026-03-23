"""RAG Content Integrity Checker (Phase 13, F13).

Scans document chunks for instruction-injection payloads and verifies
chunk provenance against the document → version → chunk lineage chain.

Designed to be called:
  - At ingestion time (chunker pipeline)
  - At retrieval time (broker Stage 4.5 post-filter)
  - On-demand via compliance API

Public surface::

    from internalcmdb.retrieval.integrity import RAGContentIntegrityChecker

    checker = RAGContentIntegrityChecker()
    findings = checker.scan_chunks(["chunk text 1", "chunk text 2"])
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Injection detection patterns
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(prior|above|previous)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an|the)\s+", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]|<\|im_start\|>|<\|im_end\|>"),
    re.compile(r"```\s*(?:system|assistant)\s*\n", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow\s+(?:any|the)\s+(?:rules|guidelines)", re.IGNORECASE),
    re.compile(r"override\s+(?:all\s+)?(?:safety|security|content)\s+(?:filter|policy)", re.IGNORECASE),
    re.compile(r"repeat\s+(?:the\s+)?(?:system|initial)\s+(?:prompt|instruction)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(?:if\s+)?(?:you\s+(?:are|were)|a)\s+", re.IGNORECASE),
    re.compile(r"(?:reveal|show|print|output)\s+(?:the\s+)?(?:system|hidden)\s+prompt", re.IGNORECASE),
    re.compile(r"<\s*/?(?:script|iframe|object|embed)\s*", re.IGNORECASE),
    re.compile(r"(?:base64|eval|exec)\s*\(", re.IGNORECASE),
]

_SEVERITY_MAP: dict[str, str] = {
    "ignore": "critical",
    "disregard": "critical",
    "override": "critical",
    "system": "high",
    "INST": "high",
    "script": "high",
    "eval": "high",
    "act as": "medium",
    "you are now": "medium",
    "repeat": "medium",
}


def _classify_severity(pattern_str: str) -> str:
    """Map a pattern string to a severity level."""
    for keyword, severity in _SEVERITY_MAP.items():
        if keyword.lower() in pattern_str.lower():
            return severity
    return "medium"


def _recommendation_for_severity(severity: str) -> str:
    """Operational follow-up hint for a finding (avoids nested ternaries, S3358)."""
    if severity == "critical":
        return "quarantine"
    if severity == "high":
        return "review"
    return "flag"


# ---------------------------------------------------------------------------
# Scan finding
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntegrityFinding:
    """A single integrity scan finding."""

    chunk_index: int
    pattern_matched: str
    severity: str
    snippet: str
    recommendation: str


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------


class RAGContentIntegrityChecker:
    """Scans RAG chunks for injection attacks and verifies provenance."""

    def __init__(self, patterns: list[re.Pattern[str]] | None = None) -> None:
        self._patterns = patterns or INJECTION_PATTERNS

    def scan_chunks(self, chunks: list[str]) -> list[dict]:
        """Scan a list of chunk texts for instruction-injection patterns.

        Synchronous CPU-bound regex scan; call via ``asyncio.to_thread`` from
        async endpoints if event-loop latency matters.

        Returns a list of finding dicts.  Empty list means all chunks are clean.
        """
        findings: list[dict] = []

        for idx, chunk in enumerate(chunks):
            for pattern in self._patterns:
                match = pattern.search(chunk)
                if match:
                    ctx_start = max(0, match.start() - 50)
                    ctx_end = min(len(chunk), match.end() + 50)
                    snippet = chunk[ctx_start:ctx_end]
                    severity = _classify_severity(pattern.pattern)

                    finding = IntegrityFinding(
                        chunk_index=idx,
                        pattern_matched=pattern.pattern,
                        severity=severity,
                        snippet=snippet,
                        recommendation=_recommendation_for_severity(severity),
                    )

                    findings.append({
                        "chunk_index": finding.chunk_index,
                        "pattern": finding.pattern_matched,
                        "severity": finding.severity,
                        "snippet": finding.snippet,
                        "recommendation": finding.recommendation,
                        "detected_at": datetime.now(tz=UTC).isoformat(),
                    })

                    logger.warning(
                        "Injection pattern in chunk %d: severity=%s pattern=%s",
                        idx,
                        severity,
                        pattern.pattern[:60],
                    )

        return findings

    def verify_chunk_provenance(
        self,
        chunk_id: str,
        session: Any | None = None,
    ) -> dict:
        """Verify provenance of a specific chunk.

        When *session* (sync SQLAlchemy Session) is provided, runs real DB
        queries.  Without a session falls back to structural-only validation
        that flags the result as ``unverified``.
        """
        if session is None:
            return self._provenance_no_db(chunk_id)

        return self._provenance_with_db(chunk_id, session)

    @staticmethod
    def _provenance_no_db(chunk_id: str) -> dict:
        """Return a structural provenance map without database access."""
        return {
            "chunk_id": chunk_id,
            "provenance": {
                "document_chunk": {"exists": None, "content_hash_verified": None},
                "document_version": {"exists": None, "status": None},
                "chunk_embedding": {"exists": None, "embedding_model": None},
            },
            "integrity_status": "unverified",
            "reason": "no database session provided",
            "checked_at": datetime.now(tz=UTC).isoformat(),
        }

    @staticmethod
    def _provenance_with_db(chunk_id: str, session: Any) -> dict:
        """Query retrieval schema tables to verify full provenance chain."""
        from sqlalchemy import text as sa_text  # noqa: PLC0415

        chunk_row = session.execute(
            sa_text("""
                SELECT dc.document_chunk_id, dc.chunk_hash, dc.content_text,
                       dc.document_version_id
                FROM retrieval.document_chunk dc
                WHERE dc.document_chunk_id = :cid
            """),
            {"cid": chunk_id},
        ).fetchone()

        if chunk_row is None:
            return {
                "chunk_id": chunk_id,
                "provenance": {"document_chunk": {"exists": False}},
                "integrity_status": "failed",
                "reason": "chunk not found in retrieval.document_chunk",
                "checked_at": datetime.now(tz=UTC).isoformat(),
            }

        stored_hash = chunk_row[1]
        content = chunk_row[2]
        doc_version_id = chunk_row[3]
        computed_hash = hashlib.sha256(content.strip().encode()).hexdigest()
        hash_match = stored_hash == computed_hash

        version_row = session.execute(
            sa_text("""
                SELECT dv.status_text, dv.commit_sha
                FROM docs.document_version dv
                WHERE dv.document_version_id = :dvid
            """),
            {"dvid": str(doc_version_id)},
        ).fetchone()

        version_info: dict[str, Any] = {
            "exists": version_row is not None,
            "status": version_row[0] if version_row else None,
            "commit_sha": version_row[1] if version_row else None,
        }

        embed_row = session.execute(
            sa_text("""
                SELECT ce.embedding_model_code,
                       ce.embedding_vector IS NOT NULL AS has_vector
                FROM retrieval.chunk_embedding ce
                WHERE ce.document_chunk_id = :cid
                LIMIT 1
            """),
            {"cid": chunk_id},
        ).fetchone()

        embed_info: dict[str, Any] = {
            "exists": embed_row is not None,
            "embedding_model": embed_row[0] if embed_row else None,
            "has_vector": bool(embed_row[1]) if embed_row else False,
        }

        all_ok = (
            hash_match
            and version_info["exists"]
            and embed_info["exists"]
            and embed_info["has_vector"]
        )

        return {
            "chunk_id": chunk_id,
            "provenance": {
                "document_chunk": {
                    "exists": True,
                    "content_hash_verified": hash_match,
                    "content_hash": computed_hash,
                    "stored_hash": stored_hash,
                },
                "document_version": version_info,
                "chunk_embedding": embed_info,
            },
            "integrity_status": "verified" if all_ok else "degraded",
            "checked_at": datetime.now(tz=UTC).isoformat(),
        }
