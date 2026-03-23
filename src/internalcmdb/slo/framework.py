"""SLO Framework — define SLOs, track error budgets, evaluate burn rates.

Backed by telemetry.slo_definition and telemetry.slo_measurement tables.
Burn-rate thresholds follow Google SRE multi-window alerting:
  fast burn = 14.4× budget consumption, slow burn = 1.0× budget consumption.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .burn_rate import BurnRateCalculator, BurnRateResult

logger = logging.getLogger(__name__)


class SLOFramework:
    """Manage SLO definitions and evaluate current error budgets."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._calc = BurnRateCalculator()

    async def define_slo(
        self,
        service_id: str,
        sli_type: str,
        target: float,
        window_days: int = 30,
    ) -> dict[str, Any]:
        """Create a new SLO definition. Returns the created record."""
        if not (0.0 < target <= 1.0):
            raise ValueError(f"SLO target must be in (0.0, 1.0], got {target}")
        if not (1 <= window_days <= 365):
            raise ValueError(f"window_days must be in [1, 365], got {window_days}")

        slo_id = str(uuid.uuid4())
        await self._session.execute(
            text("""
                INSERT INTO telemetry.slo_definition
                    (slo_id, service_id, sli_type, target, window_days)
                VALUES (:slo_id, :service_id, :sli_type, :target, :window_days)
            """),
            {
                "slo_id": slo_id,
                "service_id": service_id,
                "sli_type": sli_type,
                "target": target,
                "window_days": window_days,
            },
        )
        await self._session.commit()
        return {
            "slo_id": slo_id,
            "service_id": service_id,
            "sli_type": sli_type,
            "target": target,
            "window_days": window_days,
        }

    async def current_budget(self, slo_id: str) -> dict[str, Any]:
        """Remaining error budget, burn rate, and status for an SLO."""
        defn = await self._session.execute(
            text("SELECT * FROM telemetry.slo_definition WHERE slo_id = :slo_id"),
            {"slo_id": slo_id},
        )
        slo_row = defn.fetchone()
        if slo_row is None:
            return {"error": "SLO not found", "slo_id": slo_id}

        slo = slo_row._mapping
        target = float(slo["target"])
        window_days = int(slo["window_days"])

        measurements = await self._session.execute(
            text("""
                SELECT COALESCE(SUM(good_events), 0) AS good,
                       COALESCE(SUM(total_events), 0) AS total
                FROM telemetry.slo_measurement
                WHERE slo_id = :slo_id
                  AND measured_at >= now() - make_interval(days => :window_days)
            """),
            {"slo_id": slo_id, "window_days": window_days},
        )
        row = measurements.fetchone()
        good = int(row.good) if row else 0  # type: ignore[union-attr]
        total = int(row.total) if row else 0  # type: ignore[union-attr]

        br = self._calc.calculate(good, total, target, window_days * 24)

        status = "ok"
        if br.budget_remaining_pct <= 0:
            status = "exhausted"
        elif br.is_fast_burn:
            status = "fast_burn"
        elif br.is_slow_burn:
            status = "slow_burn"

        return {
            "slo_id": slo_id,
            "target": target,
            "window_days": window_days,
            "good_events": good,
            "total_events": total,
            "burn_rate": br.burn_rate,
            "budget_remaining_pct": br.budget_remaining_pct,
            "is_fast_burn": br.is_fast_burn,
            "is_slow_burn": br.is_slow_burn,
            "status": status,
        }

    async def evaluate_burn_rate(self, slo_id: str) -> dict[str, Any]:
        """Evaluate burn rate and return alert-level information."""
        budget = await self.current_budget(slo_id)
        if "error" in budget:
            return budget

        alert_level = "none"
        if budget["is_fast_burn"]:
            alert_level = "page"
        elif budget["is_slow_burn"]:
            alert_level = "ticket"

        return {
            "slo_id": slo_id,
            "burn_rate": budget["burn_rate"],
            "budget_remaining_pct": budget["budget_remaining_pct"],
            "alert_level": alert_level,
            "is_fast_burn": budget["is_fast_burn"],
            "is_slow_burn": budget["is_slow_burn"],
        }

    async def evaluate_and_notify(self, slo_id: str) -> dict[str, Any]:
        """Evaluate burn rate and dispatch notification on breach."""
        result = await self.evaluate_burn_rate(slo_id)
        if "error" in result:
            return result

        if result["alert_level"] != "none":
            try:
                from internalcmdb.governance.notifications import notify_hitl_event

                await notify_hitl_event(
                    "slo_breach",
                    {
                        "item_id": slo_id,
                        "risk_class": "RC-3" if result["is_fast_burn"] else "RC-2",
                        "priority": "critical" if result["is_fast_burn"] else "high",
                        "status": result["alert_level"],
                        "burn_rate": result["burn_rate"],
                        "budget_remaining_pct": result["budget_remaining_pct"],
                    },
                )
                result["notification_sent"] = True
            except Exception:
                logger.exception("Failed to send SLO breach notification for %s", slo_id)
                result["notification_sent"] = False
        return result

    async def should_heal(self, slo_id: str) -> dict[str, Any]:
        """Decide whether auto-healing should be triggered based on budget state."""
        budget = await self.current_budget(slo_id)
        if "error" in budget:
            return budget

        remaining = budget["budget_remaining_pct"]

        if remaining > 50:
            action = "none"
            reason = "Budget is healthy (>50% remaining)"
        elif remaining > 20:
            action = "warn"
            reason = "Budget is moderately consumed (20-50% remaining)"
        elif remaining > 0:
            action = "heal"
            reason = "Budget is critically low (<20% remaining)"
        else:
            action = "freeze"
            reason = "Budget exhausted — block risky changes"

        return {
            "slo_id": slo_id,
            "budget_remaining_pct": remaining,
            "action": action,
            "reason": reason,
            "should_heal": action in ("heal", "freeze"),
        }
