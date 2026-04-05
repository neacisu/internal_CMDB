"""Tests for internalcmdb.slo.burn_rate."""

from __future__ import annotations

from internalcmdb.slo.burn_rate import (
    FAST_BURN_THRESHOLD,
    SLOW_BURN_THRESHOLD,
    BurnRateCalculator,
    BurnRateResult,
)


def test_constants() -> None:
    assert FAST_BURN_THRESHOLD == 14.4
    assert SLOW_BURN_THRESHOLD == 1.0


def test_zero_total_events() -> None:
    calc = BurnRateCalculator()
    r = calc.calculate(0, 0, 0.999, 24.0)
    assert r == BurnRateResult(
        burn_rate=0.0,
        is_fast_burn=False,
        is_slow_burn=False,
        budget_remaining_pct=100.0,
    )


def test_zero_window() -> None:
    calc = BurnRateCalculator()
    r = calc.calculate(100, 100, 0.999, 0.0)
    assert r.burn_rate == 0.0
    assert r.budget_remaining_pct == 100.0


def test_zero_error_budget_target_one() -> None:
    calc = BurnRateCalculator()
    r = calc.calculate(100, 100, 1.0, 24.0)
    assert r.budget_remaining_pct == 0.0
    assert r.burn_rate == 0.0


def test_perfect_slo() -> None:
    calc = BurnRateCalculator()
    r = calc.calculate(1000, 1000, 0.99, 24.0)
    assert r.burn_rate == 0.0
    assert not r.is_fast_burn
    assert not r.is_slow_burn


def test_slow_burn_range() -> None:
    calc = BurnRateCalculator()
    # High error rate relative to small budget → burn between 1 and 14.4
    r = calc.calculate(50, 100, 0.999, 24.0)
    assert r.burn_rate > 0
    if r.is_fast_burn:
        assert r.burn_rate >= FAST_BURN_THRESHOLD
    elif r.is_slow_burn:
        assert SLOW_BURN_THRESHOLD <= r.burn_rate < FAST_BURN_THRESHOLD
