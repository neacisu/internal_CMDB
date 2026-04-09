"""Tests for internalcmdb.workers.queue — WorkerSettings and helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# WorkerSettings attribute tests
# ---------------------------------------------------------------------------


class TestWorkerSettings:
    def _get_worker_settings(self):
        """Import WorkerSettings with mocked dependencies."""
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379"

        with (
            patch("internalcmdb.api.config.get_settings", return_value=mock_settings),
            patch("arq.connections.RedisSettings.from_dsn", return_value=MagicMock()),
        ):
            from internalcmdb.workers.queue import WorkerSettings  # noqa: PLC0415

            return WorkerSettings

    def test_worker_settings_queue_name(self):
        ws = self._get_worker_settings()
        assert ws.queue_name == "infraq:arq:queue"

    def test_worker_settings_max_jobs(self):
        ws = self._get_worker_settings()
        assert ws.max_jobs == 10

    def test_worker_settings_job_timeout(self):
        ws = self._get_worker_settings()
        assert ws.job_timeout == 600

    def test_worker_settings_max_tries(self):
        ws = self._get_worker_settings()
        assert ws.max_tries == 3

    def test_worker_settings_health_check_interval(self):
        ws = self._get_worker_settings()
        assert ws.health_check_interval == 60

    def test_worker_settings_functions_present(self):
        ws = self._get_worker_settings()
        function_names = [f.__name__ if callable(f) else str(f) for f in ws.functions]
        assert "data_retention_job" in function_names

    def test_worker_settings_functions_include_noop(self):
        ws = self._get_worker_settings()
        function_names = [f.__name__ for f in ws.functions if callable(f)]
        assert "_noop" in function_names

    def test_worker_settings_functions_include_health_check(self):
        ws = self._get_worker_settings()
        function_names = [f.__name__ for f in ws.functions if callable(f)]
        assert "_health_check" in function_names

    def test_worker_settings_cron_jobs_defined(self):
        ws = self._get_worker_settings()
        assert ws.cron_jobs is not None
        assert len(ws.cron_jobs) >= 1


# ---------------------------------------------------------------------------
# _health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379"

        with (
            patch("internalcmdb.api.config.get_settings", return_value=mock_settings),
            patch("arq.connections.RedisSettings.from_dsn", return_value=MagicMock()),
        ):
            from internalcmdb.workers.queue import _health_check  # noqa: PLC0415

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        ctx = {"redis": mock_redis}
        result = await _health_check(ctx)

        assert result["status"] == "healthy"
        assert result["max_jobs"] == 10

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379"

        with (
            patch("internalcmdb.api.config.get_settings", return_value=mock_settings),
            patch("arq.connections.RedisSettings.from_dsn", return_value=MagicMock()),
        ):
            from internalcmdb.workers.queue import _health_check  # noqa: PLC0415

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("ping failed"))

        ctx = {"redis": mock_redis}
        result = await _health_check(ctx)

        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_no_redis_in_ctx(self):
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379"

        with (
            patch("internalcmdb.api.config.get_settings", return_value=mock_settings),
            patch("arq.connections.RedisSettings.from_dsn", return_value=MagicMock()),
        ):
            from internalcmdb.workers.queue import _health_check  # noqa: PLC0415

        ctx = {}
        result = await _health_check(ctx)

        assert result["status"] == "healthy"


# ---------------------------------------------------------------------------
# _noop
# ---------------------------------------------------------------------------


class TestNoop:
    @pytest.mark.asyncio
    async def test_noop_returns_none(self):
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379"

        with (
            patch("internalcmdb.api.config.get_settings", return_value=mock_settings),
            patch("arq.connections.RedisSettings.from_dsn", return_value=MagicMock()),
        ):
            from internalcmdb.workers.queue import _noop  # noqa: PLC0415

        ctx = {}
        result = await _noop(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_noop_no_errors(self):
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379"

        with (
            patch("internalcmdb.api.config.get_settings", return_value=mock_settings),
            patch("arq.connections.RedisSettings.from_dsn", return_value=MagicMock()),
        ):
            from internalcmdb.workers.queue import _noop  # noqa: PLC0415

        await _noop({"redis": AsyncMock(), "job_id": "test-123"})
