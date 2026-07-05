"""Tests for llm.cost — cost accounting from telemetry.llm_call_log."""

from __future__ import annotations

from unittest.mock import MagicMock

from internalcmdb.llm.cost import compute_cost_summary


def test_compute_cost_summary_aggregates() -> None:
    row = MagicMock()
    row.model_id = "Qwen/QwQ-32B-AWQ"
    row.call_count = 10
    row.input_tokens = 1_000_000
    row.output_tokens = 500_000

    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [row]
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn

    summary = compute_cost_summary(engine, since_hours=24)

    assert summary["totals"]["call_count"] == 10
    assert summary["totals"]["input_tokens"] == 1_000_000
    assert summary["totals"]["estimated_usd"] > 0
    assert summary["models"][0]["model_id"] == "Qwen/QwQ-32B-AWQ"


def test_compute_cost_summary_query_failure() -> None:
    engine = MagicMock()
    engine.connect.side_effect = RuntimeError("db down")
    summary = compute_cost_summary(engine)
    assert summary["error"] == "query_failed"
    assert summary["totals"]["call_count"] == 0
