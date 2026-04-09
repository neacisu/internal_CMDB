"""Tests for internalcmdb.workers.cognitive_tasks.

Covers:
  - S7503 compliance: _check_database properly uses asyncio.to_thread (source
    fix); test helper stubs are plain ``def`` — ``AsyncMock`` wraps their
    return values automatically, so ``async`` is neither required nor correct.
  - S1244 compliance: all floating-point assertions use ``pytest.approx``
    instead of equality checks.
  - Task wrapper: timing, structured output, retry semantics.
  - Registry completeness: all 10 cognitive tasks registered.
  - Dependency checks: _check_redis, _check_database.
  - Self-heal pipeline: threshold evaluation, recently-healed guard, auto-heal
    vs. insight-only paths.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar
from unittest.mock import AsyncMock, patch

import pytest

from internalcmdb.workers.cognitive_tasks import (
    COGNITIVE_TASKS,
    _check_database,
    _check_redis,
    _task_wrapper,
    self_heal_check,
)


class TestTaskRegistry:
    """All 11 cognitive tasks must be registered."""

    EXPECTED_TASKS: ClassVar[list[str]] = [
        "cognitive_fact_analysis",
        "cognitive_drift_check",
        "cognitive_health_score",
        "cognitive_report_daily",
        "cognitive_report_weekly",
        "embedding_sync",
        "guard_audit",
        "self_heal_check",
        "container_log_audit",
        "hitl_escalation",
        "accuracy_eval",
    ]

    def test_all_tasks_registered(self) -> None:
        for name in self.EXPECTED_TASKS:
            assert name in COGNITIVE_TASKS, f"Task '{name}' not in COGNITIVE_TASKS"

    def test_registry_count(self) -> None:
        assert len(COGNITIVE_TASKS) == 11

    def test_all_tasks_are_callable(self) -> None:
        for name, fn in COGNITIVE_TASKS.items():
            assert callable(fn), f"COGNITIVE_TASKS['{name}'] is not callable"


class TestTaskWrapper:
    """Test the _task_wrapper decorator."""

    @pytest.mark.asyncio
    async def test_successful_task_output(self) -> None:
        @_task_wrapper("test_task")
        async def my_task(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"items": 42}

        result = await my_task({"job_try": 1, "job_id": "test-123"})

        assert result["task"] == "test_task"
        assert result["status"] == "completed"
        assert result["items"] == 42
        assert "elapsed_ms" in result
        assert result["job_try"] == 1

    @pytest.mark.asyncio
    async def test_failed_task_retries(self) -> None:
        call_count = 0

        @_task_wrapper("retry_task", max_retries=3)
        async def failing_task(ctx: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            raise ValueError("intentional failure")

        with pytest.raises(ValueError, match="intentional failure"):
            await failing_task({"job_try": 1, "job_id": "retry-test"})

    @pytest.mark.asyncio
    async def test_exhausted_retries_returns_failed(self) -> None:
        @_task_wrapper("exhaust_task", max_retries=3)
        async def failing_task(ctx: dict[str, Any]) -> dict[str, Any]:
            raise ValueError("always fails")

        result = await failing_task({"job_try": 3, "job_id": "exhaust-test"})

        assert result["status"] == "failed"
        assert result["retries_exhausted"] is True

    @pytest.mark.asyncio
    async def test_none_result_handled(self) -> None:
        @_task_wrapper("none_task")
        async def none_task(ctx: dict[str, Any]) -> dict[str, Any]:
            return None  # type: ignore[return-value]

        result = await none_task({"job_try": 1, "job_id": "none-test"})
        assert result["status"] == "completed"


class TestCheckDatabase:
    """S7503 fix: _check_database must use asyncio.to_thread."""

    @pytest.mark.asyncio
    async def test_uses_asyncio_to_thread(self) -> None:
        """_check_database wraps sync SQLAlchemy in asyncio.to_thread."""
        to_thread_called = False

        async def mock_to_thread(fn: Any, *args: Any, **kwargs: Any) -> None:
            nonlocal to_thread_called
            to_thread_called = True
            await asyncio.sleep(0)

        with patch(
            "internalcmdb.workers.cognitive_tasks.asyncio.to_thread", side_effect=mock_to_thread
        ):
            await _check_database({})

        assert to_thread_called, "_check_database must call asyncio.to_thread"

    @pytest.mark.asyncio
    async def test_probe_failure_propagates(self) -> None:
        """Database connectivity failure must propagate as an exception."""

        async def mock_to_thread(fn: Any, *args: Any, **kwargs: Any) -> None:
            await asyncio.sleep(0)
            raise ConnectionError("DB unreachable")

        with (
            patch(
                "internalcmdb.workers.cognitive_tasks.asyncio.to_thread", side_effect=mock_to_thread
            ),
            pytest.raises(ConnectionError, match="DB unreachable"),
        ):
            await _check_database({})


class TestCheckRedis:
    """_check_redis must handle missing and present redis contexts."""

    @pytest.mark.asyncio
    async def test_no_redis_in_context(self) -> None:
        await _check_redis({})

    @pytest.mark.asyncio
    async def test_redis_ping_called(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        await _check_redis({"redis": mock_redis})
        mock_redis.ping.assert_awaited_once()


class TestCognitiveTaskExecution:
    """Each cognitive task must be awaitable and return structured output."""

    @pytest.fixture
    def ctx(self) -> dict[str, Any]:
        return {"job_try": 1, "job_id": "unit-test"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "task_name",
        [
            "cognitive_fact_analysis",
            "cognitive_drift_check",
            "cognitive_health_score",
            "cognitive_report_daily",
            "cognitive_report_weekly",
            "embedding_sync",
            "guard_audit",
            "hitl_escalation",
            "accuracy_eval",
        ],
    )
    async def test_task_returns_completed(self, ctx: dict[str, Any], task_name: str) -> None:
        task_fn = COGNITIVE_TASKS[task_name]

        with (
            patch("internalcmdb.workers.cognitive_tasks.asyncio.to_thread", new_callable=AsyncMock),
            patch("internalcmdb.workers.cognitive_tasks._check_redis", new_callable=AsyncMock),
        ):
            result = await task_fn(ctx)

        assert result["status"] == "completed"
        assert result["task"] == task_name
        assert isinstance(result["elapsed_ms"], int)


class TestSelfHealCheck:
    """Dedicated tests for the self_heal_check task with mocked DB and Docker."""

    @pytest.fixture
    def ctx(self) -> dict[str, Any]:
        return {"job_try": 1, "job_id": "self-heal-test"}

    @pytest.mark.asyncio
    async def test_no_hosts_above_threshold(self, ctx: dict[str, Any]) -> None:
        """When all disks are below threshold, no plans are proposed."""
        host_data = [
            {
                "host_id": "aaaa-bbbb",
                "host_code": "orchestrator",
                "disk_payload": {"disks": [{"mountpoint": "/", "used_pct": "60%"}]},
            },
        ]

        # Plain ``def`` is correct here: ``patch`` creates an ``AsyncMock``
        # for ``asyncio.to_thread`` (which is async), and ``AsyncMock`` wraps
        # any regular callable's return value in a coroutine automatically.
        # Using ``async def`` would add no value and violates S7503.
        def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
            if fn.__name__ == "_query_disk_health":
                return host_data, set[str]()
            return None

        with patch(
            "internalcmdb.workers.cognitive_tasks.asyncio.to_thread", side_effect=_fake_to_thread
        ):
            result = await self_heal_check(ctx)

        assert result["candidates_evaluated"] == 1
        assert result["plans_proposed"] == 0
        assert result["plans_executed"] == 0

    @pytest.mark.asyncio
    async def test_host_above_threshold_not_orchestrator(self, ctx: dict[str, Any]) -> None:
        """Remote hosts get an insight but no auto-heal."""
        host_data = [
            {
                "host_id": "cccc-dddd",
                "host_code": "hz.113",
                "disk_payload": {"disks": [{"mountpoint": "/", "used_pct": "92%"}]},
            },
        ]
        insight_created: list[bool] = []

        # Plain ``def``: AsyncMock wraps return values; no ``await`` needed.
        def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
            name = getattr(fn, "__name__", "")
            if name == "_query_disk_health":
                return host_data, set[str]()
            if name == "_insert":
                insight_created.append(True)
            return None

        with patch(
            "internalcmdb.workers.cognitive_tasks.asyncio.to_thread", side_effect=_fake_to_thread
        ):
            result = await self_heal_check(ctx)

        assert result["plans_proposed"] == 1
        assert result["plans_executed"] == 0
        assert len(insight_created) == 1

    @pytest.mark.asyncio
    async def test_recently_healed_host_skipped(self, ctx: dict[str, Any]) -> None:
        """Hosts healed within the last hour are not re-evaluated."""
        host_data = [
            {
                "host_id": "eeee-ffff",
                "host_code": "orchestrator",
                "disk_payload": {"disks": [{"mountpoint": "/", "used_pct": "95%"}]},
            },
        ]

        # Plain ``def``: AsyncMock wraps return values; no ``await`` needed.
        def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
            if fn.__name__ == "_query_disk_health":
                return host_data, {"eeee-ffff"}
            return None

        with patch(
            "internalcmdb.workers.cognitive_tasks.asyncio.to_thread", side_effect=_fake_to_thread
        ):
            result = await self_heal_check(ctx)

        assert result["plans_proposed"] == 0

    @pytest.mark.asyncio
    async def test_orchestrator_auto_heal_no_socket(self, ctx: dict[str, Any]) -> None:
        """Orchestrator without Docker socket creates insight but no auto-heal."""
        host_data = [
            {
                "host_id": "1111-2222",
                "host_code": "orchestrator",
                "disk_payload": {"disks": [{"mountpoint": "/", "used_pct": "90%"}]},
            },
        ]
        insights: list[bool] = []

        # Plain ``def``: AsyncMock wraps return values; no ``await`` needed.
        def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
            name = getattr(fn, "__name__", "")
            if name == "_query_disk_health":
                return host_data, set[str]()
            if name == "_insert":
                insights.append(True)
            return None

        with (
            patch(
                "internalcmdb.workers.cognitive_tasks.asyncio.to_thread",
                side_effect=_fake_to_thread,
            ),
            patch("internalcmdb.cognitive.self_heal_disk.os.path.exists", return_value=False),
        ):
            result = await self_heal_check(ctx)

        assert result["plans_proposed"] == 1
        assert result["plans_executed"] == 0


class TestExtractRootDiskPct:
    """Tests for _extract_root_disk_pct utility."""

    def test_parses_percentage_string(self) -> None:
        from internalcmdb.workers.cognitive_tasks import _extract_root_disk_pct  # noqa: PLC0415

        payload = {"disks": [{"mountpoint": "/", "used_pct": "87.5%"}]}
        assert _extract_root_disk_pct(payload) == pytest.approx(87.5)  # pyright: ignore[reportUnknownMemberType]

    def test_parses_numeric_value(self) -> None:
        from internalcmdb.workers.cognitive_tasks import _extract_root_disk_pct  # noqa: PLC0415

        payload = {"disks": [{"mountpoint": "/", "used_pct": 92}]}
        assert _extract_root_disk_pct(payload) == pytest.approx(92.0)  # pyright: ignore[reportUnknownMemberType]

    def test_no_root_disk_returns_zero(self) -> None:
        from internalcmdb.workers.cognitive_tasks import _extract_root_disk_pct  # noqa: PLC0415

        payload = {"disks": [{"mountpoint": "/data", "used_pct": "99%"}]}
        assert _extract_root_disk_pct(payload) == pytest.approx(0.0)  # pyright: ignore[reportUnknownMemberType]

    def test_empty_payload_returns_zero(self) -> None:
        from internalcmdb.workers.cognitive_tasks import _extract_root_disk_pct  # noqa: PLC0415

        assert _extract_root_disk_pct({}) == pytest.approx(0.0)  # pyright: ignore[reportUnknownMemberType]
        assert _extract_root_disk_pct({"disks": None}) == pytest.approx(0.0)  # pyright: ignore[reportUnknownMemberType]
