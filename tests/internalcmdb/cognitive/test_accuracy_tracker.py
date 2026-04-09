"""Teste pentru AccuracyTracker (F6.4) — confuzie, metrici, bias, compute_metrics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.cognitive.accuracy_tracker import (
    AccuracyTracker,
    _confusion_from_row,
    _ConfusionAggregate,
    _detect_bias,
    _hitl_feedback_where_clause,
    _precision_recall_f1,
)

# ---------------------------------------------------------------------------
# _hitl_feedback_where_clause
# ---------------------------------------------------------------------------


class TestHitlFeedbackWhereClause:
    def test_no_filters_returns_always_true(self) -> None:
        clause, params = _hitl_feedback_where_clause(None, None, None)
        assert clause == "1=1"
        assert params == {}

    def test_model_only(self) -> None:
        clause, params = _hitl_feedback_where_clause("Qwen/QwQ-32B", None, None)
        assert ":model" in clause
        assert params["model"] == "Qwen/QwQ-32B"

    def test_template_id_only(self) -> None:
        clause, params = _hitl_feedback_where_clause(None, "tmpl-audit", None)
        assert ":tmpl" in clause
        assert params["tmpl"] == "tmpl-audit"

    def test_staleness_days_only(self) -> None:
        clause, params = _hitl_feedback_where_clause(None, None, 30)
        assert ":stale_days" in clause
        assert params["stale_days"] == 30

    def test_staleness_zero_ignored(self) -> None:
        clause, params = _hitl_feedback_where_clause(None, None, 0)
        assert clause == "1=1"
        assert "stale_days" not in params

    def test_all_filters_combined(self) -> None:
        clause, params = _hitl_feedback_where_clause("m1", "tmpl-x", 7)
        assert "AND" in clause
        assert params["model"] == "m1"
        assert params["tmpl"] == "tmpl-x"
        assert params["stale_days"] == 7

    def test_model_and_staleness(self) -> None:
        clause, params = _hitl_feedback_where_clause("m2", None, 14)
        assert ":model" in clause
        assert ":stale_days" in clause
        assert "tmpl" not in params


# ---------------------------------------------------------------------------
# _confusion_from_row
# ---------------------------------------------------------------------------


class TestConfusionFromRow:
    def test_none_row_returns_zeros(self) -> None:
        agg = _confusion_from_row(None)
        assert agg.tp == 0
        assert agg.fp == 0
        assert agg.fn == 0
        assert agg.total == 0

    def test_row_with_values(self) -> None:
        row = (10, 2, 3, 15, 10, 5, "2024-01-01", "2024-01-31")
        agg = _confusion_from_row(row)
        assert agg.tp == 10
        assert agg.fp == 2
        assert agg.fn == 3
        assert agg.total == 15
        assert agg.positive_count == 10
        assert agg.negative_count == 5

    def test_row_with_none_values_defaults_to_zero(self) -> None:
        row = (None, None, None, None, None, None, None, None)
        agg = _confusion_from_row(row)
        assert agg.tp == 0
        assert agg.total == 0


# ---------------------------------------------------------------------------
# _precision_recall_f1
# ---------------------------------------------------------------------------


class TestPrecisionRecallF1:
    def test_perfect_prediction(self) -> None:
        p, r, f1 = _precision_recall_f1(tp=10, fp=0, fn=0)
        assert p == pytest.approx(1.0)
        assert r == pytest.approx(1.0)
        assert f1 == pytest.approx(1.0)

    def test_zero_division_all_zeros(self) -> None:
        p, r, f1 = _precision_recall_f1(tp=0, fp=0, fn=0)
        assert p == pytest.approx(0.0, abs=1e-9)
        assert r == pytest.approx(0.0, abs=1e-9)
        assert f1 == pytest.approx(0.0, abs=1e-9)

    def test_normal_case(self) -> None:
        p, r, f1 = _precision_recall_f1(tp=8, fp=2, fn=3)
        assert abs(p - 0.8) < 1e-9
        assert abs(r - 8 / 11) < 1e-9
        assert f1 > 0.0

    def test_all_fp_no_tp(self) -> None:
        p, r, f1 = _precision_recall_f1(tp=0, fp=5, fn=0)
        assert p == pytest.approx(0.0, abs=1e-9)
        assert r == pytest.approx(0.0, abs=1e-9)
        assert f1 == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# _detect_bias
# ---------------------------------------------------------------------------


class TestDetectBias:
    def _agg(self, pos: int, neg: int) -> _ConfusionAggregate:
        total = pos + neg
        return _ConfusionAggregate(
            tp=pos,
            fp=0,
            fn=0,
            total=total,
            positive_count=pos,
            negative_count=neg,
            period_start="",
            period_end="",
        )

    def test_too_few_samples_returns_none(self) -> None:
        agg = self._agg(pos=2, neg=1)
        assert _detect_bias(agg) is None

    def test_heavily_negative_skewed(self) -> None:
        agg = self._agg(pos=1, neg=9)
        result = _detect_bias(agg)
        assert result is not None
        assert "negative" in result.lower()

    def test_heavily_positive_skewed(self) -> None:
        agg = self._agg(pos=9, neg=1)
        result = _detect_bias(agg)
        assert result is not None
        assert "positive" in result.lower()

    def test_balanced_returns_none(self) -> None:
        agg = self._agg(pos=5, neg=5)
        assert _detect_bias(agg) is None


# ---------------------------------------------------------------------------
# AccuracyTracker.compute_metrics
# ---------------------------------------------------------------------------


def _make_session_with_row(row: tuple | None) -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.fetchone.return_value = row
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


class TestAccuracyTrackerComputeMetrics:
    @pytest.mark.asyncio
    async def test_all_tp_perfect_score(self) -> None:
        row = (10, 0, 0, 10, 10, 0, "2024-01-01", "2024-01-31")
        session = _make_session_with_row(row)
        tracker = AccuracyTracker(session)
        metrics = await tracker.compute_metrics()
        assert metrics.precision == pytest.approx(1.0)
        assert metrics.recall == pytest.approx(1.0)
        assert metrics.f1 == pytest.approx(1.0)
        assert metrics.total_samples == 10

    @pytest.mark.asyncio
    async def test_empty_data_returns_zero_metrics(self) -> None:
        session = _make_session_with_row(None)
        tracker = AccuracyTracker(session)
        metrics = await tracker.compute_metrics()
        assert metrics.f1 == pytest.approx(0.0, abs=1e-9)
        assert metrics.total_samples == 0

    @pytest.mark.asyncio
    async def test_below_threshold_triggers_warning(self) -> None:
        row = (3, 5, 5, 13, 3, 10, "2024-01-01", "2024-01-31")
        session = _make_session_with_row(row)
        tracker = AccuracyTracker(session, alert_threshold=0.80)
        with patch(
            "internalcmdb.cognitive.accuracy_tracker.AccuracyTracker._emit_accuracy_alert",
            new_callable=AsyncMock,
        ) as mock_alert:
            await tracker.compute_metrics()
            mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_snapshot_calls_second_execute(self) -> None:
        row = (10, 0, 0, 10, 10, 0, "2024-01-01", "2024-01-31")
        session = _make_session_with_row(row)
        tracker = AccuracyTracker(session)
        await tracker.compute_metrics(persist_snapshot=True)
        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_model_filter_forwarded(self) -> None:
        row = (5, 1, 1, 7, 5, 2, "2024-01-01", "2024-01-15")
        session = _make_session_with_row(row)
        tracker = AccuracyTracker(session)
        metrics = await tracker.compute_metrics(model="Qwen/QwQ-32B-AWQ")
        assert metrics.total_samples == 7

    @pytest.mark.asyncio
    async def test_insufficient_samples_warning_in_metrics(self) -> None:
        row = (2, 0, 0, 2, 2, 0, "2024-01-01", "2024-01-05")
        session = _make_session_with_row(row)
        tracker = AccuracyTracker(session)
        metrics = await tracker.compute_metrics()
        assert any("INSUFFICIENT_SAMPLES" in w for w in metrics.warnings)

    @pytest.mark.asyncio
    async def test_no_alert_when_above_threshold(self) -> None:
        row = (9, 1, 0, 10, 9, 1, "2024-01-01", "2024-01-31")
        session = _make_session_with_row(row)
        tracker = AccuracyTracker(session, alert_threshold=0.80)
        with patch(
            "internalcmdb.cognitive.accuracy_tracker.AccuracyTracker._emit_accuracy_alert",
            new_callable=AsyncMock,
        ) as mock_alert:
            await tracker.compute_metrics()
            mock_alert.assert_not_called()
