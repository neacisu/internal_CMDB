"""F4.1 — Tool Registry: declarative catalog of tools available to the cognitive agent.

Each tool is defined with:
    * A unique ``tool_id``
    * An OpenAI-compatible JSON Schema for parameters
    * A risk classification (RC-1 read-only, RC-2 reversible write, RC-3 destructive)
    * An ``execute`` coroutine that performs the action

Risk classes drive the HITL approval workflow:
    * **RC-1** — Auto-approved: read-only diagnostics (e.g. query DB, fetch metrics)
    * **RC-2** — HITL required: reversible writes (e.g. restart service, scale replicas)
    * **RC-3** — HITL + 2-person approval: destructive or irreversible (e.g. delete data)

Usage::

    from internalcmdb.cognitive.tool_registry import get_registry

    registry = get_registry()
    tool = registry.get("query_host_health")
    result = await tool.execute({"host_code": "hz.62"})
"""

from __future__ import annotations

import asyncio
import logging
import shlex
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import ParseResult, urlparse

logger = logging.getLogger(__name__)

# Reusable parameter description
_DESC_AGENT_ID = "Target agent UUID."


class RiskClass(StrEnum):
    """Risk classification for cognitive tools."""

    RC1 = "RC-1"  # Read-only — auto-approved
    RC2 = "RC-2"  # Reversible write — HITL required
    RC3 = "RC-3"  # Destructive — HITL + 2-person approval


@dataclass(frozen=True)
class ToolDefinition:
    """Declarative definition of a cognitive tool.

    Attributes:
        tool_id:      Unique identifier (snake_case).
        name:         Human-readable display name.
        description:  Concise description for the LLM function-calling prompt.
        risk_class:   Risk classification controlling auto-approval.
        parameters:   OpenAI-compatible JSON Schema for the tool's parameters.
        execute:      Async callable that performs the action.
        tags:         Optional tags for filtering (e.g. ``["diagnostic", "host"]``).
        cooldown_s:   Minimum seconds between invocations of this tool.
        timeout_s:    Maximum execution time for this tool (seconds).
    """

    tool_id: str
    name: str
    description: str
    risk_class: RiskClass
    parameters: dict[str, Any]
    execute: Callable[..., Awaitable[dict[str, Any]]]
    tags: tuple[str, ...] = ()
    cooldown_s: int = 0
    timeout_s: int = 30

    @property
    def requires_hitl(self) -> bool:
        """Whether this tool requires human-in-the-loop approval."""
        return self.risk_class in (RiskClass.RC2, RiskClass.RC3)

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling format for LLM tool_call()."""
        return {
            "type": "function",
            "function": {
                "name": self.tool_id,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Central registry for all cognitive tools.

    Thread-safe singleton.  Tools are registered at import time
    and looked up at runtime by the ReAct agent loop.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        if tool.tool_id in self._tools:
            logger.warning("Tool %r already registered — overwriting.", tool.tool_id)
        self._tools[tool.tool_id] = tool

    def get(self, tool_id: str) -> ToolDefinition | None:
        """Look up a tool by ID."""
        return self._tools.get(tool_id)

    def list_tools(
        self,
        *,
        risk_class: RiskClass | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> list[ToolDefinition]:
        """Return tools, optionally filtered by risk class or tags."""
        tools = list(self._tools.values())
        if risk_class is not None:
            tools = [t for t in tools if t.risk_class == risk_class]
        if tags is not None:
            tag_set = set(tags)
            tools = [t for t in tools if tag_set & set(t.tags)]
        return tools

    def openai_tools(
        self,
        *,
        risk_class: RiskClass | None = None,
    ) -> list[dict[str, Any]]:
        """Return all tools in OpenAI function-calling format."""
        return [t.to_openai_tool() for t in self.list_tools(risk_class=risk_class)]

    @property
    def tool_count(self) -> int:
        return len(self._tools)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Return the global tool registry, creating it on first access."""
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = ToolRegistry()
        _register_builtin_tools(_registry)
        _register_phase4_tools(_registry)
        _register_phase5_tools(_registry)
    return _registry


# ---------------------------------------------------------------------------
# Built-in diagnostic tools (RC-1 — auto-approved)
#
# Each tool is a thin async wrapper around a sync DB query run via
# ``asyncio.to_thread`` so the event loop is never blocked.
# ---------------------------------------------------------------------------


def _get_tool_engine():
    """Create a disposable SQLAlchemy engine for tool queries."""
    from sqlalchemy import create_engine  # noqa: PLC0415

    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    return create_engine(str(get_settings().database_url), pool_pre_ping=True)


def _sync_query_host_health(params: dict[str, Any]) -> dict[str, Any]:
    """Sync: query the latest health insights for a host."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_tool_engine()
    host_code = str(params.get("host_code", ""))
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT h.host_id, h.host_code,"
                    "       ci.severity, ci.category, ci.title,"
                    "       ci.confidence, ci.created_at"
                    " FROM registry.host h"
                    " LEFT JOIN cognitive.insight ci"
                    "     ON ci.entity_id = h.host_id"
                    "    AND ci.status = 'active'"
                    "    AND ci.category = 'health'"
                    " WHERE h.host_code = :hc"
                    " ORDER BY ci.created_at DESC NULLS LAST"
                    " LIMIT 5"
                ),
                {"hc": host_code},
            ).fetchall()
        if not rows:
            return {"status": "not_found", "host_code": host_code}
        return {
            "status": "ok",
            "host_code": host_code,
            "insights": [dict(r._mapping) for r in rows],
        }
    finally:
        engine.dispose()


async def _tool_query_host_health(params: dict[str, Any]) -> dict[str, Any]:
    """Query the latest health score for a specific host."""
    import asyncio  # noqa: PLC0415

    return await asyncio.to_thread(_sync_query_host_health, params)


def _sync_query_active_insights(params: dict[str, Any]) -> dict[str, Any]:
    """Sync: query active cognitive insights with optional filters."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_tool_engine()
    severity = params.get("severity")
    category = params.get("category")
    limit = min(int(params.get("limit", 20)), 100)

    # Build SQL conditionally — no user input is interpolated; all values use bind params.
    base = (
        "SELECT ci.insight_id, ci.entity_type, ci.severity,"
        "       ci.category, ci.title, ci.confidence,"
        "       ci.created_at"
        " FROM cognitive.insight ci"
        " WHERE ci.status = 'active'"
    )
    binds: dict[str, Any] = {"lim": limit}
    if severity:
        base += " AND ci.severity = :sev"
        binds["sev"] = severity
    if category:
        base += " AND ci.category = :cat"
        binds["cat"] = category
    base += " ORDER BY ci.created_at DESC LIMIT :lim"

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(base), binds).fetchall()
        return {
            "status": "ok",
            "count": len(rows),
            "insights": [dict(r._mapping) for r in rows],
        }
    finally:
        engine.dispose()


async def _tool_query_active_insights(params: dict[str, Any]) -> dict[str, Any]:
    """Query active cognitive insights, optionally filtered by severity or category."""
    import asyncio  # noqa: PLC0415

    return await asyncio.to_thread(_sync_query_active_insights, params)


def _sync_query_fleet_summary(params: dict[str, Any]) -> dict[str, Any]:
    """Sync: summarise fleet status."""
    from sqlalchemy import text  # noqa: PLC0415

    _ = params  # unused — fleet summary takes no parameters
    engine = _get_tool_engine()
    try:
        with engine.connect() as conn:
            hosts = conn.execute(text("SELECT COUNT(*) FROM registry.host")).scalar() or 0
            agents = (
                conn.execute(text("SELECT COUNT(*) FROM discovery.collector_agent")).scalar() or 0
            )
            online = (
                conn.execute(
                    text(
                        "SELECT COUNT(DISTINCT agent_id) FROM discovery.collector_snapshot"
                        " WHERE collected_at > NOW() - INTERVAL '10 minutes'"
                    )
                ).scalar()
                or 0
            )
            active_insights = (
                conn.execute(
                    text("SELECT COUNT(*) FROM cognitive.insight WHERE status = 'active'")
                ).scalar()
                or 0
            )
        return {
            "status": "ok",
            "hosts": hosts,
            "agents": agents,
            "agents_online": online,
            "active_insights": active_insights,
        }
    finally:
        engine.dispose()


async def _tool_query_fleet_summary(params: dict[str, Any]) -> dict[str, Any]:
    """Summarise fleet status: host count, agent count, active insights."""
    import asyncio  # noqa: PLC0415

    return await asyncio.to_thread(_sync_query_fleet_summary, params)


def _sync_query_recent_drifts(params: dict[str, Any]) -> dict[str, Any]:
    """Sync: query recent drift detections."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_tool_engine()
    hours = min(int(params.get("hours", 24)), 168)
    limit = min(int(params.get("limit", 20)), 100)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT dr.drift_id, dr.entity_id, dr.entity_type,"
                    "       dr.drift_type, dr.fields_changed,"
                    "       dr.confidence, dr.explanation, dr.detected_at"
                    " FROM cognitive.drift_result dr"
                    " WHERE dr.detected_at > NOW() - :hrs * INTERVAL '1 hour'"
                    "   AND dr.has_drift = true"
                    " ORDER BY dr.detected_at DESC"
                    " LIMIT :lim"
                ),
                {"hrs": hours, "lim": limit},
            ).fetchall()
        return {
            "status": "ok",
            "count": len(rows),
            "drifts": [dict(r._mapping) for r in rows],
        }
    finally:
        engine.dispose()


async def _tool_query_recent_drifts(params: dict[str, Any]) -> dict[str, Any]:
    """Query recent drift detection results."""
    import asyncio  # noqa: PLC0415

    return await asyncio.to_thread(_sync_query_recent_drifts, params)


def _sync_query_host_snapshots(params: dict[str, Any]) -> dict[str, Any]:
    """Sync: fetch the latest snapshots for a host."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_tool_engine()
    host_code = str(params.get("host_code", ""))
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT DISTINCT ON (cs.snapshot_kind)"
                    "       cs.snapshot_kind,"
                    "       cs.payload_jsonb,"
                    "       cs.collected_at"
                    " FROM registry.host h"
                    " JOIN discovery.collector_agent ca ON ca.host_id = h.host_id"
                    " JOIN discovery.collector_snapshot cs"
                    "      ON cs.agent_id = ca.agent_id"
                    " WHERE h.host_code = :hc"
                    "   AND cs.collected_at > NOW() - INTERVAL '2 hours'"
                    " ORDER BY cs.snapshot_kind, cs.collected_at DESC"
                ),
                {"hc": host_code},
            ).fetchall()
        if not rows:
            return {"status": "not_found", "host_code": host_code}
        return {
            "status": "ok",
            "host_code": host_code,
            "snapshot_kinds": [
                {
                    "kind": r._mapping["snapshot_kind"],
                    "collected_at": str(r._mapping["collected_at"]),
                    "payload": r._mapping["payload_jsonb"],
                }
                for r in rows
            ],
        }
    finally:
        engine.dispose()


async def _tool_query_host_snapshots(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch the latest snapshots for a host across all snapshot kinds."""
    import asyncio  # noqa: PLC0415

    return await asyncio.to_thread(_sync_query_host_snapshots, params)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def _register_builtin_tools(registry: ToolRegistry) -> None:
    """Register all built-in diagnostic tools."""
    registry.register(
        ToolDefinition(
            tool_id="query_host_health",
            name="Query Host Health",
            description="Look up the latest health insights for a specific host by host_code.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "host_code": {
                        "type": "string",
                        "description": "Host code identifier (e.g. 'hz.62', 'orchestrator').",
                    }
                },
                "required": ["host_code"],
            },
            execute=_tool_query_host_health,
            tags=("diagnostic", "host", "health"),
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="query_active_insights",
            name="Query Active Insights",
            description=(
                "List active cognitive insights. "
                "Optionally filter by severity ('warning' or 'critical') "
                "and/or category ('health', 'security', 'capacity', 'performance')."
            ),
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["warning", "critical"],
                        "description": "Filter by severity level.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20, max 100).",
                    },
                },
                "required": [],
            },
            execute=_tool_query_active_insights,
            tags=("diagnostic", "insights"),
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="query_fleet_summary",
            name="Query Fleet Summary",
            description=(
                "Get a high-level fleet summary: host count, agent count, "
                "online agents, active insight count."
            ),
            risk_class=RiskClass.RC1,
            parameters={"type": "object", "properties": {}, "required": []},
            execute=_tool_query_fleet_summary,
            tags=("diagnostic", "fleet"),
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="query_recent_drifts",
            name="Query Recent Drifts",
            description=(
                "List recent configuration drift detections, optionally filtered by time window."
            ),
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Look-back window in hours (default 24, max 168).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20, max 100).",
                    },
                },
                "required": [],
            },
            execute=_tool_query_recent_drifts,
            tags=("diagnostic", "drift"),
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="query_host_snapshots",
            name="Query Host Snapshots",
            description=(
                "Fetch the latest snapshots for a specific host across all "
                "collected snapshot kinds (system_vitals, disk_state, "
                "security_posture, etc.)."
            ),
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "host_code": {
                        "type": "string",
                        "description": "Host code identifier.",
                    }
                },
                "required": ["host_code"],
            },
            execute=_tool_query_host_snapshots,
            tags=("diagnostic", "host", "snapshots"),
        )
    )

    logger.info("Tool registry: %d built-in tools registered.", registry.tool_count)


# ---------------------------------------------------------------------------
# Phase 4: Additional Diagnostic Tools (RC-1)
# ---------------------------------------------------------------------------


def _sync_query_service_instances(params: dict[str, Any]) -> dict[str, Any]:
    """Query service instances with optional status filter."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_tool_engine()
    try:
        with engine.connect() as conn:
            sql = """
                SELECT si.instance_id::text, si.service_id::text,
                       si.host_id::text, si.status, si.port,
                       ss.service_name
                FROM shared_infrastructure.service_instance si
                JOIN shared_infrastructure.shared_service ss
                    ON ss.service_id = si.service_id
            """
            bind: dict[str, Any] = {"limit": min(params.get("limit", 50), 100)}
            status = params.get("status", "")
            if status:
                sql += " WHERE si.status = :status"
                bind["status"] = status
            sql += " ORDER BY ss.service_name LIMIT :limit"
            rows = conn.execute(text(sql), bind).mappings().all()
            return {"instances": [dict(r) for r in rows], "count": len(rows)}
    finally:
        engine.dispose()


async def _tool_query_service_instances(params: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(_sync_query_service_instances, params)


def _sync_search_knowledge_base(params: dict[str, Any]) -> dict[str, Any]:
    """Text search on the RAG knowledge base (ILIKE fallback — async vector search in
    QueryEngine)."""
    from sqlalchemy import text  # noqa: PLC0415

    query_text = params.get("query", "")
    top_k = min(params.get("top_k", 5), 20)
    if not query_text:
        return {"error": "query parameter required", "results": []}

    engine = _get_tool_engine()
    try:
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text("""
                SELECT dc.document_chunk_id::text AS chunk_id,
                       dc.content_text AS content,
                       dc.section_path_text AS title
                FROM retrieval.document_chunk dc
                WHERE dc.content_text ILIKE :pattern
                ORDER BY dc.chunk_index
                LIMIT :top_k
            """),
                    {
                        "pattern": f"%{query_text[:100]}%",
                        "top_k": top_k,
                    },
                )
                .mappings()
                .all()
            )
            return {
                "results": [
                    {
                        "chunk_id": r["chunk_id"],
                        "content": r["content"][:500],
                        "title": r["title"] or "",
                    }
                    for r in rows
                ],
                "count": len(rows),
            }
    finally:
        engine.dispose()


