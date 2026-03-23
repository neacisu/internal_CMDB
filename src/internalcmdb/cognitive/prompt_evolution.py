"""F6.3 — Prompt Evolution Engine: analyse feedback to propose improved prompts.

Identifies low-accuracy prompt templates by cross-referencing
``governance.hitl_feedback`` with the ``PromptTemplateRegistry``, then uses
LLM reasoning to generate improved versions.  Every proposed change requires
HITL approval (RC-3) before activation.

Usage::

    from internalcmdb.cognitive.prompt_evolution import PromptEvolutionEngine

    engine = PromptEvolutionEngine(async_session, llm_client)
    evals  = await engine.evaluate_prompts()
    new_text = await engine.propose_improvement("tmpl-svc-audit")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.llm.client import LLMClient

logger = logging.getLogger(__name__)

_ACCURACY_THRESHOLD = 0.80
_MIN_SAMPLES = 10


@dataclass(frozen=True)
class PromptEvaluation:
    """Evaluation result for a single prompt template."""

    template_id: str
    template_code: str
    template_version: str
    accuracy: float
    total_samples: int
    correction_types: dict[str, int] = field(default_factory=dict)
    needs_improvement: bool = False


class PromptEvolutionEngine:
    """Analyses feedback data to find low-accuracy prompts and proposes
    LLM-generated improvements.

    Args:
        session: Async SQLAlchemy session.
        llm:     LLMClient instance for reasoning calls.
        accuracy_threshold: Below this accuracy a template is flagged.
    """

    def __init__(
        self,
        session: AsyncSession,
        llm: LLMClient,
        accuracy_threshold: float = _ACCURACY_THRESHOLD,
    ) -> None:
        self._session = session
        self._llm = llm
        self._threshold = accuracy_threshold

    async def evaluate_prompts(self) -> list[PromptEvaluation]:
        """Evaluate all active prompt templates against their feedback data.

        Returns a list of :class:`PromptEvaluation` sorted by accuracy
        (lowest first).
        """
        templates = await self._session.execute(
            text("""
                SELECT prompt_template_registry_id,
                       template_code,
                       template_version
                  FROM agent_control.prompt_template_registry
                 WHERE is_active = true
            """)
        )
        template_rows = templates.fetchall()
        evaluations: list[PromptEvaluation] = []

        for row in template_rows:
            tmpl_id = str(row[0])
            tmpl_code = row[1]
            tmpl_version = row[2]

            stats = await self._get_template_stats(tmpl_code)
            total = stats.get("total", 0)
            accuracy = stats.get("accuracy", 1.0)
            corrections = stats.get("correction_types", {})

            evaluations.append(
                PromptEvaluation(
                    template_id=tmpl_id,
                    template_code=tmpl_code,
                    template_version=tmpl_version,
                    accuracy=accuracy,
                    total_samples=total,
                    correction_types=corrections,
                    needs_improvement=(
                        total >= _MIN_SAMPLES and accuracy < self._threshold
                    ),
                )
            )

        evaluations.sort(key=lambda e: e.accuracy)
        return evaluations

    async def propose_improvement(
        self,
        template_code: str,
        *,
        submit_hitl: bool = True,
    ) -> dict[str, Any]:
        """Use LLM reasoning to generate an improved prompt text.

        Args:
            template_code: Stable code identifying the template.
            submit_hitl: When True (default), automatically submits the
                         proposal as an RC-3 HITL item for review.

        Returns a dict with keys: ``improved_text``, ``template_code``,
        ``version``, ``hitl_item_id`` (None when submit_hitl is False),
        ``guard_result``.

        Raises:
            KeyError: If no active template found for the given code.
            ValueError: If insufficient feedback samples exist (< MIN_SAMPLES).
        """
        template_row = await self._session.execute(
            text("""
                SELECT template_text, template_version,
                       task_type_code, template_code
                  FROM agent_control.prompt_template_registry
                 WHERE template_code = :code AND is_active = true
                 LIMIT 1
            """),
            {"code": template_code},
        )
        row = template_row.fetchone()
        if row is None:
            msg = f"No active template found for code '{template_code}'"
            raise KeyError(msg)

        current_text = row[0]
        version = row[1]

        stats = await self._get_template_stats(template_code)
        sample_count = stats.get("total", 0)
        if sample_count < _MIN_SAMPLES:
            msg = (
                f"Insufficient feedback samples for '{template_code}': "
                f"{sample_count} < {_MIN_SAMPLES} required"
            )
            raise ValueError(msg)

        feedback_rows = await self._session.execute(
            text("""
                SELECT hf.llm_suggestion, hf.human_decision,
                       hf.agreement, hf.correction_type
                  FROM governance.hitl_feedback hf
                  JOIN governance.hitl_item hi
                    ON hi.item_id = hf.hitl_item_id
                 WHERE hf.agreement = false
                   AND (hi.item_type LIKE '%' || :code || '%'
                        OR hi.correlation_id::text LIKE '%' || :code || '%')
                 ORDER BY hf.created_at DESC
                 LIMIT 20
            """),
            {"code": template_code},
        )
        disagreements = [
            {
                "llm_suggestion": r[0],
                "human_decision": r[1],
                "correction_type": r[3],
            }
            for r in feedback_rows.fetchall()
        ]

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are an expert prompt engineer. Analyse the current prompt "
                    "template and the disagreements between LLM suggestions and human "
                    "decisions. Produce an improved version of the prompt that would "
                    "reduce false positives and false negatives. Return ONLY the "
                    "improved prompt text, nothing else."
                ),
            },
            {
                "role": "user",
                "content": _build_improvement_context(
                    template_code, version, current_text, disagreements,
                ),
            },
        ]

        response = await self._llm.reason(messages, temperature=0.3)
        improved_text = _extract_response_text(response)

        guard_result = await self._guard_scan(improved_text)
        if guard_result.get("is_valid") is False:
            logger.warning(
                "Evolved prompt for '%s' REJECTED by LLM Guard: %s",
                template_code, guard_result.get("results"),
            )
            return {
                "improved_text": None,
                "template_code": template_code,
                "version": version,
                "hitl_item_id": None,
                "guard_result": guard_result,
                "rejected": True,
                "rejection_reason": "LLM Guard flagged the evolved prompt as unsafe",
            }

        hitl_item_id: str | None = None
        if submit_hitl:
            hitl_item_id = await self._submit_hitl_review(
                template_code, version, current_text, improved_text,
            )

        logger.info(
            "Proposed improvement for template '%s' v%s (hitl_item=%s)",
            template_code, version, hitl_item_id,
        )
        return {
            "improved_text": improved_text,
            "template_code": template_code,
            "version": version,
            "hitl_item_id": hitl_item_id,
            "guard_result": guard_result,
            "rejected": False,
        }

    async def _guard_scan(self, prompt_text: str) -> dict[str, Any]:
        """Scan the evolved prompt through LLM Guard for safety."""
        try:
            return await self._llm.guard_input(prompt_text)
        except Exception:
            logger.warning("LLM Guard unavailable — skipping scan", exc_info=True)
            return {"is_valid": None, "skipped": True, "reason": "guard unavailable"}

    async def _submit_hitl_review(
        self,
        template_code: str,
        current_version: str,
        original_text: str,
        improved_text: str,
    ) -> str:
        """Submit the prompt improvement as an RC-3 HITL item for mandatory review."""
        from internalcmdb.governance.hitl_workflow import HITLWorkflow  # noqa: PLC0415

        wf = HITLWorkflow(self._session)
        item_id = await wf.submit({
            "item_type": "prompt_evolution",
            "risk_class": "RC-3",
            "source_event_id": None,
            "correlation_id": template_code,
            "context": {
                "template_code": template_code,
                "current_version": current_version,
                "original_text": original_text[:500],
                "improved_text": improved_text[:500],
            },
            "llm_suggestion": {
                "decision": "approved",
                "improved_text": improved_text,
            },
            "llm_confidence": 0.7,
            "llm_model_used": "prompt_evolution_engine",
        })
        return item_id

    async def _get_template_stats(self, template_code: str) -> dict[str, Any]:
        """Compute accuracy stats for feedback linked to a template code."""
        result = await self._session.execute(
            text("""
                SELECT
                    COUNT(*)                                          AS total,
                    CASE WHEN COUNT(*) FILTER (WHERE hf.agreement IS NOT NULL) > 0
                         THEN ROUND(
                             COUNT(*) FILTER (WHERE hf.agreement = true)::numeric
                             / COUNT(*) FILTER (WHERE hf.agreement IS NOT NULL)::numeric, 4
                         )
                         ELSE 1.0
                    END                                               AS accuracy
                FROM governance.hitl_feedback hf
                JOIN governance.hitl_item hi
                  ON hi.item_id = hf.hitl_item_id
                WHERE hi.item_type LIKE '%' || :code || '%'
                   OR hi.correlation_id LIKE '%' || :code || '%'
            """),
            {"code": template_code},
        )
        row = result.fetchone()
        stats: dict[str, Any] = {
            "total": int(row[0]) if row else 0,
            "accuracy": float(row[1]) if row and row[1] is not None else 1.0,
        }

        corrections = await self._session.execute(
            text("""
                SELECT hf.correction_type, COUNT(*) AS cnt
                  FROM governance.hitl_feedback hf
                  JOIN governance.hitl_item hi
                    ON hi.item_id = hf.hitl_item_id
                 WHERE hf.correction_type IS NOT NULL
                   AND (hi.item_type LIKE '%' || :code || '%'
                        OR hi.correlation_id LIKE '%' || :code || '%')
                 GROUP BY hf.correction_type
            """),
            {"code": template_code},
        )
        stats["correction_types"] = {r[0]: int(r[1]) for r in corrections.fetchall()}
        return stats


def _build_improvement_context(
    template_code: str,
    version: str,
    current_text: str,
    disagreements: list[dict[str, Any]],
) -> str:
    """Build the user-message context for the improvement LLM call."""
    import json  # noqa: PLC0415

    disagreement_text = json.dumps(disagreements[:10], indent=2, default=str)
    return (
        f"## Template: {template_code} (v{version})\n\n"
        f"### Current Prompt:\n```\n{current_text}\n```\n\n"
        f"### Recent Disagreements (LLM wrong, human corrected):\n"
        f"```json\n{disagreement_text}\n```\n\n"
        f"Produce an improved prompt that addresses the patterns in these "
        f"disagreements while preserving the template's core intent."
    )


def _extract_response_text(response: dict[str, Any]) -> str:
    """Extract the assistant message text from a chat completion response."""
    choices = response.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return ""
