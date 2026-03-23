"""Burn-rate calculator for SLO error budgets.

Thresholds follow Google SRE multi-window alerting practice:
  - Fast burn: 14.4× the budget consumption rate  → page immediately
  - Slow burn: 1.0× the budget consumption rate   → create a ticket
"""

from __future__ import annotations

from dataclasses import dataclass


FAST_BURN_THRESHOLD = 14.4
SLOW_BURN_THRESHOLD = 1.0


@dataclass(frozen=True, slots=True)
class BurnRateResult:
    """Result of a burn-rate calculation."""

    burn_rate: float
    is_fast_burn: bool
    is_slow_burn: bool
    budget_remaining_pct: float


class BurnRateCalculator:
    """Stateless calculator for SLO burn rate and remaining budget."""

    def calculate(
        self,
        good_events: int,
        total_events: int,
        target: float,
        window_hours: float,
    ) -> BurnRateResult:
        """Compute burn rate and remaining budget.

        Args:
            good_events: number of successful events in the window
            total_events: total events in the window
            target: SLO target as a fraction (e.g. 0.999)
            window_hours: length of the SLO window in hours

        Returns:
            BurnRateResult with burn_rate, burn classification, and remaining budget.
        """
        if total_events == 0 or window_hours <= 0:
            return BurnRateResult(
                burn_rate=0.0,
                is_fast_burn=False,
                is_slow_burn=False,
                budget_remaining_pct=100.0,
            )

        error_budget = 1.0 - target
        if error_budget <= 0:
            return BurnRateResult(
                burn_rate=0.0,
                is_fast_burn=False,
                is_slow_burn=False,
                budget_remaining_pct=0.0,
            )

        error_rate = 1.0 - (good_events / total_events)
        burn_rate = error_rate / error_budget

        budget_consumed_pct = (error_rate / error_budget) * 100.0
        budget_remaining_pct = max(0.0, 100.0 - budget_consumed_pct)

        return BurnRateResult(
            burn_rate=round(burn_rate, 4),
            is_fast_burn=burn_rate >= FAST_BURN_THRESHOLD,
            is_slow_burn=SLOW_BURN_THRESHOLD <= burn_rate < FAST_BURN_THRESHOLD,
            budget_remaining_pct=round(budget_remaining_pct, 2),
        )
