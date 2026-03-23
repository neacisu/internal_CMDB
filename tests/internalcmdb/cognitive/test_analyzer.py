"""Tests for the FactAnalyzer — anomaly detection with sample data."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from internalcmdb.cognitive.analyzer import AnalysisResult, FactAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_baseline_row(
    mean: float, stddev: float, count: int
) -> MagicMock:
    """Simulate the SQLAlchemy row returned by _fetch_baseline."""
    row = MagicMock()
    row.mean = mean
    row.stddev = stddev
    row.cnt = count
    return row


# ---------------------------------------------------------------------------
# FactAnalyzer tests
# ---------------------------------------------------------------------------


class TestFactAnalyzer:
    @pytest.fixture
    def mock_async_session(self) -> MagicMock:
        session = MagicMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def analyzer(self, mock_async_session: MagicMock) -> FactAnalyzer:
        return FactAnalyzer(mock_async_session)

    @pytest.mark.asyncio
    async def test_non_numeric_fact_returns_info(self, analyzer: FactAnalyzer) -> None:
        result = await analyzer.analyze_fact({
            "entity_id": "host-1",
            "fact_namespace": "service",
            "fact_key": "status",
            "fact_value_jsonb": {"value": "running"},
        })
        assert result.is_anomaly is False
        assert result.severity == "info"
        assert result.category == "reliability"

    @pytest.mark.asyncio
    async def test_numeric_normal_value(
        self, analyzer: FactAnalyzer, mock_async_session: MagicMock
    ) -> None:
        baseline_row = _make_baseline_row(mean=50.0, stddev=10.0, count=100)
        result_mock = MagicMock()
        result_mock.one.return_value = baseline_row
        mock_async_session.execute.return_value = result_mock

        result = await analyzer.analyze_fact({
            "entity_id": "host-1",
            "fact_namespace": "cpu",
            "fact_key": "usage_pct",
            "fact_value_jsonb": {"value": 55.0},
        })
        assert result.is_anomaly is False
        assert result.severity == "info"
        assert result.category == "performance"

    @pytest.mark.asyncio
    async def test_numeric_warning_anomaly(
        self, analyzer: FactAnalyzer, mock_async_session: MagicMock
    ) -> None:
        baseline_row = _make_baseline_row(mean=50.0, stddev=10.0, count=100)
        result_mock = MagicMock()
        result_mock.one.return_value = baseline_row
        mock_async_session.execute.return_value = result_mock

        # Z-score = |75 - 50| / 10 = 2.5 → warning
        result = await analyzer.analyze_fact({
            "entity_id": "host-1",
            "fact_namespace": "cpu",
            "fact_key": "usage_pct",
            "fact_value_jsonb": {"value": 75.0},
        })
        assert result.is_anomaly is True
        assert result.severity == "warning"

    @pytest.mark.asyncio
    async def test_numeric_critical_anomaly(
        self, analyzer: FactAnalyzer, mock_async_session: MagicMock
    ) -> None:
        baseline_row = _make_baseline_row(mean=50.0, stddev=5.0, count=100)
        result_mock = MagicMock()
        result_mock.one.return_value = baseline_row
        mock_async_session.execute.return_value = result_mock

        # Z-score = |70 - 50| / 5 = 4.0 → critical
        result = await analyzer.analyze_fact({
            "entity_id": "host-1",
            "fact_namespace": "memory",
            "fact_key": "used_pct",
            "fact_value_jsonb": {"value": 70.0},
        })
        assert result.is_anomaly is True
        assert result.severity == "critical"
        assert result.category == "performance"

    @pytest.mark.asyncio
    async def test_insufficient_data(
        self, analyzer: FactAnalyzer, mock_async_session: MagicMock
    ) -> None:
        baseline_row = _make_baseline_row(mean=10.0, stddev=0.0, count=2)
        result_mock = MagicMock()
        result_mock.one.return_value = baseline_row
        mock_async_session.execute.return_value = result_mock

        result = await analyzer.analyze_fact({
            "entity_id": "host-1",
            "fact_namespace": "disk",
            "fact_key": "free_gb",
            "fact_value_jsonb": {"value": 100.0},
        })
        assert result.is_anomaly is False
        assert "Insufficient" in result.explanation

    @pytest.mark.asyncio
    async def test_zero_variance_baseline_skips_zscore(
        self, analyzer: FactAnalyzer, mock_async_session: MagicMock
    ) -> None:
        """n ≥ 3 dar pop-stddev ≈ 0 → fără împărțire la stddev (``math.isclose`` la 0)."""
        baseline_row = _make_baseline_row(mean=42.0, stddev=0.0, count=20)
        result_mock = MagicMock()
        result_mock.one.return_value = baseline_row
        mock_async_session.execute.return_value = result_mock

        result = await analyzer.analyze_fact({
            "entity_id": "host-1",
            "fact_namespace": "cpu",
            "fact_key": "usage_pct",
            "fact_value_jsonb": {"value": 99.0},
        })
        assert result.is_anomaly is False
        assert "Insufficient" in result.explanation
        assert "n=20" in result.explanation

    @pytest.mark.asyncio
    async def test_security_namespace_category(self, analyzer: FactAnalyzer) -> None:
        result = await analyzer.analyze_fact({
            "entity_id": "host-1",
            "fact_namespace": "sshd",
            "fact_key": "failed_logins",
            "fact_value_jsonb": {"value": "many"},
        })
        assert result.category == "security"

    def test_classify_category_unknown(self) -> None:
        assert FactAnalyzer._classify_category("unknown.namespace") == "reliability"

    def test_classify_category_disk(self) -> None:
        assert FactAnalyzer._classify_category("disk.usage") == "capacity"
