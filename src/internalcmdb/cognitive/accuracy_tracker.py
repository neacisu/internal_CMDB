"""F6.4 — Accuracy Tracker: compute precision/recall/F1 from HITL feedback.

Queries ``governance.hitl_feedback`` to build a confusion matrix, then derives
standard classification metrics.  Alerts are raised when accuracy drops below
a configurable threshold.

Usage::

    from internalcmdb.cognitive.accuracy_tracker import AccuracyTracker

    tracker = AccuracyTracker(async_session)
    metrics = await tracker.compute_metrics(model="Qwen/QwQ-32B-AWQ")
    if metrics.f1 < 0.80:
        print("Accuracy degradation detected!")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 0.80
_MIN_SAMPLES_FOR_METRICS = 5
_BIAS_RATIO_WARN = 0.2

_HITL_FEEDBACK_METRICS_SQL = """
    SELECT
        COUNT(*) FILTER (WHERE agreement = true)           AS tp,
        COUNT(*) FILTER (WHERE agreement = false
                          AND correction_type = 'false_positive')
                                                           AS fp,
        COUNT(*) FILTER (WHERE agreement = false
                          AND correction_type = 'false_negative')
                                                           AS fn,
        COUNT(*) FILTER (WHERE agreement IS NOT NULL)       AS total,
        COUNT(*) FILTER (WHERE agreement = true)            AS positive_count,
        COUNT(*) FILTER (WHERE agreement = false)           AS negative_count,
        MIN(created_at)::text                               AS period_start,
        MAX(created_at)::text                               AS period_end
    FROM governance.hitl_feedback
    WHERE {where_clause}
"""


@dataclass(frozen=True)
class AccuracyMetrics:
    """Classification metrics derived from HITL feedback data."""

    precision: float
    recall: float
    f1: float
    total_samples: int
    period_start: str
    period_end: str
    warnings: list[str] = field(default_factory=lambda: [])


@dataclass(frozen=True)
class _ConfusionAggregate:
    """Intermediate counts from the feedback aggregation query."""

    tp: int
    fp: int
    fn: int
    total: int
    positive_count: int
    negative_count: int
    period_start: str
    period_end: str


def _hitl_feedback_where_clause(
    model: str | None,
    template_id: str | None,
    staleness_days: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build SQL WHERE fragment and bound parameters (no raw user SQL)."""
    filters: list[str] = []
    params: dict[str, Any] = {}

    if model:
        filters.append(
            "(prompt_template_id::text = :model"
            " OR hitl_item_id IN ("
            "   SELECT item_id FROM governance.hitl_item"
            "   WHERE llm_model_used = :model))"
        )
        params["model"] = model

    if template_id:
        filters.append(
            "(hitl_item_id IN ("
            "  SELECT item_id FROM governance.hitl_item"
            "  WHERE correlation_id::text LIKE '%' || :tmpl || '%'"
            "))"
        )
        params["tmpl"] = template_id

    if staleness_days is not None and staleness_days > 0:
        filters.append("created_at >= now() - interval '1 day' * :stale_days")
        params["stale_days"] = staleness_days

    where_clause = " AND ".join(filters) if filters else "1=1"
    return where_clause, params


def _confusion_from_row(row: Any | None) -> _ConfusionAggregate:
    """Map a single aggregate row to numeric confusion counts."""
    if row is None:
        return _ConfusionAggregate(0, 0, 0, 0, 0, 0, "", "")

    return _ConfusionAggregate(
        tp=int(row[0] or 0),
        fp=int(row[1] or 0),
        fn=int(row[2] or 0),
        total=int(row[3] or 0),
        positive_count=int(row[4] or 0),
        negative_count=int(row[5] or 0),
        period_start=str(row[6] or ""),
        period_end=str(row[7] or ""),
    )


def _precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Standard binary metrics from true / false positive and false negative counts."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    denom = precision + recall
    f1 = (2 * precision * recall / denom) if denom > 0 else 0.0
    return precision, recall, f1


