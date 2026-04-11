"""Tests for AgentPlanner, PlanTask, and ExecutionPlan.

Covers:
  - PlanTask dataclass: default construction, list isolation, explicit values
  - ExecutionPlan dataclass: default construction, list isolation
  - AgentPlanner._build_decompose_prompt: static method, context handling
  - Typed default factories: _default_str_list, _default_plan_task_list
"""

from __future__ import annotations

import inspect
import json
from datetime import datetime

from internalcmdb.cognitive.agent_planner import (
    AgentPlanner,
    ExecutionPlan,
    PlanTask,
    _default_plan_task_list,
    _default_str_list,
)

# ---------------------------------------------------------------------------
# Typed default factories
# ---------------------------------------------------------------------------


class TestDefaultFactories:
    """Verify that the typed default factories return correctly typed empty lists."""

    def test_default_str_list_returns_empty_list(self) -> None:
        result = _default_str_list()
        assert result == []

    def test_default_str_list_returns_new_instance_each_call(self) -> None:
        a = _default_str_list()
        b = _default_str_list()
        a.append("x")
        assert b == [], "Each call must return a distinct list (no shared mutable default)"

    def test_default_plan_task_list_returns_empty_list(self) -> None:
        result = _default_plan_task_list()
        assert result == []

    def test_default_plan_task_list_returns_new_instance_each_call(self) -> None:
        a = _default_plan_task_list()
        b = _default_plan_task_list()
        a.append(PlanTask(task_id="t1", description="d"))
        assert b == [], "Each call must return a distinct list"


# ---------------------------------------------------------------------------
# PlanTask dataclass
# ---------------------------------------------------------------------------


class TestPlanTask:
    """Tests for PlanTask construction and field typing."""

    def test_default_construction_requires_task_id_and_description(self) -> None:
        task = PlanTask(task_id="t1", description="check disk usage")
        assert task.task_id == "t1"
        assert task.description == "check disk usage"

    def test_default_depends_on_is_empty_list(self) -> None:
        task = PlanTask(task_id="t1", description="x")
        assert task.depends_on == []

    def test_default_model_hint_is_reasoning(self) -> None:
        task = PlanTask(task_id="t1", description="x")
        assert task.model_hint == "reasoning"

    def test_default_status_is_pending(self) -> None:
        task = PlanTask(task_id="t1", description="x")
        assert task.status == "pending"

    def test_default_result_is_empty_string(self) -> None:
        task = PlanTask(task_id="t1", description="x")
        assert task.result == ""

    def test_depends_on_is_isolated_per_instance(self) -> None:
        """Each PlanTask must have its own depends_on list — no shared mutable default."""
        t1 = PlanTask(task_id="t1", description="first")
        t2 = PlanTask(task_id="t2", description="second")
        t1.depends_on.append("t0")
        assert t2.depends_on == [], (
            "Mutation of t1.depends_on must not affect t2 — confirms default_factory isolation"
        )

    def test_explicit_depends_on(self) -> None:
        task = PlanTask(task_id="t2", description="analyze", depends_on=["t1"])
        assert task.depends_on == ["t1"]

    def test_model_hint_fast(self) -> None:
        task = PlanTask(task_id="t1", description="query", model_hint="fast")
        assert task.model_hint == "fast"

    def test_status_transitions(self) -> None:
        task = PlanTask(task_id="t1", description="x")
        for state in ("pending", "running", "completed", "failed", "skipped"):
            task.status = state
            assert task.status == state

    def test_result_accepts_long_string(self) -> None:
        task = PlanTask(task_id="t1", description="x")
        task.result = "A" * 10_000
        assert len(task.result) == 10_000

    def test_depends_on_accepts_multiple_dependency_ids(self) -> None:
        task = PlanTask(
            task_id="t3",
            description="correlate",
            depends_on=["t1", "t2"],
        )
        assert len(task.depends_on) == 2
        assert "t1" in task.depends_on
        assert "t2" in task.depends_on


# ---------------------------------------------------------------------------
# ExecutionPlan dataclass
# ---------------------------------------------------------------------------


