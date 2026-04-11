"""Schema: taxonomy — vocabulary and classification domains."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class TaxonomyDomain(Base):
    __tablename__ = "taxonomy_domain"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "taxonomy"}

    taxonomy_domain_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    domain_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="1.0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )

    terms: Mapped[list[TaxonomyTerm]] = relationship(
        back_populates="domain", cascade="all, delete-orphan"
    )


class TaxonomyTerm(Base):
    __tablename__ = "taxonomy_term"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("taxonomy_domain_id", "term_code", name="uq_term_code_per_domain"),
        {"schema": "taxonomy"},
    )

    taxonomy_term_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    taxonomy_domain_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_domain.taxonomy_domain_id"), nullable=False
    )
    term_code: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )

    domain: Mapped[TaxonomyDomain] = relationship(back_populates="terms")
    children: Mapped[list[TaxonomyTerm]] = relationship(
        back_populates="parent", foreign_keys=[parent_term_id]
    )
    parent: Mapped[TaxonomyTerm | None] = relationship(
        back_populates="children",
        remote_side=lambda: [TaxonomyTerm.__table__.c.taxonomy_term_id],
    )
