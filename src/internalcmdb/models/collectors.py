"""Schema: discovery — collector agent, snapshot, and diff models."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CollectorAgent(Base):
    """Lightweight agent deployed on each infrastructure host."""

    __tablename__ = "collector_agent"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        Index("ix_collector_agent_host_code", "host_code"),
        Index("ix_collector_agent_status", "status"),
        {"schema": "discovery"},
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("registry.host.host_id"), nullable=True
    )
    host_code: Mapped[str] = mapped_column(Text, nullable=False)
    agent_version: Mapped[str] = mapped_column(Text, nullable=False)
    enrolled_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    last_heartbeat_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    agent_config_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="online")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CollectorSnapshot(Base):
    """Versioned telemetry snapshot pushed by an agent."""

    __tablename__ = "collector_snapshot"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("agent_id", "snapshot_version", name="uq_agent_snapshot_version"),
        Index(
            "ix_snapshot_agent_kind_collected",
            "agent_id",
            "snapshot_kind",
            "collected_at",
        ),
        Index("ix_snapshot_payload_hash", "payload_hash"),
        {"schema": "discovery"},
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collector_agent.agent_id"), nullable=False
    )
    collection_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=True
    )
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    collected_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    received_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    tier_code: Mapped[str] = mapped_column(Text, nullable=False)


class SnapshotDiff(Base):
    """RFC 6902 JSON Patch diff between consecutive snapshots."""

    __tablename__ = "snapshot_diff"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        Index("ix_snapshot_diff_snapshot", "snapshot_id"),
        {"schema": "discovery"},
    )

    diff_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collector_snapshot.snapshot_id"), nullable=False
    )
    previous_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collector_snapshot.snapshot_id"), nullable=False
    )
    diff_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
