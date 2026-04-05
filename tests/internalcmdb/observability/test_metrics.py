"""Tests for observability.metrics — correct label names."""
from __future__ import annotations
from prometheus_client import Counter, Gauge, Histogram


def test_metrics_importable():
    from internalcmdb.observability import metrics
    assert metrics is not None


def test_api_request_duration_is_histogram():
    from internalcmdb.observability.metrics import API_REQUEST_DURATION
    assert isinstance(API_REQUEST_DURATION, Histogram)


def test_llm_call_duration_is_histogram():
    from internalcmdb.observability.metrics import LLM_CALL_DURATION
    assert isinstance(LLM_CALL_DURATION, Histogram)


def test_llm_tokens_total_is_counter():
    from internalcmdb.observability.metrics import LLM_TOKENS_TOTAL
    assert isinstance(LLM_TOKENS_TOTAL, Counter)


def test_guard_decisions_total_is_counter():
    from internalcmdb.observability.metrics import GUARD_DECISIONS_TOTAL
    assert isinstance(GUARD_DECISIONS_TOTAL, Counter)


def test_hitl_queue_size_is_gauge():
    from internalcmdb.observability.metrics import HITL_QUEUE_SIZE
    assert isinstance(HITL_QUEUE_SIZE, Gauge)


def test_collector_ingest_total_is_counter():
    from internalcmdb.observability.metrics import COLLECTOR_INGEST_TOTAL
    assert isinstance(COLLECTOR_INGEST_TOTAL, Counter)


def test_health_score_is_gauge():
    from internalcmdb.observability.metrics import HEALTH_SCORE
    assert isinstance(HEALTH_SCORE, Gauge)


def test_self_heal_actions_total_is_counter():
    from internalcmdb.observability.metrics import SELF_HEAL_ACTIONS_TOTAL
    assert isinstance(SELF_HEAL_ACTIONS_TOTAL, Counter)


def test_metrics_can_be_incremented():
    from internalcmdb.observability.metrics import GUARD_DECISIONS_TOTAL
    before = GUARD_DECISIONS_TOTAL.labels(level="L4", result="block")._value.get()
    GUARD_DECISIONS_TOTAL.labels(level="L4", result="block").inc()
    after = GUARD_DECISIONS_TOTAL.labels(level="L4", result="block")._value.get()
    assert after == before + 1.0


def test_hitl_queue_size_can_be_set():
    from internalcmdb.observability.metrics import HITL_QUEUE_SIZE
    HITL_QUEUE_SIZE.labels(priority="high", status="pending").set(42)
    val = HITL_QUEUE_SIZE.labels(priority="high", status="pending")._value.get()
    assert val == 42.0
