"""Schema: agent_control — prompt templates, agent runs and action requests."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import Boolean, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PromptTemplateRegistry(Base):
    __tablename__ = "prompt_template_registry"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "agent_control"}

    prompt_template_registry_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    template_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    task_type_code: Mapped[str] = mapped_column(Text, nullable=False)
    template_version: Mapped[str] = mapped_column(Text, nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    policy_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "governance.policy_record.policy_record_id",
            use_alter=True,
            name="fk_prompt_template_policy",
        ),
        nullable=True,
    )
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("docs.document_version.document_version_id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class AgentRun(Base):
    __tablename__ = "agent_run"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "agent_control"}

    agent_run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    agent_identity: Mapped[str] = mapped_column(Text, nullable=False)
    task_type_code: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_registry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_control.prompt_template_registry.prompt_template_registry_id"),
        nullable=True,
    )
    approval_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("governance.approval_record.approval_record_id"), nullable=True
    )
    evidence_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("retrieval.evidence_pack.evidence_pack_id"), nullable=True
    )
    requested_scope_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status_text: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    started_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    finished_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class AgentEvidence(Base):
    __tablename__ = "agent_evidence"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "agent_control"}

    agent_evidence_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_control.agent_run.agent_run_id"), nullable=False
    )
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
    evidence_role_text: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class ActionRequest(Base):
    __tablename__ = "action_request"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("request_code", name="uq_action_request_code"),
        {"schema": "agent_control"},
    )

    action_request_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_control.agent_run.agent_run_id"), nullable=True
    )
    approval_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("governance.approval_record.approval_record_id"), nullable=True
    )
    action_class_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_scope_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    requested_change_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status_text: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    executed_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
