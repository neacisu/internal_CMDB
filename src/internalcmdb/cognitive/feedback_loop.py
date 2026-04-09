"""F6.2 — HITL Feedback Loop: record and analyse LLM-vs-human agreement.

Stores feedback rows in ``governance.hitl_feedback`` (created by migration
0007) and computes agreement rates and correction-type breakdowns per model.

Usage::

    from internalcmdb.cognitive.feedback_loop import FeedbackLoop

    fl = FeedbackLoop(async_session)
    fb_id = await fl.record_feedback(item_id, llm_suggestion, human_decision)
    stats = await fl.get_accuracy_stats(model="Qwen/QwQ-32B-AWQ")
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")),
    ("ip_address", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    ("ssh_key", re.compile(r"(ssh-rsa|ssh-ed25519|ecdsa-sha2)\s+[A-Za-z0-9+/=]+")),
    (
        "password_field",
        re.compile(r'"(password|passwd|secret|token|api_key)"\s*:\s*"[^"]*"', re.IGNORECASE),
    ),
]

_REQUIRED_FEEDBACK_KEYS = {"decision"}


def _redact_pii(obj: Any) -> Any:
    """Recursively redact PII patterns from strings inside dicts/lists."""
    if isinstance(obj, str):
        for label, pattern in _PII_PATTERNS:
            obj = pattern.sub(f"[REDACTED:{label}]", obj)
        return obj
    if isinstance(obj, dict):
        d: dict[str, Any] = obj
        return {str(k): _redact_pii(v) for k, v in d.items()}
    if isinstance(obj, list):
        lst: list[Any] = obj
        return [_redact_pii(item) for item in lst]
    return obj


class FeedbackLoop:
    """Records and queries LLM-vs-human feedback for accuracy tracking.

    Args:
        session: Async SQLAlchemy session connected to InternalCMDB.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_feedback(
        self,
        hitl_item_id: str,
        llm_suggestion: dict[str, Any],
        human_decision: dict[str, Any],
    ) -> str:
        """Persist a feedback row comparing LLM output to human decision.

        Returns the generated feedback_id.

        Raises:
            ValueError: If input dicts are missing required keys or
                        hitl_item_id does not reference an existing item.
        """
        self._validate_feedback_input(llm_suggestion, human_decision)

        item_exists = await self._session.execute(
            text("SELECT 1 FROM governance.hitl_item WHERE item_id = :iid"),
            {"iid": hitl_item_id},
        )
        if item_exists.fetchone() is None:
            msg = f"hitl_item_id '{hitl_item_id}' does not exist in governance.hitl_item"
            raise ValueError(msg)

        llm_suggestion = _redact_pii(llm_suggestion)
        human_decision = _redact_pii(human_decision)

        llm_decision = llm_suggestion.get("decision")
        human_decision_val = human_decision.get("decision")
        agreement = (
            llm_decision == human_decision_val if llm_decision and human_decision_val else None
        )

        correction_type: str | None = None
        if agreement is False:
            correction_type = _classify_correction(llm_suggestion, human_decision)

        dup_check = await self._session.execute(
            text("""
                SELECT feedback_id FROM governance.hitl_feedback
                 WHERE hitl_item_id = :item_id AND agreement = :agreement
                 ORDER BY created_at DESC LIMIT 1
            """),
            {"item_id": hitl_item_id, "agreement": agreement},
        )
        existing = dup_check.fetchone()
        if existing is not None:
            logger.info(
                "Duplicate feedback suppressed for item %s (existing=%s)",
                hitl_item_id,
                existing[0],
            )
            return str(existing[0])

        feedback_id = str(uuid.uuid4())

        await self._session.execute(
            text("""
                INSERT INTO governance.hitl_feedback
                    (feedback_id, hitl_item_id, llm_suggestion, human_decision,
                     agreement, correction_type, prompt_template_id)
                VALUES
                    (:fid, :item_id, :llm::jsonb, :human::jsonb,
                     :agreement, :correction_type, :prompt_template_id)
            """),
            {
                "fid": feedback_id,
                "item_id": hitl_item_id,
                "llm": _json_dumps(llm_suggestion),
                "human": _json_dumps(human_decision),
                "agreement": agreement,
                "correction_type": correction_type,
                "prompt_template_id": llm_suggestion.get("prompt_template_id"),
            },
        )
        await self._session.commit()
        logger.info(
            "Feedback recorded: item=%s agreement=%s correction=%s",
            hitl_item_id,
            agreement,
            correction_type,
        )
        return feedback_id

    @staticmethod
    def _validate_feedback_input(
        llm_suggestion: Any,
        human_decision: Any,
    ) -> None:
        """Validate that feedback dicts contain the minimum required keys."""
        if not isinstance(llm_suggestion, dict):
            msg = "llm_suggestion must be a dict"
            raise ValueError(msg)
        if not isinstance(human_decision, dict):
            msg = "human_decision must be a dict"
            raise ValueError(msg)

        missing = _REQUIRED_FEEDBACK_KEYS - human_decision.keys()
        if missing:
            msg = f"human_decision missing required keys: {missing}"
            raise ValueError(msg)

    async def get_accuracy_stats(self, model: str | None = None) -> dict[str, Any]:
        """Compute agreement rate and correction-type breakdown.

        Args:
            model: Optional model identifier to filter by.

        Returns a dict with keys: total, agreed, disagreed, unknown,
        agreement_rate, correction_types.
        """
        params: dict[str, Any] = {}
        model_filter = ""
        if model:
            model_filter = "AND prompt_template_id::text = :model"
            params["model"] = model

        result = await self._session.execute(
            text(
                "SELECT COUNT(*) AS total,"
                "       COUNT(*) FILTER (WHERE agreement = true) AS agreed,"
                "       COUNT(*) FILTER (WHERE agreement = false) AS disagreed,"
                "       COUNT(*) FILTER (WHERE agreement IS NULL) AS unknown,"
                "       CASE WHEN COUNT(*) FILTER (WHERE agreement IS NOT NULL) > 0"
                "            THEN ROUND("
                "                COUNT(*) FILTER (WHERE agreement = true)::numeric"
                "                / COUNT(*) FILTER (WHERE agreement IS NOT NULL)::numeric, 4)"
                "            ELSE NULL END AS agreement_rate"
                "  FROM governance.hitl_feedback"
                "  WHERE 1=1 " + model_filter
            ),
            params,
        )
        row = result.fetchone()
        stats: dict[str, Any] = (
            dict(row._mapping)
            if row
            else {
                "total": 0,
                "agreed": 0,
                "disagreed": 0,
                "unknown": 0,
                "agreement_rate": None,
            }
        )

        correction_result = await self._session.execute(
            text(
                "SELECT correction_type, COUNT(*) AS cnt"
                "  FROM governance.hitl_feedback"
                " WHERE correction_type IS NOT NULL "
                + model_filter
                + " GROUP BY correction_type ORDER BY cnt DESC"
            ),
            params,
        )
        stats["correction_types"] = {r[0]: int(r[1]) for r in correction_result.fetchall()}

        for key in ("total", "agreed", "disagreed", "unknown"):
            if key in stats and stats[key] is not None:
                stats[key] = int(stats[key])
        if stats.get("agreement_rate") is not None:
            stats["agreement_rate"] = float(stats["agreement_rate"])

        return stats

    async def get_feedback_for_item(self, hitl_item_id: str) -> list[dict[str, Any]]:
        """Return all feedback rows for a specific HITL item."""
        result = await self._session.execute(
            text("""
                SELECT feedback_id, hitl_item_id, llm_suggestion,
                       human_decision, agreement, correction_type,
                       prompt_template_id, created_at
                  FROM governance.hitl_feedback
                 WHERE hitl_item_id = :item_id
                 ORDER BY created_at DESC
            """),
            {"item_id": hitl_item_id},
        )
        return [
            {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in r._mapping.items()}
            for r in result.fetchall()
        ]


def _classify_correction(
    llm_suggestion: dict[str, Any],
    human_decision: dict[str, Any],
) -> str:
    """Heuristic correction-type classification."""
    llm_dec = llm_suggestion.get("decision", "")
    human_dec = human_decision.get("decision", "")

    if llm_dec == "approved" and human_dec == "rejected":
        return "false_positive"
    if llm_dec == "rejected" and human_dec == "approved":
        return "false_negative"
    if human_dec == "approved_with_modifications":
        return "partial_correction"
    return "other"


def _json_dumps(obj: Any) -> str:
    import json  # noqa: PLC0415

    return json.dumps(obj, default=str)
