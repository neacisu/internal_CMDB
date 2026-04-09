"""Seed default runtime settings into config.app_setting.

Run once after migration 0012.  Safe to run multiple times (ON CONFLICT DO NOTHING).

All values here mirror the previous hardcoded constants from:
  - src/internalcmdb/llm/client.py          (LLM endpoints, timeouts, circuit breaker)
  - src/internalcmdb/governance/guard_gate.py (guard URL, fail-closed)
  - src/internalcmdb/governance/hitl_workflow.py (escalation thresholds)
  - src/internalcmdb/workers/cognitive_tasks.py (disk/log self-heal thresholds)
  - src/internalcmdb/llm/budget.py           (token budgets)
  - src/internalcmdb/llm/security.py         (security budgets)
  - src/internalcmdb/workers/retention.py    (retention days)
  - src/internalcmdb/api/config.py           (OTLP, CORS, log level, debug)
"""

from __future__ import annotations

import json
import logging
from typing import Any
from typing import cast as _cast

from sqlalchemy import create_engine, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Seed data
# Each entry: (setting_key, setting_group, default_value, type_hint, description, is_secret, requires_restart)  # noqa: E501
# ---------------------------------------------------------------------------

_SETTINGS: list[tuple[str, str, object, str, str, bool, bool]] = [
    # ── LLM model endpoints ──────────────────────────────────────────────
    (
        "llm.reasoning.url",
        "llm",
        "http://10.0.1.10:49001",
        "url",
        "vLLM QwQ-32B-AWQ endpoint (HAProxy VIP)",
        False,
        False,
    ),
    (
        "llm.fast.url",
        "llm",
        "http://10.0.1.10:49002",
        "url",
        "vLLM Qwen2.5-14B-AWQ endpoint (HAProxy VIP)",
        False,
        False,
    ),
    (
        "llm.embed.url",
        "llm",
        "http://10.0.1.10:49003",
        "url",
        "Ollama Qwen3-Embedding-8B endpoint",
        False,
        False,
    ),
    (
        "llm.guard.url",
        "llm",
        "http://10.0.1.115:8000",
        "url",
        "LLM Guard service endpoint (LXC 115)",
        False,
        False,
    ),
    (
        "llm.reasoning.model_id",
        "llm",
        "Qwen/QwQ-32B-AWQ",
        "string",
        "Model ID for reasoning backend",
        False,
        False,
    ),
    (
        "llm.fast.model_id",
        "llm",
        "Qwen/Qwen2.5-14B-Instruct-AWQ",
        "string",
        "Model ID for fast backend",
        False,
        False,
    ),
    (
        "llm.embed.model_id",
        "llm",
        "qwen3-embedding-8b-q5km",
        "string",
        "Model ID for embedding backend",
        False,
        False,
    ),
    (
        "llm.reasoning.timeout_s",
        "llm",
        120,
        "integer",
        "Request timeout (seconds) for reasoning model",
        False,
        False,
    ),
    (
        "llm.fast.timeout_s",
        "llm",
        60,
        "integer",
        "Request timeout (seconds) for fast model",
        False,
        False,
    ),
    (
        "llm.embed.timeout_s",
        "llm",
        30,
        "integer",
        "Request timeout (seconds) for embed model",
        False,
        False,
    ),
    (
        "llm.guard.timeout_s",
        "llm",
        15,
        "integer",
        "Request timeout (seconds) for guard service",
        False,
        False,
    ),
    (
        "llm.guard.token",
        "llm",
        "",
        "secret",
        "Bearer token for LLM Guard API (empty = no auth)",
        True,
        False,
    ),
    (
        "llm.circuit_breaker.threshold",
        "llm",
        5,
        "integer",
        "Consecutive failures before opening circuit",
        False,
        False,
    ),
    (
        "llm.circuit_breaker.cooldown_s",
        "llm",
        60,
        "integer",
        "Seconds to wait before half-open probe",
        False,
        False,
    ),
    (
        "llm.pool.max_connections",
        "llm",
        100,
        "integer",
        "Max HTTP connections in the client pool",
        False,
        False,
    ),
    (
        "llm.pool.max_keepalive",
        "llm",
        20,
        "integer",
        "Max keepalive connections in the client pool",
        False,
        False,
    ),
    ("llm.max_retries", "llm", 3, "integer", "Max retry attempts per LLM request", False, False),
    # ── Guard & safety ───────────────────────────────────────────────────
    (
        "guard.fail_closed",
        "guard",
        True,
        "boolean",
        "Block actions when guard service is unreachable",
        False,
        False,
    ),
    (
        "guard.timeout_s",
        "guard",
        5.0,
        "float",
        "HTTP timeout for guard service /scan calls (seconds)",
        False,
        False,
    ),
    # ── HITL escalation thresholds ───────────────────────────────────────
    (
        "hitl.rc4.escalation_minutes",
        "hitl",
        15,
        "integer",
        "RC-4 (critical): auto-escalate after N minutes",
        False,
        False,
    ),
    (
        "hitl.rc3.escalation_minutes",
        "hitl",
        60,
        "integer",
        "RC-3 (high): auto-escalate after N minutes",
        False,
        False,
    ),
    (
        "hitl.rc2.escalation_hours",
        "hitl",
        4,
        "integer",
        "RC-2 (medium): auto-escalate after N hours",
        False,
        False,
    ),
    (
        "hitl.max_escalations",
        "hitl",
        3,
        "integer",
        "Max escalations before blocking an HITL item",
        False,
        False,
    ),
    # ── Self-heal thresholds ─────────────────────────────────────────────
    (
        "self_heal.disk_threshold_pct",
        "self_heal",
        85,
        "integer",
        "Root disk usage % that triggers auto-healing",
        False,
        False,
    ),
    (
        "self_heal.log_auto_truncate_bytes",
        "self_heal",
        2147483648,
        "integer",
        "Container log bytes above which auto-truncate fires (2 GB)",
        False,
        False,
    ),
    (
        "self_heal.log_hitl_bytes",
        "self_heal",
        524288000,
        "integer",
        "Container log bytes above which HITL review is created (500 MB)",
        False,
        False,
    ),
    # ── Token budgets ────────────────────────────────────────────────────
    (
        "budget.agent_audit",
        "token_budget",
        200000,
        "integer",
        "Hourly token budget for agent-audit caller",
        False,
        False,
    ),
    (
        "budget.agent_capacity",
        "token_budget",
        150000,
        "integer",
        "Hourly token budget for agent-capacity caller",
        False,
        False,
    ),
    (
        "budget.agent_security",
        "token_budget",
        100000,
        "integer",
        "Hourly token budget for agent-security caller",
        False,
        False,
    ),
    (
        "budget.cognitive_query",
        "token_budget",
        50000,
        "integer",
        "Hourly token budget for cognitive-query caller",
        False,
        False,
    ),
    (
        "budget.report_generator",
        "token_budget",
        300000,
        "integer",
        "Hourly token budget for report-generator caller",
        False,
        False,
    ),
    (
        "budget.chaos_engine",
        "token_budget",
        30000,
        "integer",
        "Hourly token budget for chaos-engine caller",
        False,
        False,
    ),
    (
        "budget.default",
        "token_budget",
        100000,
        "integer",
        "Default hourly token budget for unlisted callers",
        False,
        False,
    ),
    (
        "budget.spike_multiplier",
        "token_budget",
        3.0,
        "float",
        "Usage spike alert threshold (X times rolling average)",
        False,
        False,
    ),
    # ── Data retention (days) ─────────────────────────────────────────────
    (
        "retention.job_history_days",
        "retention",
        90,
        "integer",
        "Days to retain worker job history records",
        False,
        False,
    ),
    (
        "retention.audit_events_days",
        "retention",
        365,
        "integer",
        "Days to retain governance audit events",
        False,
        False,
    ),
    (
        "retention.snapshots_days",
        "retention",
        30,
        "integer",
        "Days to retain collector snapshots",
        False,
        False,
    ),
    (
        "retention.llm_calls_days",
        "retention",
        90,
        "integer",
        "Days to retain LLM call telemetry",
        False,
        False,
    ),
    (
        "retention.metric_points_days",
        "retention",
        30,
        "integer",
        "Days to retain telemetry.metric_point rows",
        False,
        False,
    ),
    (
        "retention.insights_days",
        "retention",
        180,
        "integer",
        "Days to retain cognitive insights",
        False,
        False,
    ),
    # ── Observability / app config ────────────────────────────────────────
    (
        "obs.otlp_endpoint",
        "observability",
        "http://localhost:4317",
        "url",
        "OpenTelemetry OTLP collector endpoint",
        False,
        True,
    ),
    (
        "obs.otlp_protocol",
        "observability",
        "grpc",
        "string",
        "OTLP transport protocol: grpc or http",
        False,
        True,
    ),
    (
        "obs.otlp_insecure",
        "observability",
        True,
        "boolean",
        "Skip TLS verification for OTLP (dev only)",
        False,
        True,
    ),
    (
        "obs.sample_rate",
        "observability",
        1.0,
        "float",
        "OpenTelemetry trace sample rate (0.0-1.0)",
        False,
        False,
    ),
    (
        "obs.log_level",
        "observability",
        "INFO",
        "string",
        "Application log level: DEBUG, INFO, WARNING, ERROR",
        False,
        True,
    ),
    (
        "obs.debug_enabled",
        "observability",
        True,
        "boolean",
        "Enable /api/v1/debug/* endpoints",
        False,
        True,
    ),
    (
        "obs.cors_origins",
        "observability",
        ["http://localhost:3333", "http://localhost:3000"],
        "json_array",
        "Allowed CORS origins (list of URLs)",
        False,
        True,
    ),
]


