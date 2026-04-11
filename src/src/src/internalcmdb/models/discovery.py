"""Schema: discovery — collection runs, observed facts, evidence and reconciliation."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import Boolean, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DiscoverySource(Base):
    __tablename__ = "discovery_source"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "discovery"}

    discovery_source_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    source_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    tool_path: Mapped[str | None] = mapped_column(Text)
    command_template: Mapped[str | None] = mapped_column(Text)
    is_read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class CollectionRun(Base):
    __tablename__ = "collection_run"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "discovery"}

    collection_run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    discovery_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.discovery_source.discovery_source_id"), nullable=False
    )
    run_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    target_scope_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    finished_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    status_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    executor_identity: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output_path: Mapped[str | None] = mapped_column(Text)
    summary_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ObservedFact(Base):
    __tablename__ = "observed_fact"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "discovery"}

    observed_fact_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=False
    )
    entity_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    fact_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    fact_key: Mapped[str] = mapped_column(Text, nullable=False)
    fact_value_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    observation_status_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    observed_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class EvidenceArtifact(Base):
    __tablename__ = "evidence_artifact"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "discovery"}

    evidence_artifact_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=False
    )
    evidence_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    artifact_path: Mapped[str | None] = mapped_column(Text)
    artifact_hash: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    content_excerpt_text: Mapped[str | None] = mapped_column(Text)
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_result"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "discovery"}

    reconciliation_result_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    entity_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    canonical_document_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("docs.document_version.document_version_id"), nullable=True
    )
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=False
    )
    result_status_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    drift_category_text: Mapped[str | None] = mapped_column(Text)
    canonical_value_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    observed_value_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    diff_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