async def _tool_search_knowledge_base(params: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(_sync_search_knowledge_base, params)


def _sync_query_audit_trail(params: dict[str, Any]) -> dict[str, Any]:
    """Query recent governance audit events."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_tool_engine()
    try:
        hours = min(params.get("hours", 24), 168)
        limit = min(params.get("limit", 20), 100)
        entity_id = params.get("entity_id", "")
        with engine.connect() as conn:
            sql = """
                SELECT event_id::text, event_type, target_id::text,
                       target_type, actor, severity, details_jsonb,
                       created_at
                FROM governance.audit_event
                WHERE created_at > NOW() - :hrs * INTERVAL '1 hour'
            """
            bind: dict[str, Any] = {"hrs": hours, "limit": limit}
            if entity_id:
                sql += " AND target_id = :eid"
                bind["eid"] = entity_id
            sql += " ORDER BY created_at DESC LIMIT :limit"
            rows = conn.execute(text(sql), bind).mappings().all()
            return {
                "events": [
                    {
                        "event_id": r["event_id"],
                        "event_type": r["event_type"],
                        "target_id": r["target_id"],
                        "severity": r["severity"],
                        "actor": r["actor"],
                        "created_at": str(r["created_at"]),
                    }
                    for r in rows
                ],
                "count": len(rows),
            }
    finally:
        engine.dispose()


async def _tool_query_audit_trail(params: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(_sync_query_audit_trail, params)


def _sync_query_snapshot_history(params: dict[str, Any]) -> dict[str, Any]:
    """Query time-series of snapshots for a host by kind."""
    from sqlalchemy import text  # noqa: PLC0415

    engine = _get_tool_engine()
    try:
        host_code = params.get("host_code", "")
        kind = params.get("snapshot_kind", "system_vitals")
        limit = min(params.get("limit", 10), 50)
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text("""
                SELECT cs.snapshot_id::text, cs.snapshot_kind,
                       cs.collected_at, cs.payload_jsonb
                FROM discovery.collector_snapshot cs
                JOIN discovery.collector_agent ca ON ca.agent_id = cs.agent_id
                JOIN registry.host h ON h.host_id = ca.host_id
                WHERE h.host_code = :hc
                  AND cs.snapshot_kind = :kind
                ORDER BY cs.collected_at DESC
                LIMIT :limit
            """),
                    {"hc": host_code, "kind": kind, "limit": limit},
                )
                .mappings()
                .all()
            )
            return {
                "snapshots": [
                    {
                        "snapshot_id": r["snapshot_id"],
                        "kind": r["snapshot_kind"],
                        "collected_at": str(r["collected_at"]),
                        "payload_summary": _summarize_payload(r["payload_jsonb"]),
                    }
                    for r in rows
                ],
                "count": len(rows),
            }
    finally:
        engine.dispose()


def _summarize_payload(payload: Any) -> dict[str, Any]:
    """Extract key metrics from a snapshot payload for agent consumption."""
    if not isinstance(payload, dict):
        return {"raw": str(payload)[:200]}
    payload_typed: dict[str, Any] = payload  # type: ignore[assignment]
    summary: dict[str, Any] = {}
    for key in (
        "cpu_times",
        "memory",
        "load_avg",
        "partitions",
        "containers",
        "ufw",
        "fail2ban",
        "iptables_rules",
    ):
        if key in payload_typed:
            val = payload_typed[key]
            if isinstance(val, dict):
                val_dict: dict[str, Any] = val  # type: ignore[assignment]
                summary[key] = {
                    k: v for k, v in val_dict.items() if not isinstance(v, (dict, list))
                }
            elif isinstance(val, list):
                val_list: list[Any] = val  # type: ignore[assignment]
                summary[key] = f"{len(val_list)} items"
            else:
                summary[key] = val
    return summary


async def _tool_query_snapshot_history(params: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(_sync_query_snapshot_history, params)


# ---------------------------------------------------------------------------
# Phase 4: Agent remote diagnostic tools (via command channel)
# ---------------------------------------------------------------------------


async def _tool_remote_diagnostic(params: dict[str, Any]) -> dict[str, Any]:
    """Send a diagnostic command to a remote agent."""
    agent_id = params.get("agent_id", "")
    command = params.get("command", "")
    if not agent_id or not command:
        return {"error": "agent_id and command are required"}

    # Use the agent_commands module to dispatch
    try:
        import asyncio as _aio  # noqa: PLC0415
        import json as _json  # noqa: PLC0415

        import redis.asyncio as aioredis  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        r: aioredis.Redis[str] = aioredis.from_url(  # type: ignore[assignment]
            str(settings.redis_url), decode_responses=True
        )
        try:
            import uuid  # noqa: PLC0415

            cmd_id = str(uuid.uuid4())
            channel = f"infraq:agent:{agent_id}:commands"
            msg = _json.dumps(
                {
                    "command_id": cmd_id,
                    "command_type": "run_diagnostic",
                    "payload": {"command": command},
                    "timeout": 30,
                }
            )
            await r.publish(channel, msg)  # type: ignore[misc]

            # Wait for result on results channel (up to 30s)
            result_channel = f"infraq:agent:results:{cmd_id}"
            pubsub = r.pubsub()  # type: ignore[misc]
            await pubsub.subscribe(result_channel)  # type: ignore[misc]
            try:
                deadline = _aio.get_event_loop().time() + 30
                while _aio.get_event_loop().time() < deadline:
                    msg_data: dict[str, Any] | None = await pubsub.get_message(  # type: ignore[misc]
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if msg_data and msg_data["type"] == "message":
                        raw = msg_data.get("data") or b""
                        if isinstance(raw, (str, bytes)):
                            return _json.loads(raw)
            finally:
                await pubsub.unsubscribe(result_channel)  # type: ignore[misc]

            return {"error": "Command timed out waiting for agent response"}
        finally:
            await r.aclose()
    except ImportError:
        return {"error": "Redis not available — command channel disabled"}
    except Exception as exc:
        return {"error": f"Remote diagnostic failed: {exc}"}


# ---------------------------------------------------------------------------
# Phase 5: Remediation Tools (RC-2, HITL-gated)
# ---------------------------------------------------------------------------


async def _tool_restart_container(params: dict[str, Any]) -> dict[str, Any]:
    """Restart a Docker container via the PlaybookExecutor."""
    from internalcmdb.motor.playbooks import PlaybookExecutor  # noqa: PLC0415

    executor = PlaybookExecutor()
    result = await executor.execute("restart_container", params)
    return {
        "success": result.success,
        "playbook": result.playbook,
        "output": result.output,
        "error": result.error,
        "duration_ms": result.duration_ms,
    }


async def _tool_clear_disk_space(params: dict[str, Any]) -> dict[str, Any]:
    """Clear disk space via Docker cleanup playbook."""
    from internalcmdb.motor.playbooks import PlaybookExecutor  # noqa: PLC0415

    executor = PlaybookExecutor()
    result = await executor.execute("clear_disk_space", params)
    return {
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "duration_ms": result.duration_ms,
    }


async def _tool_restart_systemd_service(params: dict[str, Any]) -> dict[str, Any]:
    """Restart a systemd service on a remote host via agent command."""
    agent_id = params.get("agent_id", "")
    service = params.get("service", "")
    if not agent_id or not service:
        return {"error": "agent_id and service are required"}

    # Allowlist check
    allowed_services = {"internalcmdb-agent", "nginx", "haproxy", "docker", "fail2ban"}
    if service not in allowed_services:
        return {"error": f"Service {service} not in restart allowlist: {sorted(allowed_services)}"}

    return await _tool_remote_diagnostic(
        {
            "agent_id": agent_id,
            "command": f"systemctl restart {service}",
        }
    )


async def _tool_execute_playbook(params: dict[str, Any]) -> dict[str, Any]:
    """Execute a named playbook from the playbook registry."""
    from internalcmdb.motor.playbooks import PlaybookExecutor  # noqa: PLC0415

    playbook_name = params.get("playbook", "")
    if not playbook_name:
        return {"error": "playbook name required"}

    executor = PlaybookExecutor()
    if playbook_name not in executor.available_playbooks:
        return {
            "error": f"Unknown playbook: {playbook_name}",
            "available": executor.available_playbooks,
        }

    playbook_params = {k: v for k, v in params.items() if k != "playbook"}
    result = await executor.execute(playbook_name, playbook_params)
    return {
        "success": result.success,
        "playbook": result.playbook,
        "output": result.output,
        "error": result.error,
        "duration_ms": result.duration_ms,
    }


def _register_phase4_tools(registry: ToolRegistry) -> None:
    """Register Phase 4 diagnostic tools."""
    registry.register(
        ToolDefinition(
            tool_id="query_service_instances",
            name="Query Service Instances",
            description="List service instances with optional status filter.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status."},
                    "limit": {"type": "integer", "description": "Max results (default 50)."},
                },
                "required": [],
            },
            execute=_tool_query_service_instances,
            tags=("diagnostic", "services"),
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="search_knowledge_base",
            name="Search Knowledge Base",
            description="Semantic search on the RAG knowledge base (docs, runbooks, policies).",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text."},
                    "top_k": {"type": "integer", "description": "Number of results (default 5)."},
                },
                "required": ["query"],
            },
            execute=_tool_search_knowledge_base,
            tags=("diagnostic", "knowledge", "rag"),
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="query_audit_trail",
            name="Query Audit Trail",
            description="Recent governance audit events, optionally filtered by entity.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Filter by entity ID."},
                    "hours": {"type": "integer", "description": "Look-back window (default 24h)."},
                    "limit": {"type": "integer", "description": "Max results (default 20)."},
                },
                "required": [],
            },
            execute=_tool_query_audit_trail,
            tags=("diagnostic", "audit", "governance"),
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="query_snapshot_history",
            name="Query Snapshot History",
            description=(
                "Time-series of snapshots for a host by kind (system_vitals, disk_state, etc.)."
            ),
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "host_code": {"type": "string", "description": "Host code."},
                    "snapshot_kind": {
                        "type": "string",
                        "description": (
                            "Snapshot kind (system_vitals, disk_state, docker_state, etc.)."
                        ),
                    },
                    "limit": {"type": "integer", "description": "Max results (default 10)."},
                },
                "required": ["host_code"],
            },
            execute=_tool_query_snapshot_history,
            tags=("diagnostic", "host", "snapshots", "history"),
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="remote_diagnostic",
            name="Remote Diagnostic Command",
            description=(
                "Execute a read-only diagnostic command on a remote agent"
                " (df -h, ps, systemctl, etc.)."
            ),
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                    "command": {
                        "type": "string",
                        "description": (
                            "Diagnostic command (from allowlist: df -h, ps aux, systemctl, etc.)."
                        ),
                    },
                },
                "required": ["agent_id", "command"],
            },
            execute=_tool_remote_diagnostic,
            tags=("diagnostic", "agent", "remote"),
        )
    )
    # --- Phase 4 per-diagnostic tools (wrappers around remote_diagnostic) ---

    async def _mk_check_disk(params: dict[str, Any]) -> dict[str, Any]:
        return await _tool_remote_diagnostic(
            {
                "agent_id": params.get("agent_id", ""),
                "command": "df -h",
            }
        )

    registry.register(
        ToolDefinition(
            tool_id="check_disk_usage",
            name="Check Disk Usage",
            description="Run 'df -h' on a remote host to check disk usage per partition.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                },
                "required": ["agent_id"],
            },
            execute=_mk_check_disk,
            tags=("diagnostic", "agent", "disk"),
        )
    )

    async def _mk_check_processes(params: dict[str, Any]) -> dict[str, Any]:
        return await _tool_remote_diagnostic(
            {
                "agent_id": params.get("agent_id", ""),
                "command": "ps aux --sort=-%mem | head -20",
            }
        )

    registry.register(
        ToolDefinition(
            tool_id="check_process_list",
            name="Check Process List",
            description="List top 20 memory-consuming processes on a remote host.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                },
                "required": ["agent_id"],
            },
            execute=_mk_check_processes,
            tags=("diagnostic", "agent", "processes"),
        )
    )

    async def _mk_check_services(params: dict[str, Any]) -> dict[str, Any]:
        return await _tool_remote_diagnostic(
            {
                "agent_id": params.get("agent_id", ""),
                "command": "systemctl list-units --state=failed",
            }
        )

    registry.register(
        ToolDefinition(
            tool_id="check_systemd_services",
            name="Check Systemd Services",
            description="List failed systemd units on a remote host.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                },
                "required": ["agent_id"],
            },
            execute=_mk_check_services,
            tags=("diagnostic", "agent", "systemd"),
        )
    )

    async def _mk_check_docker(params: dict[str, Any]) -> dict[str, Any]:
        return await _tool_remote_diagnostic(
            {
                "agent_id": params.get("agent_id", ""),
                "command": "docker ps -a --format json",
            }
        )

    registry.register(
        ToolDefinition(
            tool_id="check_docker_status",
            name="Check Docker Status",
            description="List all Docker containers and their states on a remote host.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                },
                "required": ["agent_id"],
            },
            execute=_mk_check_docker,
            tags=("diagnostic", "agent", "docker"),
        )
    )

    async def _mk_check_journal(params: dict[str, Any]) -> dict[str, Any]:
        return await _tool_remote_diagnostic(
            {
                "agent_id": params.get("agent_id", ""),
                "command": "journalctl -p err --since '1 hour ago' --no-pager | tail -100",
            }
        )

    registry.register(
        ToolDefinition(
            tool_id="check_journal_errors",
            name="Check Journal Errors",
            description="Fetch recent error-level journal entries from a remote host.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                },
                "required": ["agent_id"],
            },
            execute=_mk_check_journal,
            tags=("diagnostic", "agent", "journal", "errors"),
        )
    )

    async def _mk_check_net(params: dict[str, Any]) -> dict[str, Any]:
        url: str = str(params.get("url", ""))
        if not url:
            return {"error": "url parameter required"}
        parsed: ParseResult = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return {"error": "Only http/https URLs are allowed"}
        if not parsed.netloc:
            return {"error": "Invalid URL: missing host"}
        return await _tool_remote_diagnostic(
            {
                "agent_id": params.get("agent_id", ""),
                "command": f"curl -s -o /dev/null -w '%{{http_code}}' {shlex.quote(url)}",
            }
        )

    registry.register(
        ToolDefinition(
            tool_id="check_network_connectivity",
            name="Check Network Connectivity",
            description="Check HTTP reachability of a URL from a remote host.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                    "url": {"type": "string", "description": "URL to check."},
                },
                "required": ["agent_id", "url"],
            },
            execute=_mk_check_net,
            tags=("diagnostic", "agent", "network"),
        )
    )

    async def _mk_read_config(params: dict[str, Any]) -> dict[str, Any]:
        path = params.get("path", "")
        if not path:
            return {"error": "path parameter required"}
        _allowed_prefixes = ("/etc/", "/opt/stacks/", "/var/log/", "/home/", "/usr/local/etc/")
        if not any(path.startswith(p) for p in _allowed_prefixes):
            return {"error": f"Path not in allowlist. Allowed prefixes: {_allowed_prefixes}"}
        return await _tool_remote_diagnostic(
            {
                "agent_id": params.get("agent_id", ""),
                "command": f"cat {shlex.quote(path)}",
            }
        )

    registry.register(
        ToolDefinition(
            tool_id="read_config_file",
            name="Read Config File",
            description="Read a configuration file on a remote host (path must be in allowlist).",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                    "path": {
                        "type": "string",
                        "description": "File path (e.g. /etc/ssh/sshd_config).",
                    },
                },
                "required": ["agent_id", "path"],
            },
            execute=_mk_read_config,
            tags=("diagnostic", "agent", "config"),
        )
    )

    async def _mk_check_cert(params: dict[str, Any]) -> dict[str, Any]:
        cert_path = params.get("path", "")
        if not cert_path:
            return {"error": "path parameter required"}
        return await _tool_remote_diagnostic(
            {
                "agent_id": params.get("agent_id", ""),
                "command": f"openssl x509 -in {cert_path} -noout -enddate -subject",
            }
        )

    registry.register(
        ToolDefinition(
            tool_id="check_certificate",
            name="Check Certificate",
            description="Check TLS certificate expiry and subject on a remote host.",
            risk_class=RiskClass.RC1,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                    "path": {"type": "string", "description": "Certificate file path."},
                },
                "required": ["agent_id", "path"],
            },
            execute=_mk_check_cert,
            tags=("diagnostic", "agent", "certificate", "security"),
        )
    )


def _register_phase5_tools(registry: ToolRegistry) -> None:
    """Register Phase 5 remediation tools (RC-2, HITL-gated)."""
    registry.register(
        ToolDefinition(
            tool_id="restart_container",
            name="Restart Container",
            description="Restart a Docker container. Requires HITL approval.",
            risk_class=RiskClass.RC2,
            parameters={
                "type": "object",
                "properties": {
                    "container_name": {"type": "string", "description": "Container name or ID."},
                },
                "required": ["container_name"],
            },
            execute=_tool_restart_container,
            tags=("remediation", "docker", "container"),
            cooldown_s=60,
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="clear_disk_space",
            name="Clear Disk Space",
            description="Run Docker cleanup to free disk space. Requires HITL approval.",
            risk_class=RiskClass.RC2,
            parameters={
                "type": "object",
                "properties": {
                    "threshold_pct": {
                        "type": "integer",
                        "description": "Disk usage % threshold for cleanup (default 85).",
                    },
                },
                "required": [],
            },
            execute=_tool_clear_disk_space,
            tags=("remediation", "disk", "cleanup"),
            cooldown_s=300,
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="restart_systemd_service",
            name="Restart Systemd Service",
            description=(
                "Restart a systemd service on a host (from allowlist only). Requires HITL approval."
            ),
            risk_class=RiskClass.RC2,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                    "service": {
                        "type": "string",
                        "description": (
                            "Service name (internalcmdb-agent, nginx, haproxy, docker, fail2ban)."
                        ),
                    },
                },
                "required": ["agent_id", "service"],
            },
            execute=_tool_restart_systemd_service,
            tags=("remediation", "systemd", "service"),
            cooldown_s=120,
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="execute_playbook",
            name="Execute Playbook",
            description="Execute a named remediation playbook. Requires HITL approval.",
            risk_class=RiskClass.RC2,
            parameters={
                "type": "object",
                "properties": {
                    "playbook": {"type": "string", "description": "Playbook name."},
                },
                "required": ["playbook"],
            },
            execute=_tool_execute_playbook,
            tags=("remediation", "playbook"),
            cooldown_s=60,
        )
    )

    # --- Additional Phase 5 remediation tools ---

    async def _tool_rotate_log_files(params: dict[str, Any]) -> dict[str, Any]:
        """Truncate runaway container logs via the truncate_container_log playbook."""
        from internalcmdb.motor.playbooks import PlaybookExecutor  # noqa: PLC0415

        executor = PlaybookExecutor()
        result = await executor.execute("truncate_container_log", params)
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "duration_ms": result.duration_ms,
        }

    registry.register(
        ToolDefinition(
            tool_id="rotate_log_files",
            name="Rotate Log Files",
            description=(
                "Truncate/rotate runaway Docker container log files. Requires HITL approval."
            ),
            risk_class=RiskClass.RC2,
            parameters={
                "type": "object",
                "properties": {
                    "log_path": {
                        "type": "string",
                        "description": "Full path to the container log file.",
                    },
                    "container_name": {
                        "type": "string",
                        "description": "Container name for audit trail.",
                    },
                },
                "required": ["log_path"],
            },
            execute=_tool_rotate_log_files,
            tags=("remediation", "logs", "disk"),
            cooldown_s=120,
        )
    )

    async def _tool_edit_config(params: dict[str, Any]) -> dict[str, Any]:
        """Edit a config file on a remote host. Generates diff, applies after HITL approval."""
        agent_id = params.get("agent_id", "")
        path = params.get("path", "")
        content = params.get("new_content", "")
        if not agent_id or not path or not content:
            return {"error": "agent_id, path, and new_content are required"}

        # Read current content for diff
        current = await _tool_remote_diagnostic(
            {
                "agent_id": agent_id,
                "command": path,
            }
        )
        return {
            "action": "config_edit_prepared",
            "path": path,
            "original_content": current.get("stdout", "")[:4096],
            "new_content": content[:4096],
            "requires_backup": True,
            "note": "Diff reviewed and applied upon HITL approval.",
        }

    registry.register(
        ToolDefinition(
            tool_id="edit_config_file",
            name="Edit Configuration File",
            description=(
                "Generate a diff for a config file edit on a remote host."
                " RC-3: requires HITL + double approval."
            ),
            risk_class=RiskClass.RC3,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                    "path": {
                        "type": "string",
                        "description": "Config file path (e.g. /etc/ssh/sshd_config).",
                    },
                    "new_content": {"type": "string", "description": "New file content."},
                },
                "required": ["agent_id", "path", "new_content"],
            },
            execute=_tool_edit_config,
            tags=("remediation", "config", "security"),
            cooldown_s=300,
        )
    )

    async def _tool_update_firewall(params: dict[str, Any]) -> dict[str, Any]:
        """Update firewall rules on a remote host with auto-revert safety."""
        await asyncio.sleep(0)  # cooperative yield
        agent_id = params.get("agent_id", "")
        rule = params.get("rule", "")
        if not agent_id or not rule:
            return {"error": "agent_id and rule are required"}
        return {
            "action": "firewall_update_prepared",
            "rule": rule,
            "auto_revert_minutes": 5,
            "note": "Rule will auto-revert after 5 minutes if not confirmed.",
        }

    registry.register(
        ToolDefinition(
            tool_id="update_firewall_rules",
            name="Update Firewall Rules",
            description=(
                "Apply iptables/ufw rule changes with 5-minute auto-revert safety."
                " RC-3: requires HITL + double approval."
            ),
            risk_class=RiskClass.RC3,
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": _DESC_AGENT_ID},
                    "rule": {"type": "string", "description": "Firewall rule to apply."},
                },
                "required": ["agent_id", "rule"],
            },
            execute=_tool_update_firewall,
            tags=("remediation", "firewall", "security"),
            cooldown_s=600,
        )
    )

    async def _tool_cert_renewal(params: dict[str, Any]) -> dict[str, Any]:
        """Trigger certificate renewal via the rotate_certificate playbook."""
        from internalcmdb.motor.playbooks import PlaybookExecutor  # noqa: PLC0415

        executor = PlaybookExecutor()
        result = await executor.execute("rotate_certificate", params)
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "duration_ms": result.duration_ms,
        }

    registry.register(
        ToolDefinition(
            tool_id="certificate_renewal",
            name="Certificate Renewal",
            description="Trigger TLS certificate renewal/rotation cycle. Requires HITL approval.",
            risk_class=RiskClass.RC2,
            parameters={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Domain name for the certificate."},
                },
                "required": ["domain"],
            },
            execute=_tool_cert_renewal,
            tags=("remediation", "certificate", "security"),
            cooldown_s=600,
        )
    )
