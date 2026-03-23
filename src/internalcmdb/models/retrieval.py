"""Schema: retrieval — document chunks, embeddings and evidence packs."""

from __future__ import annotations

import os
import uuid
from typing import Any, ClassVar

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

_SERVER_NOW = "now()"

# pgvector VECTOR type — optional; falls back to TEXT until the extension
# is enabled on the server and the column is altered by a follow-up migration.
_EMBEDDING_DIM: int = int(os.environ.get("EMBEDDING_VECTOR_DIM", "4096"))

_embedding_col: Any
try:
    from pgvector.sqlalchemy import Vector

    _embedding_col = Vector(_EMBEDDING_DIM)
except ImportError:
    _embedding_col = Text()


class DocumentChunk(Base):
    __tablename__ = "document_chunk"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "retrieval"}

    document_chunk_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("docs.document_version.document_version_id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    section_path_text: Mapped[str | None] = mapped_column(Text)
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embedding"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "retrieval"}

    chunk_embedding_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retrieval.document_chunk.document_chunk_id"), nullable=False
    )
    embedding_model_code: Mapped[str] = mapped_column(Text, nullable=False)
    # Stored as VECTOR(4096) when pgvector extension is present, TEXT otherwise.
    embedding_vector: Mapped[str | None] = mapped_column(_embedding_col)
    lexical_tsv: Mapped[str | None] = mapped_column(TSVECTOR)
    summary_text: Mapped[str | None] = mapped_column(Text)
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )


class EvidencePack(Base):
    __tablename__ = "evidence_pack"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "retrieval"}

    evidence_pack_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pack_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    task_type_code: Mapped[str] = mapped_column(Text, nullable=False)
    request_scope_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    selection_rationale_text: Mapped[str | None] = mapped_column(Text)
    token_budget: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )


class EvidencePackItem(Base):
    __tablename__ = "evidence_pack_item"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "retrieval"}

    evidence_pack_item_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evidence_pack_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retrieval.evidence_pack.evidence_pack_id"), nullable=False
    )
    item_order: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("retrieval.document_chunk.document_chunk_id"), nullable=True
    )
    evidence_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery.evidence_artifact.evidence_artifact_id"), nullable=True
    )
    inclusion_reason_text: Mapped[str | None] = mapped_column(Text)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )
