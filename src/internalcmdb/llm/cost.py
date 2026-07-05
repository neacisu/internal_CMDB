"""LLM cost accounting from telemetry.llm_call_log (F5.4)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Estimated USD per 1M tokens — configurable via SettingsStore in production
_DEFAULT_COST_PER_M_INPUT = 0.15
_DEFAULT_COST_PER_M_OUTPUT = 0.60


@dataclass(frozen=True)
class ModelCostSummary:
    """Cost rollup for a single model."""

    model_id: str
    call_count: int
    input_tokens: int
    output_tokens: int
    estimated_usd: float


def compute_cost_summary(
    engine: Engine,
    *,
    since_hours: int = 24,
    cost_per_m_input: float = _DEFAULT_COST_PER_M_INPUT,
    cost_per_m_output: float = _DEFAULT_COST_PER_M_OUTPUT,
) -> dict[str, Any]:
    """Aggregate LLM costs from ``telemetry.llm_call_log``.

    Returns per-model summaries and fleet-wide totals for the given window.
    """
    since = datetime.now(tz=UTC) - timedelta(hours=since_hours)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT model_id,
                           COUNT(*)::bigint AS call_count,
                           COALESCE(SUM(input_tokens), 0)::bigint AS input_tokens,
                           COALESCE(SUM(output_tokens), 0)::bigint AS output_tokens
                    FROM telemetry.llm_call_log
                    WHERE called_at >= :since
                      AND status = 'ok'
                    GROUP BY model_id
                    ORDER BY call_count DESC
                """),
                {"since": since},
            ).fetchall()
    except Exception:
        logger.warning("compute_cost_summary: llm_call_log query failed", exc_info=True)
        return {
            "since": since.isoformat(),
            "since_hours": since_hours,
            "models": [],
            "totals": {"call_count": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0.0},
            "error": "query_failed",
        }

    models: list[ModelCostSummary] = []
    total_calls = 0
    total_in = 0
    total_out = 0
    total_usd = 0.0

    for row in rows:
        in_tok = int(row.input_tokens)
        out_tok = int(row.output_tokens)
        usd = (in_tok / 1_000_000 * cost_per_m_input) + (out_tok / 1_000_000 * cost_per_m_output)
        models.append(
            ModelCostSummary(
                model_id=row.model_id,
                call_count=int(row.call_count),
                input_tokens=in_tok,
                output_tokens=out_tok,
                estimated_usd=round(usd, 4),
            )
        )
        total_calls += int(row.call_count)
        total_in += in_tok
        total_out += out_tok
        total_usd += usd

    return {
        "since": since.isoformat(),
        "since_hours": since_hours,
        "models": [
            {
                "model_id": m.model_id,
                "call_count": m.call_count,
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "estimated_usd": m.estimated_usd,
            }
            for m in models
        ],
        "totals": {
            "call_count": total_calls,
            "input_tokens": total_in,
            "output_tokens": total_out,
            "estimated_usd": round(total_usd, 4),
        },
    }
