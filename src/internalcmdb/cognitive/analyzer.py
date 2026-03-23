"""F2.1 — Fact Analyzer: anomaly detection and classification for observed facts.

Analyses incoming ``ObservedFact``-style payloads against historical baselines
using Z-score anomaly detection on numeric values and rule-based classification
for severity and category.

Usage::

    from internalcmdb.cognitive.analyzer import FactAnalyzer

    analyzer = FactAnalyzer(db_session)
    result = await analyzer.analyze_fact(fact_payload)
    if result.is_anomaly:
        print(f"{result.severity}: {result.explanation}")
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.models.discovery import ObservedFact

# Z-score thresholds for anomaly classification.
_Z_CRITICAL = 3.0
_Z_WARNING = 2.0
# Pop stddev is ~0 when all historical samples are identical; avoid ``== 0.0`` (S1244).
_STDDEV_NEAR_ZERO_ABS_TOL = 1e-12

# fact_namespace → category mapping (aligned with taxonomy_seed domains).
_NAMESPACE_CATEGORY: dict[str, str] = {
    "cpu": "performance",
    "memory": "performance",
    "load": "performance",
    "disk": "capacity",
    "filesystem": "capacity",
    "storage": "capacity",
    "network": "performance",
    "security": "security",
    "sshd": "security",
    "tls": "security",
    "firewall": "security",
    "service": "reliability",
    "container": "reliability",
    "systemd": "reliability",
    "uptime": "reliability",
}


@dataclass(frozen=True)
class AnalysisResult:
    """Outcome of a single fact analysis.

    Attributes:
        is_anomaly:  True when the observed value deviates significantly
                     from the historical baseline.
        severity:    ``"critical"`` | ``"warning"`` | ``"info"``.
        category:    ``"performance"`` | ``"security"`` | ``"capacity"`` | ``"reliability"``.
        confidence:  0.0–1.0 confidence in the classification.
        explanation: Human-readable description of the finding.
    """

    is_anomaly: bool
    severity: str
    category: str
    confidence: float
    explanation: str


class FactAnalyzer:
    """Stateless analyser — requires an async SQLAlchemy session for
    historical baseline queries.

    Args:
        session: An ``AsyncSession`` connected to the InternalCMDB database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def analyze_fact(self, fact_payload: dict[str, Any] | None) -> AnalysisResult:
        """Analyse a single observed-fact payload.

        Expected keys in *fact_payload* (matching ``ObservedFact`` columns):
            - ``entity_id`` (str | UUID)
            - ``fact_namespace`` (str)
            - ``fact_key`` (str)
            - ``fact_value_jsonb`` (dict — must contain a ``"value"`` key
              for numeric analysis)

        Returns an :class:`AnalysisResult`.
        """
        if not fact_payload:
            return AnalysisResult(
                is_anomaly=False,
                severity="info",
                category="reliability",
                confidence=0.0,
                explanation="Empty or None payload — analysis skipped.",
            )

        namespace = fact_payload.get("fact_namespace", "")
        fact_key = fact_payload.get("fact_key", "")
        entity_id = fact_payload.get("entity_id")

        if not entity_id:
            return AnalysisResult(
                is_anomaly=False,
                severity="info",
                category=self._classify_category(namespace),
                confidence=0.0,
                explanation=(
                    f"Missing entity_id for '{namespace}.{fact_key}' — "
                    f"cannot compute baseline."
                ),
            )

        value_container = fact_payload.get("fact_value_jsonb") or {}
        raw_value = value_container.get("value")
        category = self._classify_category(namespace)

        if raw_value is not None and isinstance(raw_value, (int, float)):
            numeric = float(raw_value)
            if math.isnan(numeric) or math.isinf(numeric):
                return AnalysisResult(
                    is_anomaly=False,
                    severity="info",
                    category=category,
                    confidence=0.0,
                    explanation=(
                        f"Non-finite numeric value ({numeric}) for "
                        f"'{namespace}.{fact_key}' — analysis skipped."
                    ),
                )
            return await self._numeric_analysis(
                entity_id=entity_id,
                namespace=namespace,
                fact_key=fact_key,
                value=numeric,
                category=category,
            )

        return AnalysisResult(
            is_anomaly=False,
            severity="info",
            category=category,
            confidence=0.5,
            explanation=(
                f"Non-numeric fact '{namespace}.{fact_key}' recorded — "
                f"no anomaly detection applicable."
            ),
        )

    async def _numeric_analysis(
        self,
        *,
        entity_id: Any,
        namespace: str,
        fact_key: str,
        value: float,
        category: str,
    ) -> AnalysisResult:
        """Z-score anomaly detection against the historical baseline for
        this entity + namespace + key combination."""
        mean, stddev, sample_count = await self._fetch_baseline(
            entity_id, namespace, fact_key,
        )

        if sample_count < 3 or math.isclose(
            stddev, 0.0, abs_tol=_STDDEV_NEAR_ZERO_ABS_TOL, rel_tol=0.0
        ):
            return AnalysisResult(
                is_anomaly=False,
                severity="info",
                category=category,
                confidence=round(min(sample_count / 30.0, 1.0), 4),
                explanation=(
                    f"Insufficient historical data for '{namespace}.{fact_key}' "
                    f"(n={sample_count}). Value={value}, baseline mean={mean:.4f}."
                ),
            )

        z_score = abs(value - mean) / stddev

        if z_score >= _Z_CRITICAL:
            severity = "critical"
            is_anomaly = True
        elif z_score >= _Z_WARNING:
            severity = "warning"
            is_anomaly = True
        else:
            severity = "info"
            is_anomaly = False

        confidence = round(min(1.0, 1.0 - math.exp(-z_score)), 4)

        return AnalysisResult(
            is_anomaly=is_anomaly,
            severity=severity,
            category=category,
            confidence=confidence,
            explanation=(
                f"{'ANOMALY' if is_anomaly else 'Normal'}: "
                f"'{namespace}.{fact_key}' = {value} "
                f"(mean={mean:.4f}, stddev={stddev:.4f}, z={z_score:.2f}, "
                f"n={sample_count})."
            ),
        )

    async def _fetch_baseline(
        self,
        entity_id: Any,
        namespace: str,
        fact_key: str,
    ) -> tuple[float, float, int]:
        """Compute mean, stddev, and sample count from historical observed facts.

        Extracts the numeric value from ``fact_value_jsonb->>'value'`` and
        computes aggregate statistics filtered by entity, namespace, and key.
        """
        numeric_expr = ObservedFact.fact_value_jsonb["value"].as_float()

        stmt = select(
            func.avg(numeric_expr).label("mean"),
            func.stddev_pop(numeric_expr).label("stddev"),
            func.count().label("cnt"),
        ).where(
            ObservedFact.entity_id == entity_id,
            ObservedFact.fact_namespace == namespace,
            ObservedFact.fact_key == fact_key,
            ObservedFact.fact_value_jsonb["value"].isnot(None),
        )

        result = await self._session.execute(stmt)
        row = result.one()

        mean = float(row.mean) if row.mean is not None else 0.0
        stddev = float(row.stddev) if row.stddev is not None else 0.0
        count = int(row.cnt)

        return mean, stddev, count

    @staticmethod
    def _classify_category(namespace: str) -> str:
        """Map a fact namespace to one of the four canonical categories."""
        ns_lower = namespace.lower().split(".")[0]
        return _NAMESPACE_CATEGORY.get(ns_lower, "reliability")
