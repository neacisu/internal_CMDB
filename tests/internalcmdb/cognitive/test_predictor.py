"""Unit tests for predictive analytics helpers and public API."""

from __future__ import annotations

from unittest.mock import MagicMock

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


# ---------------------------------------------------------------------------
# _get_risk_factors — resource_pressure via system_vitals payload
# ---------------------------------------------------------------------------


def _make_session_with_vitals(payload_jsonb: object) -> MagicMock:
    """Build a minimal SQLAlchemy session mock returning a given vitals payload."""
    session = MagicMock()

    # err_row (err_count = 5)
    err_row = MagicMock()
    err_row.__getitem__ = lambda self, k: 5 if k == "err_count" else None

    # vitals_row
    vitals_row: MagicMock | None
    if payload_jsonb is None:
        vitals_row = None
    else:
        vitals_row = MagicMock()
        vitals_row.__getitem__ = lambda self, k: payload_jsonb if k == "payload_jsonb" else None
        vitals_row.__bool__ = lambda self: True

    # age_row (age_days = 90)
    age_row = MagicMock()
    age_row.__getitem__ = lambda self, k: 90 if k == "age_days" else None

    # fail_row (cnt = 2)
    fail_row = MagicMock()
    fail_row.__getitem__ = lambda self, k: 2 if k == "cnt" else None

    call_count = {"n": 0}

    def _execute_side_effect(query, params=None):
        call_count["n"] += 1
        count = call_count["n"]
        # Call order: 1=err_count, 2=vitals, 3=age, 4=fail
        row = [err_row, vitals_row, age_row, fail_row][min(count - 1, 3)]
        result = MagicMock()
        m = MagicMock()
        m.first.return_value = row
        result.mappings.return_value = m
        return result

    session.execute.side_effect = _execute_side_effect
    return session


def test_get_risk_factors_with_full_vitals_payload() -> None:
    """cpu=80%, mem=60% -> resource_pressure=(80+60)/200=0.7."""
    payload = {"cpu_times": {"percent": 80.0}, "memory": {"percent": 60.0}}
    session = _make_session_with_vitals(payload)
    pa = PredictiveAnalytics(session=session)
    factors = pa._get_risk_factors("entity-001")

    assert factors["resource_pressure_factor"] == pytest.approx(0.7, abs=1e-3)


def test_get_risk_factors_zero_cpu_and_memory() -> None:
    """cpu=0%, mem=0% -> resource_pressure=0.0."""
    payload = {"cpu_times": {"percent": 0.0}, "memory": {"percent": 0.0}}
    session = _make_session_with_vitals(payload)
    pa = PredictiveAnalytics(session=session)
    factors = pa._get_risk_factors("entity-002")

    assert factors["resource_pressure_factor"] == pytest.approx(0.0, abs=1e-3)


def test_get_risk_factors_100_percent_pressure() -> None:
    """cpu=100%, mem=100% -> resource_pressure=1.0 (maximum)."""
    payload = {"cpu_times": {"percent": 100.0}, "memory": {"percent": 100.0}}
    session = _make_session_with_vitals(payload)
    pa = PredictiveAnalytics(session=session)
    factors = pa._get_risk_factors("entity-003")

    assert factors["resource_pressure_factor"] == pytest.approx(1.0, abs=1e-3)


def test_get_risk_factors_missing_cpu_times_key_defaults_to_50() -> None:
    """Payload without cpu_times key uses default 50% -> (50+60)/200=0.55."""
    payload = {"memory": {"percent": 60.0}}
    session = _make_session_with_vitals(payload)
    pa = PredictiveAnalytics(session=session)
    factors = pa._get_risk_factors("entity-004")

    assert factors["resource_pressure_factor"] == pytest.approx(0.55, abs=1e-3)


def test_get_risk_factors_missing_memory_key_defaults_to_50() -> None:
    """Payload without memory key uses default 50% -> (80+50)/200=0.65."""
    payload = {"cpu_times": {"percent": 80.0}}
    session = _make_session_with_vitals(payload)
    pa = PredictiveAnalytics(session=session)
    factors = pa._get_risk_factors("entity-005")

    assert factors["resource_pressure_factor"] == pytest.approx(0.65, abs=1e-3)


def test_get_risk_factors_empty_payload_defaults_both_to_50() -> None:
    """An empty payload dict {} is falsy — the vitals block is skipped, pressure=0.25."""
    payload: dict[str, object] = {}
    session = _make_session_with_vitals(payload)
    pa = PredictiveAnalytics(session=session)
    factors = pa._get_risk_factors("entity-006")

    # {} is falsy in Python, so `if vitals_row and vitals_row["payload_jsonb"]:` is False
    assert factors["resource_pressure_factor"] == pytest.approx(0.25, abs=1e-3)


def test_get_risk_factors_null_vitals_row_uses_fallback_pressure() -> None:
    """None vitals_row -> resource_pressure stays at fallback 0.25."""
    session = _make_session_with_vitals(None)
    pa = PredictiveAnalytics(session=session)
    factors = pa._get_risk_factors("entity-007")

    assert factors["resource_pressure_factor"] == pytest.approx(0.25, abs=1e-3)


def test_get_risk_factors_no_session_returns_fallback() -> None:
    """With no DB session the constant fallback values are returned."""
    pa = PredictiveAnalytics()
    factors = pa._get_risk_factors("any-entity")

    assert factors["resource_pressure_factor"] == pytest.approx(0.25, abs=1e-3)
    assert factors["age_factor"] == pytest.approx(0.3, abs=1e-3)
    assert "sample_count" in factors


def test_get_risk_factors_cpu_times_none_value_treated_as_empty_dict() -> None:
    """cpu_times present but None -> (payload.get('cpu_times') or {}) -> {} -> default 50."""
    payload = {"cpu_times": None, "memory": {"percent": 40.0}}
    session = _make_session_with_vitals(payload)
    pa = PredictiveAnalytics(session=session)
    factors = pa._get_risk_factors("entity-008")

    assert factors["resource_pressure_factor"] == pytest.approx((50.0 + 40.0) / 200.0, abs=1e-3)


# ---------------------------------------------------------------------------
# predict_failure_probability — end-to-end with fallback (no session)
# ---------------------------------------------------------------------------


def test_predict_failure_probability_structure() -> None:
    """predict_failure_probability returns all documented keys."""
    pa = PredictiveAnalytics()
    out = pa.predict_failure_probability("host-test")

    assert out["entity_id"] == "host-test"
    assert "failure_probability" in out
    assert out["risk_level"] in {"low", "medium", "high", "critical"}
    assert "factors" in out
    assert "confidence" in out
    assert "confidence_interval" in out
    assert "lower" in out["confidence_interval"]
    assert "upper" in out["confidence_interval"]
    assert "predicted_at" in out


def test_predict_failure_probability_bounded() -> None:
    """Probability must always be in [0, 1] with valid CI."""
    pa = PredictiveAnalytics()
    out = pa.predict_failure_probability("host-extreme")

    assert 0.0 <= out["failure_probability"] <= 1.0
    assert out["confidence_interval"]["lower"] <= out["failure_probability"]
    assert out["confidence_interval"]["upper"] >= out["failure_probability"]
