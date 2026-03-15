"""Tests for the collector models (ORM)."""

from __future__ import annotations

import uuid

from internalcmdb.models.collectors import (
    CollectorAgent,
    CollectorSnapshot,
    SnapshotDiff,
)


class TestCollectorModels:
    def test_collector_agent_defaults(self) -> None:
        agent = CollectorAgent(
            agent_id=uuid.uuid4(),
            host_code="hz.113",
            agent_version="1.0.0",
            status="online",
            is_active=True,
        )
        assert agent.host_code == "hz.113"
        assert agent.status == "online"
        assert agent.is_active is True

    def test_collector_snapshot_fields(self) -> None:
        snap = CollectorSnapshot(
            snapshot_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            snapshot_version=1,
            snapshot_kind="heartbeat",
            payload_jsonb={"test": True},
            payload_hash="abc123",
            collected_at="2026-03-15T00:00:00Z",
            tier_code="5s",
        )
        assert snap.snapshot_kind == "heartbeat"
        assert snap.tier_code == "5s"
        assert snap.snapshot_version == 1

    def test_snapshot_diff_fields(self) -> None:
        diff = SnapshotDiff(
            diff_id=uuid.uuid4(),
            snapshot_id=uuid.uuid4(),
            previous_snapshot_id=uuid.uuid4(),
            diff_jsonb=[{"op": "replace", "path": "/a", "value": 2}],
            change_summary="1 changed",
        )
        assert diff.change_summary == "1 changed"
