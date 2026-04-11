"""Tests for AgentLoop model routing and initialization.

Covers:
  - Automatic model selection based on goal intent keywords
  - Explicit model override takes precedence
  - Edge cases: empty goal, mixed keywords, unknown intent
"""

from __future__ import annotations

import json

from internalcmdb.cognitive.agent_loop import AgentLoop, AgentSession, AgentStep


class TestModelRouting:
    """Tests for _route_model() intent-based model selection."""

    def test_diagnostic_keywords_route_to_fast(self) -> None:
        loop = AgentLoop()
        assert loop._route_model("check disk usage on hz.223") == "fast"
        assert loop._route_model("show status of all hosts") == "fast"
        assert loop._route_model("list services on production") == "fast"
        assert loop._route_model("get health scores") == "fast"
        assert loop._route_model("query CPU utilization") == "fast"

    def test_reasoning_keywords_route_to_reasoning(self) -> None:
        loop = AgentLoop()
        assert loop._route_model("investigate why hz.62 is slow") == "reasoning"
        assert loop._route_model("analyze root cause of outage") == "reasoning"
        assert loop._route_model("diagnose memory leak on orchestrator") == "reasoning"
        assert loop._route_model("correlate incidents across fleet") == "reasoning"
        assert loop._route_model("fix the certificate issue") == "reasoning"
        assert loop._route_model("remediate disk full on hz.223") == "reasoning"

    def test_reasoning_takes_precedence_over_fast(self) -> None:
        """When both fast and reasoning keywords present, reasoning wins."""
        loop = AgentLoop()
        # "investigate" (reasoning) + "check" (fast) → reasoning
        assert loop._route_model("investigate and check disk root cause") == "reasoning"
        # "why" (reasoning) + "status" (fast) → reasoning
        assert loop._route_model("why is the status degraded") == "reasoning"

    def test_unknown_intent_defaults_to_reasoning(self) -> None:
        loop = AgentLoop()
        assert loop._route_model("do something about the infrastructure") == "reasoning"
        assert loop._route_model("") == "reasoning"

    def test_explicit_model_overrides_routing(self) -> None:
        loop = AgentLoop(model_name="fast")
        # Even with reasoning keywords, explicit model wins
        assert loop._route_model("investigate root cause") == "fast"

    def test_explicit_model_none_enables_routing(self) -> None:
        loop = AgentLoop(model_name=None)
        assert loop._route_model("check disk usage") == "fast"
        assert loop._route_model("investigate outage") == "reasoning"

    def test_case_insensitive_routing(self) -> None:
        loop = AgentLoop()
        assert loop._route_model("CHECK DISK USAGE") == "fast"
        assert loop._route_model("INVESTIGATE THE ISSUE") == "reasoning"


class TestAgentLoopInit:
    """Tests for AgentLoop constructor defaults and overrides."""

    def test_default_values(self) -> None:
        loop = AgentLoop()
        assert loop._max_iterations == 10
        assert loop._timeout_s == 300
        assert loop._max_tokens == 50_000
        assert loop._explicit_model is None
        assert loop._model_name == "reasoning"

    def test_explicit_model_stored(self) -> None:
        loop = AgentLoop(model_name="fast")
        assert loop._explicit_model == "fast"
        assert loop._model_name == "fast"

    def test_none_model_enables_auto_routing(self) -> None:
        loop = AgentLoop(model_name=None)
        assert loop._explicit_model is None
        assert loop._model_name == "reasoning"  # default before routing

    def test_custom_limits(self) -> None:
        loop = AgentLoop(max_iterations=5, timeout_s=60, max_tokens=10_000)
        assert loop._max_iterations == 5
        assert loop._timeout_s == 60
        assert loop._max_tokens == 10_000


# ---------------------------------------------------------------------------
# AgentSession dataclass — field typing correctness
# ---------------------------------------------------------------------------


