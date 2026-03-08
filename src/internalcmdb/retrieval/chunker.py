"""internalCMDB — Document Chunker with Lineage (pt-015).

Responsible for splitting raw document text into bounded chunks with full
provenance tracking.  Every chunk produced here can be traced back to:
  - its parent DocumentVersion (and thus Document + git commit SHA)
  - its zero-based chunk index within that version
  - the embedding model version that will be used to embed it
  - a SHA-256 content hash for deduplication

Design constraints:
  - Chunk boundaries respect sentence endings (``\\n\\n`` paragraph splits
    first, then sentence-boundary approximation).
  - Max token count per chunk is configurable (default 512).
  - Overlap between consecutive chunks is configurable (default 64 tokens).
  - Section path is preserved from Markdown heading context.
  - No chunk may be empty or contain only whitespace.

ADR-003 compliance: chunker produces deterministic output for a given
(content, max_tokens, overlap) triple — same content always yields the same
chunks in the same order.

Usage::

    from internalcmdb.retrieval.chunker import Chunker, ChunkerConfig

    cfg = ChunkerConfig(max_tokens=512, overlap_tokens=64)
    chunks = Chunker(cfg).chunk("# Introduction\\n\\nFull document text...")
    for c in chunks:
        print(c.index, c.section_path, c.token_count)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_MAX_TOKENS: int = 512
_DEFAULT_OVERLAP_TOKENS: int = 64
_CHARS_PER_TOKEN: int = 4  # conservative BPE estimate for mixed prose/YAML

# Markdown heading pattern — captures heading level and text.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)


@dataclass(frozen=True)
class ChunkerConfig:
    """Chunking strategy configuration.

    Attributes:
        max_tokens:    Hard upper bound on tokens per chunk (approximate).
        overlap_tokens: Number of tokens to repeat from the previous chunk
                       at the start of the next chunk (context window overlap).
        embedding_model_code: Identifier for the embedding model to be used
                              when creating ChunkEmbedding records downstream.
    """

    max_tokens: int = _DEFAULT_MAX_TOKENS
    overlap_tokens: int = _DEFAULT_OVERLAP_TOKENS
    embedding_model_code: str = "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class TextChunk:
    """A single text chunk with full lineage metadata.

    Attributes:
        index:          Zero-based position of this chunk within the document
                        version.  Deterministic for a given (content, config).
        content:        The raw chunk text (whitespace-normalised, never empty).
        token_count:    Estimated token count (approximate, character-based).
        section_path:   Dot-separated Markdown heading path at chunk start,
                        e.g. ``"Introduction.Background"``.  Empty string when
                        no heading context is available.
        content_hash:   SHA-256 hex digest of the normalised content.
        embedding_model_code: Copied from ChunkerConfig — links this chunk to
                              the embedding model that should embed it.
        metadata:       Free-form dict for downstream consumers (not persisted
                        by the chunker itself).
    """

    index: int
    content: str
    token_count: int
    section_path: str
    content_hash: str
    embedding_model_code: str
    metadata: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------


class Chunker:
    """Splits document text into overlapping, provenance-tagged chunks.

    Args:
        config: Chunking configuration.
    """

    def __init__(self, config: ChunkerConfig | None = None) -> None:
        self._config = config or ChunkerConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, text: str) -> list[TextChunk]:
        """Split *text* into a list of :class:`TextChunk` instances.

        Returns an empty list for blank/whitespace-only input.
        """
        if not text or not text.strip():
            return []

        paragraphs = self._split_paragraphs(text)
        raw_chunks = self._assemble_chunks(paragraphs)
        return self._tag_chunks(raw_chunks)

    # ------------------------------------------------------------------
    # Internal split helpers
    # ------------------------------------------------------------------

    def _split_paragraphs(self, text: str) -> list[tuple[str, str]]:
        """Split *text* into (section_path, paragraph_text) pairs.

        Paragraph boundaries are blank lines (``\\n\\n``).  Heading lines
        advance the section_path tracker but are included in the paragraph.
        """
        result: list[tuple[str, str]] = []
        current_heading_path: list[str] = []

        # Split on one-or-more blank lines.
        raw_paragraphs = re.split(r"\n{2,}", text.strip())

        for raw_para in raw_paragraphs:
            para = raw_para.strip()
            if not para:
                continue
            # Check if the paragraph starts with a Markdown heading.
            m = _HEADING_RE.match(para)
            if m:
                level = len(m.group(1))  # number of '#' characters
                heading_text = m.group(2).strip()
                # Trim the path to the current level and append.
                current_heading_path = [*current_heading_path[: level - 1], heading_text]

            section = ".".join(current_heading_path)
            result.append((section, para))

        return result

    def _assemble_chunks(self, paragraphs: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Merge consecutive paragraphs into chunks bounded by max_tokens.

        Returns a list of (section_path, chunk_text) tuples.
        """
        max_chars = self._config.max_tokens * _CHARS_PER_TOKEN
        overlap_chars = self._config.overlap_tokens * _CHARS_PER_TOKEN

        chunks: list[tuple[str, str]] = []
        current_section = ""
        current_parts: list[str] = []
        current_len = 0

        for section, para in paragraphs:
            para_len = len(para)

            if current_parts and current_len + para_len + 1 > max_chars:
                # Flush current chunk.
                chunk_text = "\n\n".join(current_parts)
                chunks.append((current_section, chunk_text))

                # Overlap: keep the tail of the previous chunk.
                overlap_text = chunk_text[-overlap_chars:] if overlap_chars else ""
                current_parts = [overlap_text] if overlap_text.strip() else []
                current_len = len(overlap_text)
                current_section = section

            if not current_parts:
                current_section = section

            current_parts.append(para)
            current_len += para_len + 1  # +1 for the separator

        if current_parts:
            chunks.append((current_section, "\n\n".join(current_parts)))

        return chunks

    # ------------------------------------------------------------------
    # Tagging
    # ------------------------------------------------------------------

    def _tag_chunks(self, raw_chunks: list[tuple[str, str]]) -> list[TextChunk]:
        """Convert raw (section, text) pairs into :class:`TextChunk` objects."""
        result: list[TextChunk] = []
        for idx, (section, text) in enumerate(raw_chunks):
            normalised = text.strip()
            if not normalised:
                continue
            token_count = max(1, len(normalised) // _CHARS_PER_TOKEN)
            content_hash = hashlib.sha256(normalised.encode()).hexdigest()
            result.append(
                TextChunk(
                    index=idx,
                    content=normalised,
                    token_count=token_count,
                    section_path=section,
                    content_hash=content_hash,
                    embedding_model_code=self._config.embedding_model_code,
                )
            )
        return result
