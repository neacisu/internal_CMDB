"""Prometheus metric families for InternalCMDB.

Exposes application-level metrics for scraping at ``/metrics``.
All metric objects are module-level singletons so they can be imported
and updated from any part of the application.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# API request instrumentation
# ---------------------------------------------------------------------------

API_REQUEST_DURATION = Histogram(
    "cmdb_api_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "path", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ---------------------------------------------------------------------------
# LLM call instrumentation
# ---------------------------------------------------------------------------

LLM_CALL_DURATION = Histogram(
    "cmdb_llm_call_duration_seconds",
    "LLM invocation duration in seconds",
    labelnames=["model", "endpoint", "status"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

LLM_TOKENS_TOTAL = Counter(
    "cmdb_llm_tokens_total",
    "Total LLM tokens processed",
    labelnames=["model", "direction"],
)

# ---------------------------------------------------------------------------
# Governance guard decisions
# ---------------------------------------------------------------------------

GUARD_DECISIONS_TOTAL = Counter(
    "cmdb_guard_decisions_total",
    "Governance guard gate decisions",
    labelnames=["level", "result"],
)

# ---------------------------------------------------------------------------
# HITL queue
# ---------------------------------------------------------------------------

HITL_QUEUE_SIZE = Gauge(
    "cmdb_hitl_queue_size",
    "Current HITL queue depth",
    labelnames=["priority", "status"],
)

# ---------------------------------------------------------------------------
# Collector ingest
# ---------------------------------------------------------------------------

COLLECTOR_INGEST_TOTAL = Counter(
    "cmdb_collector_ingest_total",
    "Total snapshots ingested per host and kind",
    labelnames=["host", "kind"],
)

# ---------------------------------------------------------------------------
# Health score
# ---------------------------------------------------------------------------

HEALTH_SCORE = Gauge(
    "cmdb_health_score",
    "Composite health score (0-100) per entity",
    labelnames=["entity_type", "entity_id"],
)

# ---------------------------------------------------------------------------
# Self-heal actions
# ---------------------------------------------------------------------------

SELF_HEAL_ACTIONS_TOTAL = Counter(
    "cmdb_self_heal_actions_total",
    "Self-healing playbook executions",
    labelnames=["playbook", "result"],
)