def _detect_bias(agg: _ConfusionAggregate) -> str | None:
    """Detect feedback bias — returns a warning string or None."""
    if agg.total < _MIN_SAMPLES_FOR_METRICS:
        return None
    positive_ratio = agg.positive_count / agg.total if agg.total > 0 else 0.5
    if positive_ratio < _BIAS_RATIO_WARN:
        return (
            f"FEEDBACK_BIAS: only {agg.positive_count}/{agg.total} "
            f"({positive_ratio:.1%}) positive — heavily negative-skewed"
        )
    if positive_ratio > (1.0 - _BIAS_RATIO_WARN):
        return (
            f"FEEDBACK_BIAS: {agg.positive_count}/{agg.total} "
            f"({positive_ratio:.1%}) positive — heavily positive-skewed"
        )
    return None


def _to_accuracy_metrics(
    agg: _ConfusionAggregate,
    precision: float,
    recall: float,
    f1: float,
    extra_warnings: list[str] | None = None,
) -> AccuracyMetrics:
    """Round and package for API / monitoring consumers."""
    warnings: list[str] = list(extra_warnings or [])

    if agg.total < _MIN_SAMPLES_FOR_METRICS:
        warnings.append(
            f"INSUFFICIENT_SAMPLES: {agg.total} < {_MIN_SAMPLES_FOR_METRICS} minimum — "
            f"metrics may be unreliable"
        )

    bias_warn = _detect_bias(agg)
    if bias_warn:
        warnings.append(bias_warn)

    return AccuracyMetrics(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        total_samples=agg.total,
        period_start=agg.period_start,
        period_end=agg.period_end,
        warnings=warnings,
    )


