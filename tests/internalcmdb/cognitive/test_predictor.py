"""Unit tests for predictive analytics helpers and public API."""

from __future__ import annotations

import pytest

from internalcmdb.cognitive.predictor import (
    PredictiveAnalytics,
    RegressionResult,
    _capacity_days_to_pct_threshold,
    _cert_renewal_urgency,
    _cpu_capacity_recommendation,
    _failure_risk_level,
    _merge_capacity_recommendations,
)


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (0, "critical"),
        (7, "critical"),
        (8, "warning"),
        (30, "warning"),
        (31, "info"),
    ],
)
def test_cert_renewal_urgency(days: int, expected: str) -> None:
    assert _cert_renewal_urgency(days) == expected


@pytest.mark.parametrize(
    ("prob", "expected"),
    [
        (0.0, "low"),
        (0.29, "low"),
        (0.3, "medium"),
        (0.59, "medium"),
        (0.6, "high"),
        (0.79, "high"),
        (0.8, "critical"),
        (1.0, "critical"),
    ],
)
def test_failure_risk_level(prob: float, expected: str) -> None:
    assert _failure_risk_level(prob) == expected


def test_capacity_days_to_threshold_no_growth() -> None:
    assert _capacity_days_to_pct_threshold(50.0, 80.0, 0.0) == 0
    assert _capacity_days_to_pct_threshold(85.0, 80.0, 1.0) == 0


def test_capacity_days_to_threshold_positive() -> None:
    # (80 - 50) / 2 = 15 days
    assert _capacity_days_to_pct_threshold(50.0, 80.0, 2.0) == 15


def test_merge_capacity_recommendations_empty_trend_stable() -> None:
    recs, trend = _merge_capacity_recommendations(None, None)
    assert trend == "stable"
    assert len(recs) == 1
    assert "sufficient" in recs[0].lower()


def test_merge_capacity_recommendations_growing_when_cpu() -> None:
    recs, trend = _merge_capacity_recommendations("CPU up", None)
    assert trend == "growing"
    assert recs == ["CPU up"]


def test_predict_disk_exhaustion_returns_host_scoped_payload() -> None:
    pa = PredictiveAnalytics()
    out = pa.predict_disk_exhaustion("host-prod-1")
    assert out["host_id"] == "host-prod-1"
    assert "days_until_full" in out
    assert "confidence" in out


def test_predict_capacity_needs_uses_regression_helpers() -> None:
    pa = PredictiveAnalytics()
    out = pa.predict_capacity_needs("cluster-a")
    assert out["cluster_id"] == "cluster-a"
    assert out["growth_trend"] in {"growing", "stable", "unknown"}
    assert isinstance(out["recommendations"], list)


def test_cpu_capacity_recommendation_respects_slope_threshold() -> None:
    low_slope = RegressionResult(slope=0.4, intercept=0.0, r_squared=0.9, n=5)
    assert _cpu_capacity_recommendation(low_slope, [40.0, 41.0]) is None
    high_slope = RegressionResult(slope=0.6, intercept=0.0, r_squared=0.9, n=5)
    msg = _cpu_capacity_recommendation(high_slope, [40.0, 50.0])
    assert msg is not None
    assert "CPU" in msg
    assert "80%" in msg
