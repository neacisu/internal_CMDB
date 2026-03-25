"""Schema: governance — policy, approval, change log, and audit trail."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

_SERVER_NOW = "now()"


class AuditEvent(Base):
    """HTTP request audit event recorded by AuditMiddleware."""

    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_created", "created_at"),
        Index("ix_audit_event_actor", "actor"),
        Index("ix_audit_event_status", "status"),
        {"schema": "governance"},
    )

    audit_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, default="http_request")
    actor: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_entity: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[str | None] = mapped_column(Text, default="low")
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )


class PolicyRecord(Base):
    __tablename__ = "policy_record"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "governance"}

    policy_record_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    policy_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    policy_name: Mapped[str] = mapped_column("name", Text, nullable=False)
    scope_text: Mapped[str | None] = mapped_column(Text)
    rules_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("docs.document_version.document_version_id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )


class ApprovalRecord(Base):
    __tablename__ = "approval_record"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "governance"}

    approval_record_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    approval_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    entity_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    change_scope_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(Text)
    status_text: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    expires_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )


class ChangeLog(Base):
    __tablename__ = "change_log"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("change_code", name="uq_change_log_code"),
        {"schema": "governance"},
    )

    change_log_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    change_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    entity_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    change_source_text: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    action_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_control.action_request.action_request_id"), nullable=True
    )
    approval_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("governance.approval_record.approval_record_id"), nullable=True
    )
    collection_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=True
    )
    reconciliation_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery.reconciliation_result.reconciliation_result_id"),
        nullable=True,
    )
    canonical_document_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("docs.document_version.document_version_id"), nullable=True
    )
    before_state_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_state_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    rollback_reference_text: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_SERVER_NOW
    )
