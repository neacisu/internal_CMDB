"""Pydantic v2 schemas for the collector agent API."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from .common import DatetimeStr, OptDatetimeStr, OrmBase

# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


class EnrollRequest(BaseModel):
    host_code: str
    agent_version: str
    capabilities: list[str] = []


class EnrollResponse(BaseModel):
    agent_id: uuid.UUID
    schedule_tiers: dict[str, int]
    enabled_collectors: list[str]
    api_token: str


# ---------------------------------------------------------------------------
# Agent management
# ---------------------------------------------------------------------------


class AgentOut(OrmBase):
    agent_id: uuid.UUID
    host_id: uuid.UUID | None = None
    host_code: str
    agent_version: str
    enrolled_at: DatetimeStr
    last_heartbeat_at: OptDatetimeStr = None
    agent_config_jsonb: dict[str, Any] | None = None
    status: str
    is_active: bool


class AgentConfigUpdate(BaseModel):
    tiers: dict[str, int] | None = None
    enabled_collectors: list[str] | None = None


# ---------------------------------------------------------------------------
# Snapshot ingestion
# ---------------------------------------------------------------------------


class SnapshotItem(BaseModel):
    snapshot_kind: str
    tier_code: str
    payload: dict[str, Any]
    collected_at: str
    payload_hash: str


class IngestRequest(BaseModel):
    agent_id: uuid.UUID
    snapshots: list[SnapshotItem] = Field(min_length=1, max_length=50)


class IngestResponse(BaseModel):
    accepted: int
    deduplicated: int
    errors: list[str] = []


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


class HeartbeatRequest(BaseModel):
    agent_id: uuid.UUID
    agent_version: str
    uptime_seconds: float
    load_avg: list[float] = []
    memory_pct: float | None = None


class HeartbeatResponse(BaseModel):
    ok: bool = True
    config_update: dict[str, Any] | None = None
    update_available: bool = False


# ---------------------------------------------------------------------------
# Snapshots query
# ---------------------------------------------------------------------------


class SnapshotOut(OrmBase):
    snapshot_id: uuid.UUID
    agent_id: uuid.UUID
    snapshot_version: int
    snapshot_kind: str
    payload_jsonb: dict[str, Any] | None = None
    payload_hash: str
    collected_at: DatetimeStr
    received_at: DatetimeStr
    tier_code: str


class SnapshotDiffOut(OrmBase):
    diff_id: uuid.UUID
    snapshot_id: uuid.UUID
    previous_snapshot_id: uuid.UUID
    diff_jsonb: dict[str, Any] | None = None
    change_summary: str | None = None
    created_at: DatetimeStr


# ---------------------------------------------------------------------------
# Fleet health
# ---------------------------------------------------------------------------


class FleetHealthSummary(BaseModel):
    online: int = 0
    degraded: int = 0
    offline: int = 0
    retired: int = 0
    total: int = 0
    registered_agents: int = 0
    expected_hosts: int = 0
    unassigned_agents: int = 0


class HostHealth(BaseModel):
    agent_id: uuid.UUID | None = None
    host_code: str
    status: str
    agent_version: str | None = None
    last_heartbeat_at: str | None = None
    uptime_seconds: float | None = None
    load_avg: list[float] = []
    memory_pct: float | None = None


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class ReportGenerateRequest(BaseModel):
    report_kind: str  # fleet_posture | drift_summary | security_posture
    scope: dict[str, Any] = {}


class ReportOut(BaseModel):
    evidence_artifact_id: uuid.UUID
    report_kind: str
    report_version: int
    generated_at: str
    content_excerpt: str | None = None


# ---------------------------------------------------------------------------
# Live worker status
# ---------------------------------------------------------------------------


class LiveWorkerStatus(BaseModel):
    host_code: str
    container_name: str
    image: str | None = None
    status: str
    started_at: str | None = None
