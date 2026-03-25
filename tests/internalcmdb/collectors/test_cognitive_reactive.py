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

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.api.routers.collectors import (
    _DISK_HEAL_THRESHOLD_PCT,
    _enqueue_cognitive_self_heal,
    _extract_root_usage,
    _trigger_cognitive_reactions,
)


class TestExtractRootUsage:
    """Parsing root filesystem usage from disk_state payloads."""

    def test_parses_percentage_string(self) -> None:
        payload = {"disks": [{"mountpoint": "/", "used_pct": "87.5%"}]}
        assert _extract_root_usage(payload) == pytest.approx(87.5)

    def test_parses_numeric_value(self) -> None:
        payload = {"disks": [{"mountpoint": "/", "used_pct": 92}]}
        assert _extract_root_usage(payload) == pytest.approx(92.0)

    def test_parses_integer_string(self) -> None:
        payload = {"disks": [{"mountpoint": "/", "used_pct": "45"}]}
        assert _extract_root_usage(payload) == pytest.approx(45.0)

    def test_no_root_disk_returns_zero(self) -> None:
        payload = {"disks": [{"mountpoint": "/data", "used_pct": "99%"}]}
        assert _extract_root_usage(payload) == pytest.approx(0.0)

    def test_empty_payload_returns_zero(self) -> None:
        assert _extract_root_usage({}) == pytest.approx(0.0)

    def test_none_disks_returns_zero(self) -> None:
        assert _extract_root_usage({"disks": None}) == pytest.approx(0.0)

    def test_empty_disks_list_returns_zero(self) -> None:
        assert _extract_root_usage({"disks": []}) == pytest.approx(0.0)

    def test_invalid_pct_value_returns_zero(self) -> None:
        payload = {"disks": [{"mountpoint": "/", "used_pct": "N/A"}]}
        assert _extract_root_usage(payload) == pytest.approx(0.0)

    def test_multiple_disks_finds_root(self) -> None:
        payload = {
            "disks": [
                {"mountpoint": "/boot", "used_pct": "30%"},
                {"mountpoint": "/", "used_pct": "88%"},
                {"mountpoint": "/data", "used_pct": "50%"},
            ]
        }
        assert _extract_root_usage(payload) == pytest.approx(88.0)


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
        body = self._make_body([
            self._make_snapshot("heartbeat", {}),
            self._make_snapshot("system_vitals", {}),
        ])
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
        assert args[0][2] == pytest.approx(85.0)

    def test_disk_above_threshold_triggers(self) -> None:
        bg = MagicMock()
        payload = {"disks": [{"mountpoint": "/", "used_pct": "95.2%"}]}
        body = self._make_body([self._make_snapshot("disk_state", payload)])
        _trigger_cognitive_reactions(bg, body, self._make_agent("hz.113"))
        bg.add_task.assert_called_once()
        args = bg.add_task.call_args
        assert args[0][1] == "hz.113"
        assert args[0][2] == pytest.approx(95.2)

    def test_only_one_trigger_per_batch(self) -> None:
        """Even with multiple disk_state snapshots above threshold, only one task is queued."""
        bg = MagicMock()
        body = self._make_body([
            self._make_snapshot("disk_state", {"disks": [{"mountpoint": "/", "used_pct": "90%"}]}),
            self._make_snapshot("disk_state", {"disks": [{"mountpoint": "/", "used_pct": "95%"}]}),
        ])
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
        from internalcmdb.workers.queue import WorkerSettings

        assert hasattr(WorkerSettings, "cron_jobs")
        assert len(WorkerSettings.cron_jobs) >= 1

    def test_self_heal_check_in_cron(self) -> None:
        from internalcmdb.workers.queue import WorkerSettings

        cron_task_names = []
        for job in WorkerSettings.cron_jobs:
            coroutine = job.coroutine
            name = getattr(coroutine, "__name__", "") or getattr(
                coroutine, "__qualname__", ""
            )
            cron_task_names.append(name)
        assert "self_heal_check" in cron_task_names

    def test_cron_runs_every_15_minutes(self) -> None:
        from internalcmdb.workers.queue import WorkerSettings

        job = WorkerSettings.cron_jobs[0]
        assert job.minute == {0, 15, 30, 45}