class AccuracyTracker:
    """Computes and monitors LLM prediction accuracy against human decisions.

    Args:
        session: Async SQLAlchemy session.
        alert_threshold: F1 score below which an alert is logged (default 0.80).
    """

    def __init__(
        self,
        session: AsyncSession,
        alert_threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        self._session = session
        self._threshold = alert_threshold

    def _log_f1_below_threshold(
        self,
        *,
        total: int,
        f1: float,
        precision: float,
        recall: float,
        model: str | None,
    ) -> None:
        """Emit a single structured warning when sample size and F1 warrant it."""
        if total <= 0:
            return
        if f1 >= self._threshold:
            return

        logger.warning(
            "Accuracy below threshold: F1=%.4f (threshold=%.2f, "
            "precision=%.4f, recall=%.4f, n=%d, model=%s)",
            f1,
            self._threshold,
            precision,
            recall,
            total,
            model or "all",
        )

    async def compute_metrics(
        self,
        model: str | None = None,
        template_id: str | None = None,
        staleness_days: int | None = None,
        persist_snapshot: bool = False,
    ) -> AccuracyMetrics:
        """Compute precision, recall, and F1 from hitl_feedback.

        The confusion matrix treats ``agreement = true`` as true-positive and
        ``agreement = false`` with ``correction_type = 'false_positive'`` vs
        ``'false_negative'`` for the remaining quadrants.

        Args:
            model: Optional model filter.
            template_id: Optional template correlation filter.
            staleness_days: Only consider feedback from the last N days.
                            None means all data (no recency filter).
            persist_snapshot: When True, saves the computed metrics to
                              ``telemetry.metric_point`` for historical tracking.
        """
        where_clause, params = _hitl_feedback_where_clause(
            model,
            template_id,
            staleness_days,
        )
        sql = _HITL_FEEDBACK_METRICS_SQL.format(where_clause=where_clause)

        result = await self._session.execute(text(sql), params)
        agg = _confusion_from_row(result.fetchone())

        precision, recall, f1 = _precision_recall_f1(agg.tp, agg.fp, agg.fn)
        metrics = _to_accuracy_metrics(agg, precision, recall, f1)

        self._log_f1_below_threshold(
            total=agg.total,
            f1=f1,
            precision=precision,
            recall=recall,
            model=model,
        )

        if f1 < self._threshold and agg.total >= _MIN_SAMPLES_FOR_METRICS:
            await self._emit_accuracy_alert(model, f1, precision, recall, agg.total)

        if persist_snapshot:
            await self._persist_snapshot(model, metrics)

        return metrics

    async def _emit_accuracy_alert(
        self,
        model: str | None,
        f1: float,
        precision: float,
        recall: float,
        total: int,
    ) -> None:
        """Best-effort: emit accuracy degradation notification."""
        try:
            from internalcmdb.governance.notifications import notify_hitl_event  # noqa: PLC0415

            await notify_hitl_event(
                "accuracy_degradation",
                {
                    "model": model or "all",
                    "f1": round(f1, 4),
                    "precision": round(precision, 4),
                    "recall": round(recall, 4),
                    "total_samples": total,
                    "threshold": self._threshold,
                    "detected_at": datetime.now(tz=UTC).isoformat(),
                },
            )
        except Exception:
            logger.debug("Accuracy alert notification failed", exc_info=True)

    async def _persist_snapshot(
        self,
        model: str | None,
        metrics: AccuracyMetrics,
    ) -> None:
        """Persist a metric snapshot to telemetry.metric_point."""
        try:
            import json as _json  # noqa: PLC0415

            labels = _json.dumps(
                {
                    "model": model or "all",
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "total_samples": metrics.total_samples,
                    "warnings": metrics.warnings,
                },
                default=str,
            )
            await self._session.execute(
                text("""
                    INSERT INTO telemetry.metric_point
                        (host_id, metric_name, metric_value, labels_jsonb)
                    VALUES
                        (NULL, :name, :value, :labels::jsonb)
                """),
                {
                    "name": "accuracy_tracker.f1_score",
                    "value": metrics.f1,
                    "labels": labels,
                },
            )
            await self._session.commit()
        except Exception:
            logger.debug("Snapshot persistence failed", exc_info=True)

    async def get_trend(
        self,
        model: str | None = None,
        window_days: int = 7,
        buckets: int = 12,
    ) -> list[dict[str, Any]]:
        """Compute accuracy trend over time windows.

        Returns a list of dicts with keys: bucket_start, bucket_end,
        accuracy, sample_count.
        """
        params: dict[str, Any] = {"days": window_days, "buckets": buckets}
        model_filter = ""
        if model:
            model_filter = (
                "AND (hf.prompt_template_id::text = :model"
                " OR hf.hitl_item_id IN ("
                "   SELECT item_id FROM governance.hitl_item"
                "   WHERE llm_model_used = :model))"
            )
            params["model"] = model

        result = await self._session.execute(
            text(
                "WITH bounds AS ("
                "  SELECT now() - interval '1 day' * :days AS range_start, now() AS range_end"
                "), buckets AS ("
                "  SELECT generate_series("
                "    (SELECT range_start FROM bounds),"
                "    (SELECT range_end   FROM bounds),"
                "    ((SELECT range_end - range_start FROM bounds) / :buckets)"
                "  ) AS bucket_start"
                ") SELECT b.bucket_start::text,"
                "  (b.bucket_start + ((SELECT range_end - range_start FROM bounds) / :buckets))::text"  # noqa: E501
                "      AS bucket_end,"
                "  COUNT(*) FILTER (WHERE hf.agreement IS NOT NULL) AS sample_count,"
                "  CASE WHEN COUNT(*) FILTER (WHERE hf.agreement IS NOT NULL) > 0"
                "       THEN ROUND("
                "           COUNT(*) FILTER (WHERE hf.agreement = true)::numeric"
                "           / COUNT(*) FILTER (WHERE hf.agreement IS NOT NULL)::numeric, 4)"
                "       ELSE NULL END AS accuracy"
                "  FROM buckets b"
                "  LEFT JOIN governance.hitl_feedback hf"
                "    ON hf.created_at >= b.bucket_start"
                "   AND hf.created_at < b.bucket_start"
                "       + ((SELECT range_end - range_start FROM bounds) / :buckets)"
                "  " + model_filter + "  GROUP BY b.bucket_start ORDER BY b.bucket_start"
            ),
            params,
        )
        return [
            {
                "bucket_start": r[0],
                "bucket_end": r[1],
                "sample_count": int(r[2] or 0),
                "accuracy": float(r[3]) if r[3] is not None else None,
            }
            for r in result.fetchall()
        ]