def run_seed(database_url: str) -> int:
    """Insert default settings using ON CONFLICT DO NOTHING.

    Returns the number of rows actually inserted (0 if already seeded).
    """
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    inserted = 0
    with factory() as session:
        session: Session
        for key, group, default_val, type_hint, description, is_secret, req_restart in _SETTINGS:
            # Pass the Python value directly — psycopg3 serializes Python dicts/lists/scalars
            # to JSONB natively.  Avoid :param::jsonb — the ::jsonb cast in SQLAlchemy text()
            # with psycopg3 causes the parameter to be stripped from the compiled query.
            default_json = json.dumps(default_val)
            result = _cast(
                CursorResult[Any],
                session.execute(
                    text("""
                    INSERT INTO config.app_setting
                        (setting_key, setting_group, value_jsonb, default_jsonb,
                         type_hint, description, is_secret, requires_restart)
                    VALUES
                        (:key, :group,
                         CAST(:val AS jsonb), CAST(:default AS jsonb),
                         :type_hint, :description, :is_secret, :req_restart)
                    ON CONFLICT (setting_key) DO NOTHING
                """),
                    {
                        "key": key,
                        "group": group,
                        "val": default_json,
                        "default": default_json,
                        "type_hint": type_hint,
                        "description": description,
                        "is_secret": is_secret,
                        "req_restart": req_restart,
                    },
                ),
            )
            inserted += result.rowcount or 0
        session.commit()
    engine.dispose()
    logger.info("settings_seed: inserted %d/%d settings", inserted, len(_SETTINGS))
    return inserted


if __name__ == "__main__":
    import sys

    from internalcmdb.api.config import get_settings

    logging.basicConfig(level=logging.INFO)
    n = run_seed(str(get_settings().database_url))
    print(f"Seeded {n} settings.")
    sys.exit(0)
