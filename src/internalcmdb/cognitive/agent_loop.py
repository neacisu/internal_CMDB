"""ReAct Agent Loop — Observe → Think → Act → Observe reasoning engine.

Implements an agentic ReAct (Reasoning + Acting) loop that:
    1. Receives a goal and context
    2. Uses the LLM (QwQ-32B reasoning model) to think step-by-step
    3. Selects and executes tools via the ToolExecutor
    4. Observes the results and decides next action
    5. Terminates with a FINAL_ANSWER or after max iterations

Usage::

    from internalcmdb.cognitive.agent_loop import AgentLoop

    loop = AgentLoop()
    result = await loop.run("investigate disk usage on hz.223")
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from redis.asyncio import Redis as _AioRedis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_ITERATIONS = 10
_SESSION_TIMEOUT_S = 300  # 5 minutes
_MAX_TOKENS_PER_SESSION = 50_000
_FINAL_ANSWER_MARKER = "FINAL_ANSWER"
_LLM_CONSECUTIVE_FAILURES = 3  # circuit breaker threshold


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class AgentStep:
    """A single step in the ReAct loop."""

    iteration: int
    phase: str  # "think", "act", "observe"
    content: str
    tool_call: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None
    tokens_used: int = 0
    timestamp: str = ""


@dataclass
class AgentSession:
    """Complete record of an agent run."""

    session_id: str = ""
    goal: str = ""
    status: str = "running"  # running, completed, failed, timeout, budget_exceeded
    model_used: str = "reasoning"
    iterations: int = 0
    tokens_used: int = 0
    steps: list[AgentStep] = field(default_factory=lambda: cast(list[AgentStep], []))
    tool_calls: list[dict[str, Any]] = field(default_factory=lambda: cast(list[dict[str, Any]], []))
    final_answer: str = ""
    error: str = ""
    created_at: str = ""
    completed_at: str = ""


# ---------------------------------------------------------------------------
# Agent Loop
# ---------------------------------------------------------------------------


class AgentLoop:
    """ReAct reasoning loop with tool execution.

    Features:
        * Observe → Think → Act → Observe cycle
        * Max 10 iterations per session
        * 5-minute timeout
        * 50k token budget
        * Guard pipeline on each LLM output
        * Multi-model routing: diagnostic → fast, root cause → reasoning
        * Circuit breaker fallback to rule-based response
    """

    # Keywords that trigger the fast model (simple diagnostics, queries)
    _FAST_KEYWORDS: frozenset[str] = frozenset(
        {
            "check",
            "status",
            "list",
            "query",
            "show",
            "get",
            "fetch",
            "health",
            "disk",
            "memory",
            "cpu",
            "uptime",
            "ping",
        }
    )
    # Keywords that require the reasoning model (root cause, investigation)
    _REASONING_KEYWORDS: frozenset[str] = frozenset(
        {
            "investigate",
            "root cause",
            "why",
            "analyze",
            "correlate",
            "debug",
            "diagnose",
            "remediate",
            "fix",
            "repair",
            "plan",
        }
    )

    def __init__(
        self,
        *,
        max_iterations: int = _MAX_ITERATIONS,
        timeout_s: int = _SESSION_TIMEOUT_S,
        max_tokens: int = _MAX_TOKENS_PER_SESSION,
        model_name: str | None = None,
    ) -> None:
        self._max_iterations = max_iterations
        self._timeout_s = timeout_s
        self._max_tokens = max_tokens
        self._explicit_model = model_name
        self._model_name = model_name or "reasoning"
        self._consecutive_llm_failures = 0

    def _route_model(self, goal: str) -> str:
        """Select optimal model based on goal intent analysis.

        Returns ``"fast"`` for simple diagnostics, ``"reasoning"`` for
        complex root-cause analysis.  An explicit ``model_name`` passed
        to ``__init__`` always takes precedence.
        """
        if self._explicit_model is not None:
            return self._explicit_model

        lower = goal.lower()
        if any(kw in lower for kw in self._REASONING_KEYWORDS):
            return "reasoning"
        if any(kw in lower for kw in self._FAST_KEYWORDS):
            return "fast"
        return "reasoning"  # default to reasoning for unknown intents

    async def run(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        *,
        triggered_by: str = "cognitive_engine",
    ) -> AgentSession:
        """Execute the full ReAct loop for a given goal.

        Args:
            goal:         Natural language description of the task.
            context:      Optional dict with current CMDB state context.
            triggered_by: Who/what initiated this session.

        Returns:
            An :class:`AgentSession` with the full reasoning trace.
        """
        from internalcmdb.cognitive.tool_executor import ToolExecutor  # noqa: PLC0415
        from internalcmdb.cognitive.tool_registry import get_registry  # noqa: PLC0415
        from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

        # Auto-select model based on goal intent
        self._model_name = self._route_model(goal)

        session = AgentSession(
            session_id=getattr(self, "_session_id_override", None) or str(uuid.uuid4()),
            goal=goal,
            created_at=datetime.now(tz=UTC).isoformat(),
            model_used=self._model_name,
        )

        registry = get_registry()
        executor = ToolExecutor()
        start_time = time.monotonic()
        tools_schema = registry.openai_tools()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt(goal, context)},
            {"role": "user", "content": self._build_user_prompt(goal, context)},
        ]

        try:
            llm = await LLMClient.from_settings()
        except Exception as exc:
            session.status = "failed"
            session.error = f"LLM client init failed: {exc}"
            await self._persist_session(session, triggered_by)
            return session

        try:
            await self._reasoning_loop(
                session,
                llm,
                executor,
                messages,
                tools_schema,
                start_time,
            )
        except Exception as exc:
            session.status = "failed"
            session.error = str(exc)
            logger.exception("Agent loop failed for session %s", session.session_id)
        finally:
            session.completed_at = datetime.now(tz=UTC).isoformat()
            await llm.close()
            await self._persist_session(session, triggered_by)
            # Publish terminal event so SSE consumers know the stream is done
            await self._stream_step(
                session.session_id,
                AgentStep(
                    iteration=session.iterations,
                    phase="done",
                    content=session.final_answer or session.error or session.status,
                    timestamp=session.completed_at,
                ),
            )

        return session

    # -- Decomposed loop phases --------------------------------------------

    async def _reasoning_loop(  # noqa: PLR0913
        self,
        session: AgentSession,
        llm: Any,
        executor: Any,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]],
        start_time: float,
    ) -> None:
        """Core Observe → Think → Act → Observe cycle."""
        content = ""
        for iteration in range(1, self._max_iterations + 1):
            session.iterations = iteration

            if self._check_limits(session, start_time):
                return

            step_result = await self._run_iteration(
                session,
                llm,
                executor,
                messages,
                tools_schema,
                iteration,
            )
            if step_result is None:
                return  # session terminated (error, final answer, etc.)
            content = step_result

        # Exhausted max iterations without explicit termination
        if session.status == "running":
            session.status = "completed"
            session.final_answer = (
                content or "Maximum iterations reached without conclusive answer."
            )

    async def _run_iteration(  # noqa: PLR0913
        self,
        session: AgentSession,
        llm: Any,
        executor: Any,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]],
        iteration: int,
    ) -> str | None:
        """Run one ReAct iteration. Return content text, or ``None`` to stop."""
        response = await self._call_llm(session, llm, messages, tools_schema, iteration)
        if response is None:
            return None

        content, tool_calls, finish_reason, message = await self._parse_llm_response(
            session,
            response,
            iteration,
        )
        if session.status != "running":
            return None

        if self._check_final_answer(session, content, tool_calls, finish_reason):
            return None

        if tool_calls:
            messages.append(message)
            await self._execute_tool_calls(
                session,
                executor,
                messages,
                tool_calls,
                iteration,
            )
        else:
            messages.append({"role": "assistant", "content": content})

        return content

    def _check_limits(self, session: AgentSession, start_time: float) -> bool:
        """Return ``True`` if budget or timeout exceeded (session status set)."""
        elapsed = time.monotonic() - start_time
        if elapsed > self._timeout_s:
            session.status = "timeout"
            session.error = f"Session timed out after {int(elapsed)}s"
            return True
        if session.tokens_used > self._max_tokens:
            session.status = "budget_exceeded"
            session.error = f"Token budget exceeded: {session.tokens_used}/{self._max_tokens}"
            return True
        return False

    async def _call_llm(
        self,
        session: AgentSession,
        llm: Any,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]],
        iteration: int,
    ) -> dict[str, Any] | None:
        """Call the LLM and return the raw response, or ``None`` on failure.

        Implements a circuit breaker: after ``_LLM_CONSECUTIVE_FAILURES``
        consecutive failures, falls back to a rule-based response.
        """
        # Circuit breaker check
        if self._consecutive_llm_failures >= _LLM_CONSECUTIVE_FAILURES:
            logger.warning(
                "Circuit breaker open: %d consecutive LLM failures — falling back.",
                self._consecutive_llm_failures,
            )
            session.status = "completed"
            session.final_answer = (
                "LLM is currently degraded. Based on available data, "
                "please check the CMDB dashboard for current fleet health "
                "and review active insights for any critical issues."
            )
            return None

        try:
            if tools_schema:
                response = await llm.tool_call(
                    messages,
                    tools_schema,
                    model_name=self._model_name,
                )
            else:
                response = await llm.reason(messages)
            self._consecutive_llm_failures = 0
            return response
        except Exception as exc:
            self._consecutive_llm_failures += 1
            logger.warning(
                "LLM call failed on iteration %d (failure %d/%d): %s",
                iteration,
                self._consecutive_llm_failures,
                _LLM_CONSECUTIVE_FAILURES,
                exc,
            )
            if self._consecutive_llm_failures >= _LLM_CONSECUTIVE_FAILURES:
                session.status = "completed"
                session.final_answer = (
                    "LLM is currently degraded. Based on available data, "
                    "please check the CMDB dashboard for current fleet health "
                    "and review active insights for any critical issues."
                )
            else:
                session.status = "failed"
                session.error = f"LLM error: {exc}"
            return None

    async def _parse_llm_response(
        self,
        session: AgentSession,
        response: dict[str, Any],
        iteration: int,
    ) -> tuple[str, list[dict[str, Any]] | None, str, dict[str, Any]]:
        """Parse LLM response into (content, tool_calls, finish_reason, message).

        Appends a think step to session. Sets session to failed
        if the response is empty.
        """
        usage = response.get("usage", {})
        step_tokens = usage.get("total_tokens", 0)
        session.tokens_used += step_tokens

        choices = response.get("choices", [])
        if not choices:
            session.status = "failed"
            session.error = "Empty response from LLM"
            return "", None, "", {}

        message = choices[0].get("message", {})
        content = message.get("content", "") or ""
        tool_calls = message.get("tool_calls")
        finish_reason = choices[0].get("finish_reason", "")

        think_step = AgentStep(
            iteration=iteration,
            phase="think",
            content=content,
            tokens_used=step_tokens,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        session.steps.append(think_step)
        await self._stream_step(session.session_id, think_step)

        # Guard pipeline scan on LLM output (OWASP LLM01)
        if content:
            guard_block = self._guard_scan_output(content)
            if guard_block:
                logger.warning("Guard blocked LLM output: %s", guard_block)
                content = "[Guard blocked: potentially unsafe LLM output]"

        return content, tool_calls, finish_reason, message

    @staticmethod
    def _check_final_answer(
        session: AgentSession,
        content: str,
        tool_calls: list[dict[str, Any]] | None,
        finish_reason: str,
    ) -> bool:
        """Return ``True`` and update session if a final answer was found."""
        if _FINAL_ANSWER_MARKER in content:
            answer_start = content.index(_FINAL_ANSWER_MARKER) + len(_FINAL_ANSWER_MARKER)
            session.final_answer = content[answer_start:].strip().lstrip(":").strip()
            session.status = "completed"
            return True
        if not tool_calls and finish_reason == "stop":
            session.final_answer = content
            session.status = "completed"
            return True
        return False

    @staticmethod
    def _guard_scan_output(content: str) -> str:
        """Scan LLM output for prompt injection or unsafe patterns. Returns block reason or ''."""
        try:
            from internalcmdb.llm.security import LLMSecurityLayer  # noqa: PLC0415

            layer = LLMSecurityLayer()
            findings = layer.scan_rag_content([content])
            if findings:
                return findings[0].get("pattern", "suspicious pattern")[:100]
        except Exception:
            logger.debug("Guard scan unavailable for LLM output", exc_info=True)
        return ""

    async def _execute_tool_calls(
        self,
        session: AgentSession,
        executor: Any,
        messages: list[dict[str, Any]],
        tool_calls: list[dict[str, Any]],
        iteration: int,
    ) -> None:
        """Execute each tool call, record results, and feed observations back."""
        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            tool_args: dict[str, Any] = func.get("arguments", {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    tool_args = {}

            tc_id = tc.get("id", str(uuid.uuid4()))
            await self._execute_single_tool(
                session,
                executor,
                messages,
                tool_name,
                tool_args,
                tc_id,
                iteration,
            )

    async def _execute_single_tool(  # noqa: PLR0913
        self,
        session: AgentSession,
        executor: Any,
        messages: list[dict[str, Any]],
        tool_name: str,
        tool_args: dict[str, Any],
        tc_id: str,
        iteration: int,
    ) -> None:
        """Execute one tool, append act + observe steps, feed result to LLM."""
        act_step = AgentStep(
            iteration=iteration,
            phase="act",
            content=f"Calling tool: {tool_name}",
            tool_call={"name": tool_name, "arguments": tool_args},
            timestamp=datetime.now(tz=UTC).isoformat(),
        )

        exec_result = await executor.execute(
            tool_name,
            tool_args,
            triggered_by=f"agent:{session.session_id}",
        )

        act_step.tool_result = {
            "success": exec_result.success,
            "output": exec_result.output,
            "error": exec_result.error,
            "requires_approval": exec_result.requires_approval,
        }
        session.steps.append(act_step)
        await self._stream_step(session.session_id, act_step)
        session.tool_calls.append(
            {
                "tool": tool_name,
                "args": tool_args,
                "result": exec_result.output if exec_result.success else exec_result.error,
                "success": exec_result.success,
            }
        )

        observe_content = json.dumps(
            exec_result.output if exec_result.success else {"error": exec_result.error},
            default=str,
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc_id,
                "content": observe_content,
            }
        )

        observe_step = AgentStep(
            iteration=iteration,
            phase="observe",
            content=observe_content[:500],
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        session.steps.append(observe_step)
        await self._stream_step(session.session_id, observe_step)

        if exec_result.requires_approval:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Tool {tool_name} requires human approval "
                        f"(HITL item {exec_result.hitl_item_id}). "
                        "The action has been queued. Continue with other "
                        "diagnostic steps or provide a FINAL_ANSWER."
                    ),
                }
            )

    @staticmethod
    def _build_system_prompt(goal: str, context: dict[str, Any] | None) -> str:
        """Build the system prompt for the ReAct agent."""
        return (
            "You are an expert infrastructure diagnostic agent for internalCMDB. "
            "You operate on a fleet of servers running Docker containers, "
            "monitored by collector agents reporting system vitals, disk state, "
            "security posture, and Docker state.\n\n"
            "## Instructions\n"
            "1. Think step-by-step about the problem.\n"
            "2. Use the available tools to gather data and diagnose issues.\n"
            "3. Each tool call should have a clear purpose.\n"
            "4. After gathering enough data, synthesize findings.\n"
            "5. When you have a conclusion, include 'FINAL_ANSWER:' followed by your answer.\n\n"
            "## Safety Rules\n"
            "- NEVER execute destructive actions without explicit human approval.\n"
            "- Read-only diagnostic tools execute automatically.\n"
            "- Write operations will be queued for human review.\n"
            "- Stay focused on the stated goal. Do not deviate.\n"
            "- Maximum 10 iterations. Be efficient.\n\n"
            "## Available Context\n"
            f"Goal: {goal}\n"
        )

    @staticmethod
    def _build_user_prompt(goal: str, context: dict[str, Any] | None) -> str:
        """Build the initial user message."""
        prompt = f"Please investigate: {goal}"
        if context:
            prompt += (
                f"\n\nCurrent context:\n```json\n{json.dumps(context, indent=2, default=str)}\n```"
            )
        return prompt

    @staticmethod
    async def _stream_step(session_id: str, step: AgentStep) -> None:
        """Publish a step event to Redis for SSE consumers.

        Channel: ``infraq:agent:stream:{session_id}``
        Payload:  JSON with iteration, phase, content (capped 2000 chars), timestamp.

        Failures are silently swallowed so a Redis outage never crashes the agent.
        """
        try:
            import redis.asyncio as aioredis  # noqa: PLC0415

            from internalcmdb.api.config import get_settings  # noqa: PLC0415

            settings = get_settings()
            r: _AioRedis = aioredis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[reportUnknownMemberType]
            try:
                payload = json.dumps(
                    {
                        "session_id": session_id,
                        "iteration": step.iteration,
                        "phase": step.phase,
                        "content": step.content[:2000],
                        "tool_call": step.tool_call,
                        "timestamp": step.timestamp,
                    },
                    default=str,
                )
                _publish: Awaitable[Any] = cast(
                    Awaitable[Any],
                    r.publish(  # type: ignore[reportUnknownMemberType]
                        f"infraq:agent:stream:{session_id}", payload
                    ),
                )
                await _publish
            finally:
                await r.aclose()
        except Exception:
            logger.debug("_stream_step: failed to publish to Redis", exc_info=True)

    @staticmethod
    async def _persist_session(session: AgentSession, triggered_by: str) -> None:
        """Persist the agent session to cognitive.agent_session."""
        import asyncio  # noqa: PLC0415

        from sqlalchemy import create_engine, text  # noqa: PLC0415

        def _insert() -> None:
            try:
                from internalcmdb.api.config import get_settings  # noqa: PLC0415

                settings = get_settings()
                engine = create_engine(str(settings.database_url), pool_pre_ping=True)
                try:
                    with engine.connect() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO cognitive.agent_session
                                    (session_id, goal, status, model_used,
                                     iterations, tokens_used, tool_calls,
                                     conversation, final_answer, error,
                                     triggered_by, created_at, completed_at)
                                VALUES
                                    (:sid, :goal, :status, :model,
                                     :iters, :tokens, :tc::json,
                                     :conv::json, :answer, :error,
                                     :tb, :created, :completed)
                                ON CONFLICT (session_id) DO UPDATE SET
                                    status = EXCLUDED.status,
                                    iterations = EXCLUDED.iterations,
                                    tokens_used = EXCLUDED.tokens_used,
                                    tool_calls = EXCLUDED.tool_calls,
                                    conversation = EXCLUDED.conversation,
                                    final_answer = EXCLUDED.final_answer,
                                    error = EXCLUDED.error,
                                    completed_at = EXCLUDED.completed_at
                            """),
                            {
                                "sid": session.session_id,
                                "goal": session.goal,
                                "status": session.status,
                                "model": session.model_used,
                                "iters": session.iterations,
                                "tokens": session.tokens_used,
                                "tc": json.dumps(session.tool_calls, default=str),
                                "conv": json.dumps(
                                    [
                                        {
                                            "iteration": s.iteration,
                                            "phase": s.phase,
                                            "content": s.content[:1000],
                                        }
                                        for s in session.steps
                                    ],
                                    default=str,
                                ),
                                "answer": (
                                    session.final_answer[:5000] if session.final_answer else None
                                ),
                                "error": (session.error[:2000] if session.error else None),
                                "tb": triggered_by,
                                "created": session.created_at,
                                "completed": session.completed_at or None,
                            },
                        )
                        conn.commit()
                finally:
                    engine.dispose()
            except Exception:
                logger.debug("Failed to persist agent session", exc_info=True)

        await asyncio.to_thread(_insert)