class TestAgentSession:
    def test_default_construction(self) -> None:
        """AgentSession must be constructible with all defaults."""
        s = AgentSession()
        assert s.session_id == ""
        assert s.goal == ""
        assert s.status == "running"
        assert s.model_used == "reasoning"
        assert s.iterations == 0
        assert s.tokens_used == 0
        assert s.steps == []
        assert s.tool_calls == []
        assert s.final_answer == ""
        assert s.error == ""

    def test_steps_field_is_typed_list(self) -> None:
        """steps must be a mutable list of AgentStep (not shared across instances)."""
        s1 = AgentSession()
        s2 = AgentSession()
        step = AgentStep(iteration=1, phase="think", content="hello", tokens_used=5)
        s1.steps.append(step)
        assert len(s1.steps) == 1
        assert len(s2.steps) == 0  # isolation confirms default_factory, not shared

    def test_tool_calls_field_is_typed_list(self) -> None:
        """tool_calls must be isolated per instance."""
        s1 = AgentSession()
        s2 = AgentSession()
        s1.tool_calls.append({"tool": "query_host_health", "result": "ok"})
        assert len(s1.tool_calls) == 1
        assert len(s2.tool_calls) == 0

    def test_steps_field_accepts_agent_step(self) -> None:
        s = AgentSession()
        step = AgentStep(iteration=2, phase="act", content="calling tool", tokens_used=42)
        s.steps.append(step)
        assert s.steps[0].phase == "act"
        assert s.steps[0].tokens_used == 42

    def test_tool_calls_field_accepts_dicts(self) -> None:
        s = AgentSession()
        tc: dict[str, object] = {
            "id": "tc-001",
            "function": {"name": "query_fleet_summary", "arguments": "{}"},
        }
        s.tool_calls.append(tc)
        assert s.tool_calls[0]["id"] == "tc-001"


# ---------------------------------------------------------------------------
# AgentStep dataclass
# ---------------------------------------------------------------------------


class TestAgentStep:
    def test_default_construction(self) -> None:
        step = AgentStep(iteration=0, phase="think", content="")
        assert step.iteration == 0
        assert step.phase == "think"
        assert step.content == ""
        assert step.tool_call is None
        assert step.tool_result is None
        assert step.tokens_used == 0
        assert step.timestamp == ""

    def test_explicit_construction(self) -> None:
        step = AgentStep(
            iteration=3,
            phase="observe",
            content="tool returned 5 hosts",
            tokens_used=120,
            timestamp="2026-04-10T10:00:00+00:00",
        )
        assert step.iteration == 3
        assert step.phase == "observe"
        assert step.content == "tool returned 5 hosts"
        assert step.tokens_used == 120


# ---------------------------------------------------------------------------
# _build_user_prompt — static method
# ---------------------------------------------------------------------------


class TestBuildUserPrompt:
    def test_prompt_without_context(self) -> None:
        prompt = AgentLoop._build_user_prompt("check disk on hz.62", None)
        assert "hz.62" in prompt
        assert "investigate" in prompt.lower() or "hz.62" in prompt

    def test_prompt_with_context_contains_json(self) -> None:
        ctx = {"host": "hz.62", "cpu_pct": 87.5}
        prompt = AgentLoop._build_user_prompt("check disk on hz.62", ctx)
        assert "hz.62" in prompt
        assert "cpu_pct" in prompt
        assert "87.5" in prompt

    def test_prompt_with_empty_context_omits_json_block(self) -> None:
        """Empty dict is falsy — context block must not be appended."""
        prompt_no_ctx = AgentLoop._build_user_prompt("goal", None)
        prompt_empty_ctx = AgentLoop._build_user_prompt("goal", {})
        assert prompt_no_ctx == prompt_empty_ctx

    def test_prompt_context_is_valid_json(self) -> None:
        ctx = {"key": "value", "nested": {"a": 1}}
        prompt = AgentLoop._build_user_prompt("goal", ctx)
        # Extract the JSON block between ```json and ```
        start = prompt.find("```json\n") + len("```json\n")
        end = prompt.find("\n```", start)
        json_block = prompt[start:end]
        parsed = json.loads(json_block)
        assert parsed["key"] == "value"


# ---------------------------------------------------------------------------
# _guard_scan_output — no LLM security layer available (import fails gracefully)
# ---------------------------------------------------------------------------


class TestGuardScanOutput:
    def test_returns_empty_string_without_security_layer(self) -> None:
        """When LLMSecurityLayer is unavailable, guard returns '' (no block)."""
        loop = AgentLoop()
        result = loop._guard_scan_output("normal output about disk usage")
        assert result == ""

    def test_returns_empty_string_for_empty_content(self) -> None:
        loop = AgentLoop()
        assert loop._guard_scan_output("") == ""
