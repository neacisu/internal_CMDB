"""F4.2 — Tool Executor: secured execution of cognitive tools with HITL gating.

Handles the runtime execution of tools selected by the ReAct agent loop:
    * RC-1 tools execute immediately (read-only, auto-approved)
    * RC-2 tools create a HITL review item and wait for approval
    * RC-3 tools create a HITL item with 2-person approval requirement

All executions are recorded in an audit trail for compliance.

Usage::

    from internalcmdb.cognitive.tool_executor import ToolExecutor

    executor = ToolExecutor()
    result = await executor.execute("query_host_health", {"host_code": "hz.62"})
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of a tool execution.

    Attributes:
        tool_id:           Which tool was invoked.
        success:           True if the tool completed without error.
        output:            Tool output (when successful).
        error:             Error message (when failed).
        execution_time_ms: Wall-clock execution time.
        requires_approval: True if execution was deferred pending HITL approval.
        hitl_item_id:      ID of the HITL item (when approval is required).
        audit_id:          Unique ID for this execution (for audit trail).
    """

    tool_id: str
    success: bool
    output: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))
    error: str = ""
    execution_time_ms: int = 0
    requires_approval: bool = False
    hitl_item_id: str = ""
    audit_id: str = ""


class ToolExecutor:
    """Execute cognitive tools with risk-class gating and audit trail.

    For RC-1 tools, execution is immediate. For RC-2 and RC-3, a HITL
    review item is created and the result indicates ``requires_approval=True``.
    """

    def __init__(self, *, skip_hitl: bool = False) -> None:
        self._last_invoked: dict[str, float] = {}
        self._skip_hitl = skip_hitl

    async def execute(
        self,
        tool_id: str,
        params: dict[str, Any],
        *,
        triggered_by: str = "cognitive_agent",
    ) -> ExecutionResult:
        """Execute a tool by ID with the given parameters.

        Args:
            tool_id:       The registered tool_id to invoke.
            params:        Parameters matching the tool's JSON Schema.
            triggered_by:  Who/what triggered this execution (for audit).

        Returns:
            An :class:`ExecutionResult` with the outcome.
        """
        from internalcmdb.cognitive.tool_registry import RiskClass, get_registry  # noqa: PLC0415

        audit_id = str(uuid.uuid4())
        registry = get_registry()
        tool = registry.get(tool_id)

        if tool is None:
            logger.warning("ToolExecutor: unknown tool %r", tool_id)
            return ExecutionResult(
                tool_id=tool_id,
                success=False,
                error=f"Unknown tool: {tool_id}",
                audit_id=audit_id,
            )

        # Cooldown check
        if tool.cooldown_s > 0:
            last = self._last_invoked.get(tool_id, 0.0)
            elapsed = time.monotonic() - last
            if elapsed < tool.cooldown_s:
                remaining = int(tool.cooldown_s - elapsed)
                return ExecutionResult(
                    tool_id=tool_id,
                    success=False,
                    error=f"Tool {tool_id} is on cooldown — {remaining}s remaining.",
                    audit_id=audit_id,
                )

        # Policy gate — evaluated before HITL deferral and RC-1 execution (F3.1)
        policy_block = await self._check_policy(tool, params, triggered_by)
        if policy_block:
            await self._persist_audit(
                audit_id,
                tool_id,
                tool.risk_class.value,
                params,
                None,
                False,
                policy_block,
                0,
                triggered_by,
            )
            return ExecutionResult(
                tool_id=tool_id,
                success=False,
                error=policy_block,
                audit_id=audit_id,
            )

        # RC-2 and RC-3: defer to HITL (unless skip_hitl is set — used by post-approval worker)
        if tool.risk_class in (RiskClass.RC2, RiskClass.RC3) and not self._skip_hitl:
            hitl_id = await self._create_hitl_item(tool, params, triggered_by)
            logger.info(
                "ToolExecutor: %s (RC=%s) deferred to HITL item %s.",
                tool_id,
                tool.risk_class.value,
                hitl_id,
            )
            await self._persist_audit(
                audit_id,
                tool_id,
                tool.risk_class.value,
                params,
                None,
                True,
                None,
                0,
                triggered_by,
            )
            return ExecutionResult(
                tool_id=tool_id,
                success=True,
                output={"message": f"Pending HITL approval (item {hitl_id})"},
                requires_approval=True,
                hitl_item_id=hitl_id,
                audit_id=audit_id,
            )

        # Guard scan on parameters (fail-closed via LLM Guard)
        guard_block = await self._guard_scan_params(tool_id, params)
        if guard_block:
            await self._persist_audit(
                audit_id,
                tool_id,
                tool.risk_class.value,
                params,
                None,
                False,
                guard_block,
                0,
                triggered_by,
            )
            return ExecutionResult(
                tool_id=tool_id,
                success=False,
                error=guard_block,
                audit_id=audit_id,
            )

        # RC-1: execute immediately
        import asyncio as _asyncio  # noqa: PLC0415

        start = time.monotonic()
        try:
            timeout = tool.timeout_s if tool.timeout_s > 0 else None
            coro = tool.execute(params)
            output: dict[str, Any] = (
                await _asyncio.wait_for(coro, timeout=timeout)
                if timeout
                else await coro
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self._last_invoked[tool_id] = time.monotonic()

            # Post-execution output scan (PII / injection in results)
            output_block = self._guard_scan_output(tool_id, output)
            if output_block:
                logger.warning("Post-exec guard blocked output for %s", tool_id)
                output = {"redacted": True, "reason": output_block}

            logger.info("ToolExecutor: %s completed in %dms.", tool_id, elapsed_ms)
            await self._persist_audit(
                audit_id,
                tool_id,
                tool.risk_class.value,
                params,
                output,
                True,
                None,
                elapsed_ms,
                triggered_by,
            )
            return ExecutionResult(
                tool_id=tool_id,
                success=True,
                output=output,
                execution_time_ms=elapsed_ms,
                audit_id=audit_id,
            )
        except _asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            err = f"Tool {tool_id} timed out after {tool.timeout_s}s"
            logger.warning("ToolExecutor: %s", err)
            await self._persist_audit(
                audit_id,
                tool_id,
                tool.risk_class.value,
                params,
                None,
                False,
                err,
                elapsed_ms,
                triggered_by,
            )
            return ExecutionResult(
                tool_id=tool_id,
                success=False,
                error=err,
                execution_time_ms=elapsed_ms,
                audit_id=audit_id,
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("ToolExecutor: %s failed after %dms.", tool_id, elapsed_ms)
            await self._persist_audit(
                audit_id,
                tool_id,
                tool.risk_class.value,
                params,
                None,
                False,
                str(exc),
                elapsed_ms,
                triggered_by,
            )
            return ExecutionResult(
                tool_id=tool_id,
                success=False,
                error=str(exc),
                execution_time_ms=elapsed_ms,
                audit_id=audit_id,
            )

    @staticmethod
    async def _check_policy(tool: Any, params: dict[str, Any], triggered_by: str) -> str:
        """Evaluate tool invocation against governance policies. Returns block reason or ''."""
        import asyncio  # noqa: PLC0415

        from sqlalchemy import create_engine  # noqa: PLC0415
        from sqlalchemy.orm import Session  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415
        from internalcmdb.governance.policy_enforcer import PolicyEnforcer  # noqa: PLC0415

        action = {
            "type": tool.tool_id,
            "target": str(params.get("host_code") or params.get("host") or "unknown"),
            "risk_class": tool.risk_class.value,
        }
        context = {"role": triggered_by.split(":")[0], "environment": params.get("environment", "")}

        def _evaluate() -> str:
            settings = get_settings()
            engine = create_engine(str(settings.database_url), pool_pre_ping=True)
            try:
                with Session(engine) as session:
                    result = PolicyEnforcer(session).check(action, context)
                    if not result.compliant:
                        return "; ".join(v.reason for v in result.violations)
            except Exception:
                logger.exception("Policy check failed — FAIL-CLOSED")
                return "Policy database unavailable; action blocked (fail-closed)"
            finally:
                engine.dispose()
            return ""

        return await asyncio.to_thread(_evaluate)

    @staticmethod
    async def _guard_scan_params(tool_id: str, params: dict[str, Any]) -> str:
        """Scan tool parameters via LLM Guard. Returns block reason or '' (fail-closed)."""
        from internalcmdb.llm.client import LLMClient  # noqa: PLC0415
        from internalcmdb.llm.guard_pipeline import scan_prompt  # noqa: PLC0415

        serialised = json.dumps(params, default=str)
        try:
            async with LLMClient() as llm:
                result = await scan_prompt(llm, serialised)
            if not result.is_valid:
                reason = (
                    f"Guard blocked {tool_id}: parameter scan failed "
                    f"(score={result.score:.3f}, details={result.details})"
                )
                logger.warning(reason)
                return reason
        except Exception:
            logger.exception("Guard param scan failed — FAIL-CLOSED for %s", tool_id)
            return f"Guard blocked {tool_id}: guard service unavailable (fail-closed)"

        return ""

    @staticmethod
    async def _guard_scan_output(tool_id: str, output: dict[str, Any]) -> str:
        """Scan tool output via LLM Guard. Returns block reason or '' (fail-closed)."""
        from internalcmdb.llm.client import LLMClient  # noqa: PLC0415
        from internalcmdb.llm.guard_pipeline import scan_output  # noqa: PLC0415

        serialised = json.dumps(output, default=str)
        try:
            async with LLMClient() as llm:
                result = await scan_output(llm, serialised, serialised)
            if not result.is_valid:
                reason = (
                    f"Post-exec guard blocked {tool_id}: output scan failed "
                    f"(score={result.score:.3f})"
                )
                logger.warning(reason)
                return reason
        except Exception:
            logger.exception("Guard output scan failed — FAIL-CLOSED for %s", tool_id)
            return f"Post-exec guard blocked {tool_id}: guard service unavailable (fail-closed)"

        return ""

    @staticmethod
    async def _persist_audit(  # noqa: PLR0913
        audit_id: str,
        tool_id: str,
        risk_class: str,
        params: dict[str, Any],
        result: dict[str, Any] | None,
        success: bool,
        error: str | None,
        execution_time_ms: int,
        triggered_by: str,
    ) -> None:
        """Persist tool execution to agent_control.tool_execution_log."""
        import asyncio as _asyncio  # noqa: PLC0415

        from sqlalchemy import create_engine, text  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415

        def _insert() -> None:
            try:
                settings = get_settings()
                engine = create_engine(str(settings.database_url), pool_pre_ping=True)
                try:
                    with engine.connect() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO agent_control.tool_execution_log
                                    (audit_id, tool_id, params, result, success,
                                     error, execution_time_ms, risk_class, triggered_by)
                                VALUES
                                    (:aid, :tid, :params::json, :result::json,
                                     :success, :error, :ems, :rc, :tb)
                            """),
                            {
                                "aid": audit_id,
                                "tid": tool_id,
                                "params": json.dumps(params, default=str),
                                "result": json.dumps(result, default=str) if result else None,
                                "success": success,
                                "error": error,
                                "ems": execution_time_ms,
                                "rc": risk_class,
                                "tb": triggered_by,
                            },
                        )
                        conn.commit()
                finally:
                    engine.dispose()
            except Exception:
                logger.debug("Failed to persist tool audit log", exc_info=True)

        await _asyncio.to_thread(_insert)

    async def _create_hitl_item(
        self,
        tool: Any,
        params: dict[str, Any],
        triggered_by: str,
    ) -> str:
        """Create a HITL governance item for RC-2/RC-3 tool approval via HITLWorkflow."""
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: PLC0415

        from internalcmdb.api.config import get_settings  # noqa: PLC0415
        from internalcmdb.api.deps import _normalize_pg_url  # noqa: PLC0415
        from internalcmdb.governance.hitl_workflow import HITLWorkflow  # noqa: PLC0415

        settings = get_settings()
        async_url = _normalize_pg_url(str(settings.database_url), driver="asyncpg")
        engine = create_async_engine(async_url, pool_pre_ping=True)

        context = {
            "tool_id": tool.tool_id,
            "tool_name": tool.name,
            "risk_class": tool.risk_class.value,
            "parameters": params,
            "triggered_by": triggered_by,
        }
        suggestion = {"action": tool.tool_id, "params": params}

        try:
            async with AsyncSession(engine) as session:
                wf = HITLWorkflow(session)
                return await wf.submit(
                    {
                        "item_type": f"tool_approval_{tool.tool_id}",
                        "risk_class": tool.risk_class.value,
                        "context": context,
                        "llm_suggestion": suggestion,
                        "llm_confidence": 0.85,
                        "llm_model_used": "cognitive_agent",
                    }
                )
        finally:
            await engine.dispose()
