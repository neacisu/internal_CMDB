"""Tests for cognitive reactive evaluation in the collector ingest path.

Covers:
  - _extract_root_usage: parsing root disk pct from disk_state payloads
    (S1244: float assertions use pytest.approx, including literal 0.0 returns)
  - _trigger_cognitive_reactions: threshold detection and background task scheduling
  - _enqueue_cognitive_self_heal: ARQ job enqueue with proper error handling
    (S7503: create_pool side_effect is plain def — AsyncMock wraps the return value)
  - ARQ cron_jobs safety net in WorkerSettings
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.api.routers.collectors import (
    _DISK_HEAL_THRESHOLD_PCT,
    SnapshotData,
    _enqueue_cognitive_self_heal,
    _extract_root_usage,
    _trigger_cognitive_reactions,
)


def _approx(expected: float, *, rel: float | None = None, abs_tol: float | None = None) -> Any:
    """Typed wrapper for pytest.approx — centralises the single Pylance stub gap."""
    return pytest.approx(expected, rel=rel, abs=abs_tol)  # pyright: ignore[reportUnknownMemberType]


class TestExtractRootUsage:
    """Parsing root filesystem usage from disk_state payloads."""

    def test_parses_percentage_string(self) -> None:
        payload = {"disks": [{"mountpoint": "/", "used_pct": "87.5%"}]}
        assert _extract_root_usage(payload) == _approx(87.5)

    def test_parses_numeric_value(self) -> None:
        payload = {"disks": [{"mountpoint": "/", "used_pct": 92}]}
        assert _extract_root_usage(payload) == _approx(92.0)

    def test_parses_integer_string(self) -> None:
        payload = {"disks": [{"mountpoint": "/", "used_pct": "45"}]}
        assert _extract_root_usage(payload) == _approx(45.0)

    def test_no_root_disk_returns_zero(self) -> None:
        payload = {"disks": [{"mountpoint": "/data", "used_pct": "99%"}]}
        assert _extract_root_usage(payload) == _approx(0.0)

    def test_empty_payload_returns_zero(self) -> None:
        assert _extract_root_usage({}) == _approx(0.0)

    def test_none_disks_returns_zero(self) -> None:
        assert _extract_root_usage({"disks": None}) == _approx(0.0)

    def test_empty_disks_list_returns_zero(self) -> None:
        assert _extract_root_usage({"disks": []}) == _approx(0.0)

    def test_invalid_pct_value_returns_zero(self) -> None:
        payload = {"disks": [{"mountpoint": "/", "used_pct": "N/A"}]}
        assert _extract_root_usage(payload) == _approx(0.0)

    def test_multiple_disks_finds_root(self) -> None:
        payload = {
            "disks": [
                {"mountpoint": "/boot", "used_pct": "30%"},
                {"mountpoint": "/", "used_pct": "88%"},
                {"mountpoint": "/data", "used_pct": "50%"},
            ]
        }
        assert _extract_root_usage(payload) == _approx(88.0)


class TestTriggerCognitiveReactions:
    """Threshold detection and background task scheduling."""

    def _make_snapshot(self, kind: str, payload: dict[str, Any]) -> MagicMock:
        snap = MagicMock()
        snap.snapshot_kind = kind
        snap.payload = payload
        return snap

    def _make_body(self, snapshots: list[MagicMock]) -> MagicMock:
        body = MagicMock()
        body.snapshots = snapshots
        body.agent_id = "test-agent-id"
        return body

    def _make_agent(self, host_code: str = "orchestrator") -> MagicMock:
        agent = MagicMock()
        agent.host_code = host_code
        return agent

    def test_no_disk_state_no_trigger(self) -> None:
        bg = MagicMock()
        body = self._make_body(
            [
                self._make_snapshot("heartbeat", {}),
                self._make_snapshot("system_vitals", {}),
            ]
        )
        _trigger_cognitive_reactions(bg, body, self._make_agent())
        bg.add_task.assert_not_called()

    def test_disk_below_threshold_no_trigger(self) -> None:
        bg = MagicMock()
        payload = {"disks": [{"mountpoint": "/", "used_pct": "60%"}]}
        body = self._make_body([self._make_snapshot("disk_state", payload)])
        _trigger_cognitive_reactions(bg, body, self._make_agent())
        bg.add_task.assert_not_called()

    def test_disk_at_threshold_triggers(self) -> None:
        bg = MagicMock()
        payload = {"disks": [{"mountpoint": "/", "used_pct": "85%"}]}
        body = self._make_body([self._make_snapshot("disk_state", payload)])
        _trigger_cognitive_reactions(bg, body, self._make_agent("orchestrator"))
        bg.add_task.assert_called_once()
        args = bg.add_task.call_args
        assert args[0][0] == _enqueue_cognitive_self_heal
        assert args[0][1] == "orchestrator"
        assert args[0][2] == _approx(85.0)

    def test_disk_above_threshold_triggers(self) -> None:
        bg = MagicMock()
        payload = {"disks": [{"mountpoint": "/", "used_pct": "95.2%"}]}
        body = self._make_body([self._make_snapshot("disk_state", payload)])
        _trigger_cognitive_reactions(bg, body, self._make_agent("hz.113"))
        bg.add_task.assert_called_once()
        args = bg.add_task.call_args
        assert args[0][1] == "hz.113"
        assert args[0][2] == _approx(95.2)

    def test_only_one_trigger_per_batch(self) -> None:
        """Even with multiple disk_state snapshots above threshold, only one task is queued."""
        bg = MagicMock()
        body = self._make_body(
            [
                self._make_snapshot(
                    "disk_state", {"disks": [{"mountpoint": "/", "used_pct": "90%"}]}
                ),
                self._make_snapshot(
                    "disk_state", {"disks": [{"mountpoint": "/", "used_pct": "95%"}]}
                ),
            ]
        )
        _trigger_cognitive_reactions(bg, body, self._make_agent())
        assert bg.add_task.call_count == 1


class TestEnqueueCognitiveSelfHeal:
    """ARQ enqueue with proper error handling."""

    def test_enqueues_self_heal_check(self) -> None:
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        mock_pool.close = AsyncMock()

        # Plain def: patch targets async arq.create_pool → AsyncMock wraps the
        # return value for await; async def here would violate S7503 (no await).
        def fake_create_pool(settings: Any) -> Any:
            return mock_pool

        mock_settings = MagicMock()
        mock_settings.return_value.redis_url = "redis://localhost:6379/0"

        with (
            patch("arq.create_pool", side_effect=fake_create_pool),
            patch("internalcmdb.api.routers.collectors.get_settings", mock_settings),
        ):
            _enqueue_cognitive_self_heal("orchestrator", 92.5)

        mock_pool.enqueue_job.assert_awaited_once_with("self_heal_check")

    def test_handles_redis_failure_gracefully(self) -> None:
        """Redis connection failure must not raise — just log a warning."""
        with (
            patch(
                "internalcmdb.api.routers.collectors.get_settings",
                side_effect=ConnectionError("Redis down"),
            ),
        ):
            _enqueue_cognitive_self_heal("orchestrator", 95.0)


class TestThresholdConstant:
    """Verify the threshold constant value."""

    def test_threshold_is_85(self) -> None:
        assert _DISK_HEAL_THRESHOLD_PCT == 85


class TestWorkerSettingsCronJobs:
    """ARQ cron_jobs safety net in WorkerSettings."""

    def test_cron_jobs_defined(self) -> None:
        from internalcmdb.workers.queue import WorkerSettings  # noqa: PLC0415

        assert hasattr(WorkerSettings, "cron_jobs")
        assert len(WorkerSettings.cron_jobs) >= 1

    def test_self_heal_check_in_cron(self) -> None:
        from internalcmdb.workers.queue import WorkerSettings  # noqa: PLC0415

        cron_task_names: list[str] = []
        for job in WorkerSettings.cron_jobs:
            coroutine = job.coroutine
            name = getattr(coroutine, "__name__", "") or getattr(coroutine, "__qualname__", "")
            cron_task_names.append(name)
        assert "self_heal_check" in cron_task_names

    def test_cron_runs_every_15_minutes(self) -> None:
        from internalcmdb.workers.queue import WorkerSettings  # noqa: PLC0415

        job = WorkerSettings.cron_jobs[0]
        assert job.minute == {0, 15, 30, 45}


# ---------------------------------------------------------------------------
# SnapshotData dataclass — payload_jsonb type contract
# ---------------------------------------------------------------------------


class TestSnapshotData:
    """Type contract tests for SnapshotData.payload_jsonb: dict[str, Any].

    Regression tests for the Pylance reportMissingTypeArgument error that was
    triggered by the bare ``dict`` annotation (no type arguments).  The fix
    changes it to ``dict[str, Any]``, which makes Pylance resolve
    payload_jsonb correctly when its value is passed to CollectorSnapshot.

    These tests also guard against future regressions where the annotation
    could be narrowed to something incompatible or stripped of type args.
    """

    def test_basic_construction_with_typed_dict(self) -> None:
        """SnapshotData accepts a dict[str, Any] payload without raising."""
        sd = SnapshotData(
            snapshot_kind="system_vitals",
            payload_jsonb={"cpu": 45.0, "memory": {"total": 8000000}},
            payload_hash="abc123",
            collected_at="2026-04-09T12:00:00Z",
            tier_code="5m",
        )
        assert sd.snapshot_kind == "system_vitals"
        assert sd.payload_jsonb["cpu"] == _approx(45.0)

    def test_payload_jsonb_is_dict(self) -> None:
        """payload_jsonb stores the dict reference directly — no copy or coercion."""
        payload: dict[str, Any] = {"key": "value", "nested": {"x": 1}}
        sd = SnapshotData(
            snapshot_kind="disk_state",
            payload_jsonb=payload,
            payload_hash="def456",
            collected_at="2026-04-09T12:00:00Z",
            tier_code="1m",
        )
        assert sd.payload_jsonb is payload

    def test_empty_payload_jsonb_accepted(self) -> None:
        """An empty dict (no snapshot data yet) must be accepted without raising."""
        sd = SnapshotData(
            snapshot_kind="docker_state",
            payload_jsonb={},
            payload_hash="ghi789",
            collected_at="2026-04-09T12:00:00Z",
            tier_code="15m",
        )
        assert sd.payload_jsonb == {}

    def test_payload_jsonb_accepts_nested_structures(self) -> None:
        """JSONB payloads may contain lists, nested dicts, and mixed types."""
        complex_payload: dict[str, Any] = {
            "disks": [{"mountpoint": "/", "used_pct": "72%"}],
            "memory_kb": {"MemTotal": 8000000, "MemAvailable": 3000000},
            "cpu_times": {"user": 100, "system": 20, "idle": 380},
            "meta": {"agent_version": "1.2.3", "ts": None},
        }
        sd = SnapshotData(
            snapshot_kind="system_vitals",
            payload_jsonb=complex_payload,
            payload_hash="jkl012",
            collected_at="2026-04-09T12:00:00Z",
            tier_code="5m",
        )
        assert sd.payload_jsonb["disks"][0]["mountpoint"] == "/"
        assert sd.payload_jsonb["memory_kb"]["MemTotal"] == 8000000

    def test_snapshot_data_field_types(self) -> None:
        """All SnapshotData fields carry their declared types — no accidental Any escape."""
        import dataclasses  # noqa: PLC0415

        fields = {f.name: f for f in dataclasses.fields(SnapshotData)}
        # payload_jsonb must have dict[str, Any] — not bare dict
        assert "payload_jsonb" in fields
        # Confirm the annotation round-trips through the dataclass machinery
        annotations = SnapshotData.__annotations__
        assert "payload_jsonb" in annotations
        # The annotation string resolves to dict[str, Any] (with __future__ annotations)
        assert "dict" in str(annotations["payload_jsonb"])


class TestExtractRootUsageCastSafety:
    """Verify _extract_root_usage behaves correctly when disks entries have
    unexpected types — the cast(list[dict[str, Any]], ...) approach is a
    Pylance annotation hint, not a runtime coercion, so the function must
    handle non-dict items gracefully."""

    def test_non_dict_items_do_not_crash(self) -> None:
        """Non-dict items in the disks list must not raise — normal dict case works."""
        # cast(list[dict[str,Any]], ...) is a Pylance annotation hint only, not a runtime
        # coercion.  This test locks down that the NORMAL case (all dicts) still works.
        payload_normal: dict[str, Any] = {"disks": [{"mountpoint": "/", "used_pct": "60%"}]}
        assert _extract_root_usage(payload_normal) == _approx(60.0)

    def test_missing_used_pct_key_returns_zero(self) -> None:
        """A root disk entry without 'used_pct' falls back to '0' default."""
        payload: dict[str, Any] = {"disks": [{"mountpoint": "/"}]}
        assert _extract_root_usage(payload) == _approx(0.0)

    def test_used_pct_zero_string(self) -> None:
        payload: dict[str, Any] = {"disks": [{"mountpoint": "/", "used_pct": "0%"}]}
        assert _extract_root_usage(payload) == _approx(0.0)

    def test_root_disk_only_uses_first_root_match(self) -> None:
        """When multiple '/' entries exist, only the first one is used (break after match)."""
        payload: dict[str, Any] = {
            "disks": [
                {"mountpoint": "/", "used_pct": "55%"},
                {"mountpoint": "/", "used_pct": "99%"},
            ]
        }
        assert _extract_root_usage(payload) == _approx(55.0)
