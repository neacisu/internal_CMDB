"""Schema: docs — versioned documents and entity bindings."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import Boolean, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Document(Base):
    __tablename__ = "document"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "docs"}

    document_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    document_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status_text: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    owner_code: Mapped[str | None] = mapped_column(Text)
    source_repo_url: Mapped[str | None] = mapped_column(Text)
    source_branch: Mapped[str | None] = mapped_column(Text)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "docs.document_version.document_version_id",
            use_alter=True,
            name="fk_document_current_version",
        ),
        nullable=True,
    )
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class DocumentVersion(Base):
    __tablename__ = "document_version"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "docs"}

    document_version_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("docs.document.document_id"), nullable=False
    )
    git_commit_sha: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    frontmatter_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    body_excerpt_text: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class DocumentEntityBinding(Base):
    __tablename__ = "document_entity_binding"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "docs"}

    document_entity_binding_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("docs.document_version.document_version_id"), nullable=False
    )
    entity_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    binding_role_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
