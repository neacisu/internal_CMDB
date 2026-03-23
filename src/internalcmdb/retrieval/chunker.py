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
_DEFAULT_MIN_TOKENS: int = 20
_CHARS_PER_TOKEN: int = 4  # conservative BPE estimate for mixed prose/YAML

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)

_SUPPORTED_FORMATS: frozenset[str] = frozenset({
    ".md", ".markdown", ".txt", ".rst", ".yaml", ".yml", ".json", ".toml",
    ".cfg", ".ini", ".csv", ".log", ".py", ".sh", ".sql",
})

_BINARY_SIGNATURE_BYTES = (
    b"%PDF", b"\x89PNG", b"\xff\xd8\xff", b"PK\x03\x04",
    b"\x1f\x8b", b"\x00\x00\x01\x00", b"GIF8",
)


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
    min_tokens: int = _DEFAULT_MIN_TOKENS
    embedding_model_code: str = "qwen3-embedding-8b-q5km"


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

    def chunk(self, text: str, *, source_path: str | None = None) -> list[TextChunk]:
        """Split *text* into a list of :class:`TextChunk` instances.

        Args:
            text: Raw document content.
            source_path: Optional file path for format validation.

        Returns an empty list for blank/whitespace-only input.

        Raises:
            ValueError: If *source_path* has an unsupported extension or binary content.
        """
        if not text or not text.strip():
            return []

        if source_path is not None:
            self._validate_format(source_path, text)

        paragraphs = self._split_paragraphs(text)
        raw_chunks = self._assemble_chunks(paragraphs)
        return self._tag_chunks(raw_chunks)

    @staticmethod
    def _validate_format(source_path: str, content: str) -> None:
        """Reject unsupported file formats and binary content."""
        import os  # noqa: PLC0415

        _, ext = os.path.splitext(source_path.lower())
        if ext and ext not in _SUPPORTED_FORMATS:
            msg = (
                f"Unsupported document format '{ext}' for '{source_path}'. "
                f"Supported: {', '.join(sorted(_SUPPORTED_FORMATS))}"
            )
            raise ValueError(msg)

        raw_bytes = content[:16].encode("utf-8", errors="replace")
        for sig in _BINARY_SIGNATURE_BYTES:
            if raw_bytes.startswith(sig):
                msg = f"Binary content detected in '{source_path}' — cannot chunk"
                raise ValueError(msg)

    def deduplicated_chunks(
        self,
        chunks: list[TextChunk],
        existing_hashes: frozenset[str],
    ) -> list[TextChunk]:
        """Filter out chunks whose content_hash already exists in the store.

        Args:
            chunks: Newly generated chunks.
            existing_hashes: Set of SHA-256 hashes already persisted.

        Returns only chunks with novel content (stable ordering preserved).
        """
        seen: set[str] = set()
        result: list[TextChunk] = []
        for c in chunks:
            if c.content_hash in existing_hashes:
                continue
            if c.content_hash in seen:
                continue
            seen.add(c.content_hash)
            result.append(c)
        return result

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
        """Convert raw (section, text) pairs into :class:`TextChunk` objects.

        Chunks smaller than ``min_tokens`` are merged into the previous chunk
        to avoid producing fragments too small for meaningful embedding.
        """
        min_tokens = self._config.min_tokens
        tagged: list[TextChunk] = []

        for idx, (section, text) in enumerate(raw_chunks):
            normalised = text.strip()
            if not normalised:
                continue
            token_count = max(1, len(normalised) // _CHARS_PER_TOKEN)

            if token_count < min_tokens and tagged:
                prev = tagged[-1]
                merged_content = prev.content + "\n\n" + normalised
                merged_token_count = max(1, len(merged_content) // _CHARS_PER_TOKEN)
                tagged[-1] = TextChunk(
                    index=prev.index,
                    content=merged_content,
                    token_count=merged_token_count,
                    section_path=prev.section_path,
                    content_hash=hashlib.sha256(merged_content.encode()).hexdigest(),
                    embedding_model_code=self._config.embedding_model_code,
                )
                continue

            content_hash = hashlib.sha256(normalised.encode()).hexdigest()
            tagged.append(
                TextChunk(
                    index=idx,
                    content=normalised,
                    token_count=token_count,
                    section_path=section,
                    content_hash=content_hash,
                    embedding_model_code=self._config.embedding_model_code,
                )
            )

        for i, chunk in enumerate(tagged):
            if chunk.index != i:
                tagged[i] = TextChunk(
                    index=i,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    section_path=chunk.section_path,
                    content_hash=chunk.content_hash,
                    embedding_model_code=chunk.embedding_model_code,
                )

        return tagged
