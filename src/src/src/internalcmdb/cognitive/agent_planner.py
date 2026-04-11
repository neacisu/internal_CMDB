"""Agent Planner — decompose complex goals into ordered sub-tasks.

Uses the LLM reasoning model to break down a high-level goal into
specific, actionable sub-tasks that the AgentLoop can execute.

Usage::

    from internalcmdb.cognitive.agent_planner import AgentPlanner

    planner = AgentPlanner()
    plan = await planner.decompose("investigate why hz.113 has high disk usage")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_PLAN_JSON_SCHEMA = {
    "type": "object",
    "required": ["tasks"],
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["task_id", "description", "depends_on"],
                "properties": {
                    "task_id": {"type": "string"},
                    "description": {"type": "string"},
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "model_hint": {
                        "type": "string",
                        "enum": ["fast", "reasoning"],
                    },
                },
            },
        },
        "summary": {"type": "string"},
    },
}


@dataclass
class PlanTask:
    """A single task within a decomposed plan."""

    task_id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    model_hint: str = "reasoning"
    status: str = "pending"  # pending, running, completed, failed, skipped
    result: str = ""


@dataclass
class ExecutionPlan:
    """A decomposed plan with ordered sub-tasks."""

    plan_id: str = ""
    goal: str = ""
    tasks: list[PlanTask] = field(default_factory=list)
    summary: str = ""
    created_at: str = ""


class AgentPlanner:
    """Decompose complex goals into executable sub-task plans.

    Uses LLM reasoning with structured output to generate:
        - Ordered task list with dependency tracking
        - Model routing hints (fast vs reasoning per task)
        - Task-level status tracking
    """

    async def decompose(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        """Decompose a goal into an ordered list of sub-tasks.

        Args:
            goal:    Natural language description of the complex goal.
            context: Optional CMDB context to aid decomposition.

        Returns:
            An :class:`ExecutionPlan` with ordered tasks.
        """
        import uuid  # noqa: PLC0415

        from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

        plan = ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            goal=goal,
            created_at=datetime.now(tz=UTC).isoformat(),
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert infrastructure planner for internalCMDB. "
                    "Given a complex goal, decompose it into specific, actionable sub-tasks "
                    "that can each be executed by a diagnostic agent.\n\n"
                    "Rules:\n"
                    "- Each task should be specific and focused.\n"
                    "- Tasks should build on each other logically.\n"
                    "- Use 'fast' model_hint for simple data queries.\n"
                    "- Use 'reasoning' model_hint for complex analysis.\n"
                    "- Maximum 7 tasks per plan.\n"
                    "- Include a brief summary of the plan.\n"
                ),
            },
            {
                "role": "user",
                "content": self._build_decompose_prompt(goal, context),
            },
        ]

        try:
            llm = await LLMClient.from_settings()
            try:
                response = await llm.reason_structured(
                    messages,
                    _PLAN_JSON_SCHEMA,
                    model_name="reasoning",
                )
                parsed = response.get("_parsed", {})
                raw_tasks = parsed.get("tasks", [])
                plan.summary = parsed.get("summary", "")

                for t in raw_tasks[:7]:
                    plan.tasks.append(PlanTask(
                        task_id=t.get("task_id", str(uuid.uuid4())[:8]),
                        description=t.get("description", ""),
                        depends_on=t.get("depends_on", []),
                        model_hint=t.get("model_hint", "reasoning"),
                    ))
            finally:
                await llm.close()
        except Exception as exc:
            logger.warning("Plan decomposition failed: %s — using simple plan", exc)
            # Fallback: single-task plan
            plan.tasks = [
                PlanTask(
                    task_id="t1",
                    description=goal,
                    model_hint="reasoning",
                ),
            ]
            plan.summary = f"Direct execution: {goal}"

        logger.info(
            "Plan %s decomposed into %d tasks for: %s",
            plan.plan_id, len(plan.tasks), goal,
        )
        return plan

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        *,
        triggered_by: str = "planner",
    ) -> dict[str, Any]:
        """Execute all tasks in a plan sequentially, respecting dependencies.

        Returns a summary dict with results from each task.
        """
        from internalcmdb.cognitive.agent_loop import AgentLoop  # noqa: PLC0415

        results: dict[str, Any] = {
            "plan_id": plan.plan_id,
            "goal": plan.goal,
            "task_results": [],
        }
        completed_tasks: set[str] = set()

        for task in plan.tasks:
            # Check dependencies
            unmet = [d for d in task.depends_on if d not in completed_tasks]
            if unmet:
                task.status = "skipped"
                task.result = f"Skipped: unmet dependencies {unmet}"
                results["task_results"].append({
                    "task_id": task.task_id,
                    "status": "skipped",
                    "reason": f"Unmet deps: {unmet}",
                })
                continue

            task.status = "running"
            agent = AgentLoop(model_name=task.model_hint)
            session = await agent.run(
                task.description,
                triggered_by=triggered_by,
            )

            task.status = "completed" if session.status == "completed" else "failed"
            task.result = session.final_answer or session.error or ""
            completed_tasks.add(task.task_id)

            results["task_results"].append({
                "task_id": task.task_id,
                "status": task.status,
                "answer": session.final_answer[:500] if session.final_answer else "",
                "iterations": session.iterations,
                "tokens_used": session.tokens_used,
            })

        results["status"] = (
            "completed" if all(t.status in ("completed", "skipped") for t in plan.tasks)
            else "partial"
        )
        return results

    @staticmethod
    def _build_decompose_prompt(goal: str, context: dict[str, Any] | None) -> str:
        """Build the user prompt for plan decomposition."""
        prompt = f"Decompose this goal into sub-tasks:\n\n{goal}"
        if context:
            prompt += f"\n\nAvailable context:\n```json\n{json.dumps(context, indent=2, default=str)}\n```"
        return prompt
