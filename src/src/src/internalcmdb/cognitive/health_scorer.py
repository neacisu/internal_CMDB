"""F2.3 — Health Scorer: compute health scores for hosts and fleets.

Produces a 0-100 composite health score from four equally-weighted factors:
CPU health, memory health, disk health, and service health (each 0-25).

Thresholds:
    * ``score > 80``  → healthy
    * ``60 ≤ score ≤ 80`` → warning
    * ``score < 60``  → critical

Usage::

    from internalcmdb.cognitive.health_scorer import HealthScorer

    scorer = HealthScorer()
    score = scorer.score_host(host_data)
    fleet = scorer.score_fleet([host1, host2, host3])
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

# Sub-score weight: each factor has a maximum of 25 points.
_MAX_FACTOR_SCORE = 25

# Fleet health score thresholds
_SCORE_HEALTHY_THRESHOLD = 80  # score > this → healthy status
_SCORE_WARNING_THRESHOLD = 60  # score >= this (and <= healthy) → warning status

# Thresholds (percentage utilisation → sub-score mapping).
# Lower utilisation → higher health sub-score.
_UTIL_BREAKPOINTS: list[tuple[float, float]] = [
    (0.0, 1.0),  # 0 % utilisation → 100 % of max factor score
    (50.0, 0.9),  # 50 % → 90 %
    (70.0, 0.7),  # 70 % → 70 %
    (85.0, 0.4),  # 85 % → 40 %
    (95.0, 0.1),  # 95 % → 10 %
    (100.0, 0.0),  # 100 % → 0
]


@dataclass(frozen=True)
class HealthScore:
    """Health assessment for a single entity.

    Attributes:
        entity_id:    Identifier of the scored entity.
        entity_type:  ``"host"`` or other entity kind code.
        score:        Composite health score (0-100).
        breakdown:    Per-factor score mapping.
        timestamp:    ISO-8601 timestamp of when the score was computed.
    """

    entity_id: str
    entity_type: str
    score: int
    breakdown: dict[str, Any]
    timestamp: str


@dataclass(frozen=True)
class FleetHealthScore:
    """Aggregate health assessment across a fleet of hosts.

    Attributes:
        total_hosts:    Number of hosts scored.
        healthy_count:  Hosts with score > 80.
        warning_count:  Hosts with score 60-80.
        critical_count: Hosts with score < 60.
        average_score:  Mean score across the fleet.
        min_score:      Lowest individual score.
        max_score:      Highest individual score.
        host_scores:    Individual :class:`HealthScore` instances.
        timestamp:      ISO-8601 timestamp.
    """

    total_hosts: int
    healthy_count: int
    warning_count: int
    critical_count: int
    average_score: float
    min_score: int
    max_score: int
    host_scores: list[HealthScore] = field(default_factory=lambda: cast(list[HealthScore], []))
    timestamp: str = ""


class HealthScorer:
    """Compute health scores for hosts and fleets."""

    def score_host(self, host_data: dict[str, Any]) -> HealthScore:
        """Score a single host from its metric data.

        Expected keys in *host_data*:
            - ``host_id`` or ``entity_id`` (str)
            - ``cpu_usage_pct`` (float, 0-100)
            - ``memory_usage_pct`` (float, 0-100)
            - ``disk_usage_pct`` (float, 0-100)
            - ``services_total`` (int)
            - ``services_healthy`` (int)
            - ``gpu_usage_pct`` (float, 0-100, optional — only for GPU hosts)
            - ``is_gpu_capable`` (bool, optional)
        """
        entity_id = str(host_data.get("host_id") or host_data.get("entity_id", "unknown"))

        cpu_raw = host_data.get("cpu_usage_pct")
        mem_raw = host_data.get("memory_usage_pct")
        disk_raw = host_data.get("disk_usage_pct")

        missing_metrics: list[str] = []
        cpu_val = self._safe_metric(cpu_raw, "cpu_usage_pct", missing_metrics)
        mem_val = self._safe_metric(mem_raw, "memory_usage_pct", missing_metrics)
        disk_val = self._safe_metric(disk_raw, "disk_usage_pct", missing_metrics)

        cpu = self._utilisation_subscore(cpu_val)
        mem = self._utilisation_subscore(mem_val)
        disk = self._utilisation_subscore(disk_val)
        svc = self._service_subscore(
            total=host_data.get("services_total") or 0,
            healthy=host_data.get("services_healthy") or 0,
        )

        total = cpu + mem + disk + svc

        if missing_metrics:
            penalty = len(missing_metrics) * 5
            total = max(0, total - penalty)

        breakdown: dict[str, Any] = {
            "cpu_health": cpu,
            "memory_health": mem,
            "disk_health": disk,
            "service_health": svc,
            "status": self._status_label(total),
        }

        if missing_metrics:
            breakdown["missing_metrics"] = missing_metrics
            breakdown["missing_penalty"] = len(missing_metrics) * 5

        is_gpu = host_data.get("is_gpu_capable", False)
        gpu_raw = host_data.get("gpu_usage_pct")
        if is_gpu and gpu_raw is not None:
            gpu_val = self._safe_metric(gpu_raw, "gpu_usage_pct", [])
            breakdown["gpu_health"] = self._utilisation_subscore(gpu_val)
        elif is_gpu:
            breakdown["gpu_health_note"] = "GPU-capable but no GPU metrics available"

        return HealthScore(
            entity_id=entity_id,
            entity_type="host",
            score=total,
            breakdown=breakdown,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )

    def score_fleet(self, hosts: list[dict[str, Any]]) -> FleetHealthScore:
        """Score an entire fleet of hosts.

        Args:
            hosts: List of host data dictionaries (same format as ``score_host``).
        """
        scores: list[HealthScore] = []
        for h in hosts:
            scores.append(self.score_host(h))

        if not scores:
            return FleetHealthScore(
                total_hosts=0,
                healthy_count=0,
                warning_count=0,
                critical_count=0,
                average_score=0.0,
                min_score=0,
                max_score=0,
                host_scores=[],
                timestamp=datetime.now(tz=UTC).isoformat(),
            )

        values = [s.score for s in scores]
        healthy = sum(1 for v in values if v > _SCORE_HEALTHY_THRESHOLD)
        warning = sum(
            1 for v in values if _SCORE_WARNING_THRESHOLD <= v <= _SCORE_HEALTHY_THRESHOLD
        )
        critical = sum(1 for v in values if v < _SCORE_WARNING_THRESHOLD)

        return FleetHealthScore(
            total_hosts=len(scores),
            healthy_count=healthy,
            warning_count=warning,
            critical_count=critical,
            average_score=round(statistics.mean(values), 2),
            min_score=min(values),
            max_score=max(values),
            host_scores=scores,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )

    @staticmethod
    def _safe_metric(
        raw: Any,
        name: str,
        missing: list[str],
    ) -> float:
        """Coerce a metric to float, tracking missing/invalid values."""
        if raw is None:
            missing.append(name)
            return 0.0
        try:
            val = float(raw)
        except (TypeError, ValueError):
            missing.append(name)
            return 0.0
        if math.isnan(val) or math.isinf(val):
            missing.append(name)
            return 0.0
        return val

    @staticmethod
    def _utilisation_subscore(usage_pct: float) -> int:
        """Map a utilisation percentage (0-100) to a sub-score (0-25).

        Uses linear interpolation between breakpoints.
        """
        if math.isnan(usage_pct) or math.isinf(usage_pct):
            return 0
        usage_pct = max(0.0, min(100.0, float(usage_pct)))

        prev_util, prev_factor = _UTIL_BREAKPOINTS[0]
        for bp_util, bp_factor in _UTIL_BREAKPOINTS[1:]:
            if usage_pct <= bp_util:
                ratio = (usage_pct - prev_util) / (bp_util - prev_util)
                factor = prev_factor + ratio * (bp_factor - prev_factor)
                return round(factor * _MAX_FACTOR_SCORE)
            prev_util, prev_factor = bp_util, bp_factor

        return 0

    @staticmethod
    def _service_subscore(total: int, healthy: int) -> int:
        """Service health sub-score (0-25) based on healthy/total ratio."""
        if total <= 0:
            return _MAX_FACTOR_SCORE
        ratio = max(0.0, min(1.0, healthy / total))
        return round(ratio * _MAX_FACTOR_SCORE)

    @staticmethod
    def _status_label(score: int) -> str:
        if score > _SCORE_HEALTHY_THRESHOLD:
            return "healthy"
        if score >= _SCORE_WARNING_THRESHOLD:
            return "warning"
        return "critical"