class TestExecutionPlan:
    """Tests for ExecutionPlan construction and field typing."""

    def test_default_construction(self) -> None:
        plan = ExecutionPlan()
        assert plan.plan_id == ""
        assert plan.goal == ""
        assert plan.tasks == []
        assert plan.summary == ""
        assert plan.created_at == ""

    def test_tasks_is_isolated_per_instance(self) -> None:
        """Each ExecutionPlan must have its own tasks list — no shared mutable default."""
        p1 = ExecutionPlan()
        p2 = ExecutionPlan()
        p1.tasks.append(PlanTask(task_id="t1", description="first"))
        assert p2.tasks == [], (
            "Mutation of p1.tasks must not affect p2 — confirms default_factory isolation"
        )

    def test_explicit_construction(self) -> None:
        plan = ExecutionPlan(
            plan_id="plan-001",
            goal="investigate disk usage on hz.223",
            summary="Two-step disk diagnostics plan",
            created_at="2026-04-10T12:00:00+00:00",
        )
        assert plan.plan_id == "plan-001"
        assert plan.goal == "investigate disk usage on hz.223"
        assert plan.summary == "Two-step disk diagnostics plan"

    def test_tasks_accepts_plan_task_items(self) -> None:
        plan = ExecutionPlan(plan_id="p1", goal="test")
        t1 = PlanTask(task_id="t1", description="step one")
        t2 = PlanTask(task_id="t2", description="step two", depends_on=["t1"])
        plan.tasks.extend([t1, t2])
        assert len(plan.tasks) == 2
        assert plan.tasks[1].depends_on == ["t1"]

    def test_tasks_list_supports_status_updates(self) -> None:
        plan = ExecutionPlan()
        task = PlanTask(task_id="t1", description="check")
        plan.tasks.append(task)
        plan.tasks[0].status = "completed"
        assert plan.tasks[0].status == "completed"


# ---------------------------------------------------------------------------
# AgentPlanner._build_decompose_prompt
# ---------------------------------------------------------------------------


class TestBuildDecomposePrompt:
    """Tests for the static prompt-builder method."""

    def test_prompt_contains_goal(self) -> None:
        prompt = AgentPlanner._build_decompose_prompt("investigate memory leak on hz.62", None)
        assert "investigate memory leak on hz.62" in prompt

    def test_prompt_without_context_omits_json_block(self) -> None:
        prompt = AgentPlanner._build_decompose_prompt("goal", None)
        assert "```json" not in prompt

    def test_prompt_with_empty_context_omits_json_block(self) -> None:
        """Empty dict is falsy — context block must be suppressed."""
        prompt_no_ctx = AgentPlanner._build_decompose_prompt("goal", None)
        prompt_empty = AgentPlanner._build_decompose_prompt("goal", {})
        assert prompt_no_ctx == prompt_empty

    def test_prompt_with_context_contains_json_block(self) -> None:
        ctx = {"host": "hz.62", "disk_pct": 92.5}
        prompt = AgentPlanner._build_decompose_prompt("check disk", ctx)
        assert "```json" in prompt
        assert "hz.62" in prompt
        assert "92.5" in prompt

    def test_prompt_context_json_is_valid(self) -> None:
        ctx = {"nested": {"cpu": 88, "mem": 72}, "tags": ["production", "europe"]}
        prompt = AgentPlanner._build_decompose_prompt("analyze", ctx)
        start = prompt.find("```json\n") + len("```json\n")
        end = prompt.find("\n```", start)
        json_block = prompt[start:end]
        parsed = json.loads(json_block)
        assert parsed["nested"]["cpu"] == 88
        assert parsed["tags"] == ["production", "europe"]

    def test_prompt_with_non_serialisable_context_uses_default_str(self) -> None:
        """Objects that are not JSON-serialisable must be rendered via default=str."""
        ctx = {"ts": datetime(2026, 4, 10, 12, 0, 0)}
        prompt = AgentPlanner._build_decompose_prompt("goal", ctx)
        # Must not raise; the datetime is stringified
        assert "2026" in prompt

    def test_prompt_line_lengths_within_100_chars(self) -> None:
        """Regression guard for E501 — the longest generated line must stay ≤100 chars."""
        ctx = {"key": "value" * 5}
        prompt = AgentPlanner._build_decompose_prompt("some goal text", ctx)
        # The static method produces multi-line output; we only check the
        # fixed-text line that was previously > 100 chars is now shorter.
        for line in prompt.splitlines():
            # The f-string prefix up to the JSON block is the historically long line
            if "Available context" in line:
                assert len(line) <= 100, (
                    f"'Available context' line is too long ({len(line)} chars): {line!r}"
                )


# ---------------------------------------------------------------------------
# AgentPlanner instantiation
# ---------------------------------------------------------------------------


class TestAgentPlannerInstantiation:
    def test_default_instantiation(self) -> None:
        planner = AgentPlanner()
        assert isinstance(planner, AgentPlanner)

    def test_is_callable_async(self) -> None:
        planner = AgentPlanner()
        assert inspect.iscoroutinefunction(planner.decompose)
        assert inspect.iscoroutinefunction(planner.execute_plan)
