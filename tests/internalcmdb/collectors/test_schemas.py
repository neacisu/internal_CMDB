"""Tests for the collector API schemas (Pydantic)."""

from __future__ import annotations

import uuid

from internalcmdb.api.schemas.collectors import (
    AgentConfigUpdate,
    EnrollRequest,
    FleetHealthSummary,
    HeartbeatRequest,
    IngestRequest,
    ReportGenerateRequest,
    SnapshotItem,
)


class TestEnrollRequest:
    def test_minimal(self) -> None:
        req = EnrollRequest(host_code="hz.113", agent_version="1.0.0")
        assert req.host_code == "hz.113"
        assert not req.capabilities


class TestIngestRequest:
    def test_single_snapshot(self) -> None:
        req = IngestRequest(
            agent_id=uuid.uuid4(),
            snapshots=[
                SnapshotItem(
                    snapshot_kind="heartbeat",
                    tier_code="5s",
                    payload={"test": True},
                    collected_at="2026-03-15T00:00:00Z",
                    payload_hash="abc123",
                )
            ],
        )
        assert len(req.snapshots) == 1


class TestHeartbeatRequest:
    def test_fields(self) -> None:
        req = HeartbeatRequest(
            agent_id=uuid.uuid4(),
            agent_version="1.0.0",
            uptime_seconds=3600.0,
            load_avg=[1.0, 0.5, 0.3],
            memory_pct=45.2,
        )
        assert req.uptime_seconds == 3600.0


class TestFleetHealthSummary:
    def test_defaults(self) -> None:
        summary = FleetHealthSummary()
        assert summary.online == 0
        assert summary.total == 0


class TestAgentConfigUpdate:
    def test_partial(self) -> None:
        update = AgentConfigUpdate(tiers={"5s": 10})
        assert update.tiers == {"5s": 10}
        assert update.enabled_collectors is None


class TestReportGenerateRequest:
    def test_minimal(self) -> None:
        req = ReportGenerateRequest(report_kind="fleet_posture")
        assert not req.scope
