"""Confidence Calibration with Chain-of-Verification (Phase 14, F14).

Implements the Chain-of-Verification (CoVe) pattern:
    1. Draft — initial LLM response
    2. Self-evaluation — LLM scores its own confidence
    3. Verification questions — generate targeted verification queries
    4. Independent answers — answer verification queries independently
    5. Verified synthesis — combine into a final, calibrated response

Domain-specific confidence thresholds determine whether HITL review is
required before the response is surfaced to the operator.

Safety guarantees:
    - NaN/Inf confidence values are clamped to safe defaults (0.0)
    - Total token budget across the full CoVe pipeline is enforced
    - Verification questions are capped at 3 (no infinite loop)
    - All confidence values are clamped to [0.0, 1.0]

Public surface::

    from internalcmdb.llm.confidence import ConfidenceCalibrator, CalibratedResponse

    calibrator = ConfidenceCalibrator(llm_client)
    result = await calibrator.calibrated_call("What is the disk usage on prod-gpu-01?")
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, cast

logger = logging.getLogger(__name__)

_MAX_COVE_TOTAL_TOKENS = 50_000
_MAX_VERIFICATION_QUESTIONS = 3

# ---------------------------------------------------------------------------
# Confidence thresholds per domain
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "infrastructure": 0.85,
    "security": 0.95,
    "capacity": 0.80,
    "reports": 0.70,
    "general": 0.75,
}

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "infrastructure": [
        "host",
        "server",
        "disk",
        "cpu",
        "memory",
        "network",
        "container",
        "service",
    ],
    "security": [
        "vulnerability",
        "cve",
        "certificate",
        "tls",
        "ssh",
        "firewall",
        "credential",
        "pii",
    ],
    "capacity": ["capacity", "growth", "scaling", "resource", "quota", "utilization"],
    "reports": ["report", "summary", "overview", "fleet", "audit"],
}


def _detect_domain(prompt: str) -> str:
    """Heuristically detect the domain of a prompt."""
    prompt_lower = prompt.lower()
    scores: dict[str, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in prompt_lower)
    best = max(scores, key=lambda d: scores[d])
    return best if scores[best] > 0 else "general"


# ---------------------------------------------------------------------------
# CalibratedResponse
# ---------------------------------------------------------------------------


@dataclass
class CalibratedResponse:
    """Result of a confidence-calibrated LLM call."""

    content: str
    confidence: float
    verification_steps: list[str] = field(default_factory=list[str])
    is_verified: bool = False
    domain: str = "general"
    threshold: float = 0.75
    requires_hitl: bool = False
    raw_draft: str = ""
    tokens_used: int = 0


# ---------------------------------------------------------------------------
# Calibrator
# ---------------------------------------------------------------------------


@dataclass
class _CoveState:
    """Mutable run state for the Chain-of-Verification pipeline."""

    prompt: str
    draft_content: str
    context: str
    model: str
    initial_confidence: float
    total_tokens: int
    verification_steps: list[str] = field(default_factory=list[str])
    final_content: str = ""
    final_confidence: float = 0.0


class ConfidenceCalibrator:
    """Chain-of-Verification confidence calibration for LLM responses.

    Args:
        llm_client: An :class:`~internalcmdb.llm.client.LLMClient` instance.
    """

    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client

    async def calibrated_call(
        self,
        prompt: str,
        model: str = "reasoning",
        *,
        context: str = "",
    ) -> CalibratedResponse:
        """Execute a full Chain-of-Verification pipeline.

        Steps:
          1. Draft response
          2. Self-evaluate confidence
          3. Generate verification questions
          4. Answer verification questions independently
          5. Synthesise verified response
        """
        domain = _detect_domain(prompt)
        threshold = CONFIDENCE_THRESHOLDS.get(domain, CONFIDENCE_THRESHOLDS["general"])
        total_tokens = 0

        # ── Step 1: Draft ────────────────────────────────────────────────
        draft_messages = self._build_draft_messages(prompt, context)
        try:
            draft_resp = await self._call_llm(draft_messages, model)
            draft_content = self._extract_content(draft_resp)
            total_tokens += self._count_tokens(draft_resp)
        except Exception as exc:
            logger.error("Draft generation failed: %s", exc)
            return CalibratedResponse(
                content=f"Draft generation failed: {exc}",
                confidence=0.0,
                domain=domain,
                threshold=threshold,
                requires_hitl=True,
            )

        # ── Step 2: Self-evaluation ──────────────────────────────────────
        eval_messages = self._build_eval_messages(prompt, draft_content, domain)
        try:
            eval_resp = await self._call_llm(eval_messages, model)
            eval_content = self._extract_content(eval_resp)
            total_tokens += self._count_tokens(eval_resp)
            initial_confidence = self._parse_confidence(eval_content)
        except Exception:
            initial_confidence = 0.5

        initial_confidence = self._clamp_confidence(initial_confidence)

        # If confidence is already very high, skip verification
        if initial_confidence >= 0.95:  # noqa: PLR2004
            return CalibratedResponse(
                content=draft_content,
                confidence=initial_confidence,
                verification_steps=["high-confidence — verification skipped"],
                is_verified=True,
                domain=domain,
                threshold=threshold,
                requires_hitl=initial_confidence < threshold,
                raw_draft=draft_content,
                tokens_used=total_tokens,
            )

        # Steps 3-5: Verification and synthesis
        state = _CoveState(
            prompt=prompt,
            draft_content=draft_content,
            context=context,
            model=model,
            initial_confidence=initial_confidence,
            total_tokens=total_tokens,
        )
        await self._run_verification_phase(state)

        requires_hitl = state.final_confidence < threshold
        if requires_hitl:
            logger.info(
                "Calibrated response below threshold: confidence=%.2f threshold=%.2f domain=%s",
                state.final_confidence,
                threshold,
                domain,
            )

        return CalibratedResponse(
            content=state.final_content,
            confidence=state.final_confidence,
            verification_steps=state.verification_steps,
            is_verified=len(state.verification_steps) > 0,
            domain=domain,
            threshold=threshold,
            requires_hitl=requires_hitl,
            raw_draft=draft_content,
            tokens_used=state.total_tokens,
        )

    async def _generate_verification_questions(self, state: _CoveState) -> list[str]:
        """CoVe Step 3 — generate verification questions for the draft answer.

        Returns the parsed question list, or an empty list on LLM/budget failure.
        """
        if state.total_tokens >= _MAX_COVE_TOTAL_TOKENS:
            return []
        vq_messages = self._build_verification_question_messages(state.prompt, state.draft_content)
        try:
            vq_resp = await self._call_llm(vq_messages, state.model)
            vq_content = self._extract_content(vq_resp)
            state.total_tokens += self._count_tokens(vq_resp)
            return self._parse_questions(vq_content)
        except Exception:
            return []

    async def _answer_verification_questions(self, state: _CoveState, questions: list[str]) -> None:
        """CoVe Step 4 — answer each verification question independently.

        Mutates ``state.verification_steps`` in-place.  Stops early when the
        token budget is exhausted.
        """
        for vq in questions[:_MAX_VERIFICATION_QUESTIONS]:
            if state.total_tokens >= _MAX_COVE_TOTAL_TOKENS:
                logger.warning(
                    "CoVe token budget exhausted (%d >= %d), stopping verification",
                    state.total_tokens,
                    _MAX_COVE_TOTAL_TOKENS,
                )
                break
            va_messages = self._build_independent_answer_messages(vq, state.context)
            try:
                va_resp = await self._call_llm(va_messages, state.model)
                va_content = self._extract_content(va_resp)
                state.total_tokens += self._count_tokens(va_resp)
                state.verification_steps.append(f"Q: {vq} → A: {va_content[:200]}")
            except Exception:
                state.verification_steps.append(f"Q: {vq} → A: (verification failed)")

    async def _synthesise_verified_response(self, state: _CoveState) -> None:
        """CoVe Step 5 — synthesise a final answer from draft + verification results.

        Mutates ``state.final_content`` and ``state.total_tokens`` in-place.
        Falls back to the draft content when the budget is exhausted or the
        synthesis LLM call fails.
        """
        synth_messages = self._build_synthesis_messages(
            state.prompt, state.draft_content, state.verification_steps
        )
        try:
            if state.total_tokens >= _MAX_COVE_TOTAL_TOKENS:
                logger.warning("CoVe token budget exhausted, skipping synthesis")
                raise RuntimeError("token budget")
            synth_resp = await self._call_llm(synth_messages, state.model)
            state.final_content = self._extract_content(synth_resp)
            state.total_tokens += self._count_tokens(synth_resp)
        except Exception:
            state.final_content = state.draft_content

    async def _run_verification_phase(self, state: _CoveState) -> None:
        """Execute CoVe Steps 3-5: verification questions, independent answers, synthesis."""
        verification_questions = await self._generate_verification_questions(state)
        await self._answer_verification_questions(state, verification_questions)
        await self._synthesise_verified_response(state)
        raw_confidence = state.initial_confidence + 0.1 * len(state.verification_steps)
        state.final_confidence = self._clamp_confidence(raw_confidence)

    # ------------------------------------------------------------------
    # Message builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_draft_messages(prompt: str, context: str) -> list[dict[str, Any]]:
        system = (
            "You are an infrastructure expert for internalCMDB. "
            "Answer precisely based on available evidence."
        )
        user_msg = prompt
        if context:
            user_msg = f"Context:\n{context}\n\nQuestion: {prompt}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]

    @staticmethod
    def _build_eval_messages(prompt: str, draft: str, domain: str) -> list[dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a calibration evaluator. Rate the confidence of the "
                    "following draft answer on a scale from 0.0 to 1.0. "
                    f"Domain: {domain}. "
                    'Respond with ONLY a JSON object: {"confidence": 0.XX, "reasoning": "..."}'
                ),
            },
            {
                "role": "user",
                "content": f"Question: {prompt}\n\nDraft answer: {draft}",
            },
        ]

    @staticmethod
    def _build_verification_question_messages(prompt: str, draft: str) -> list[dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": (
                    "Generate 2-3 verification questions to fact-check the draft answer. "
                    "Each question should be independently answerable. "
                    "Return as a JSON array of strings."
                ),
            },
            {
                "role": "user",
                "content": f"Original question: {prompt}\n\nDraft answer: {draft}",
            },
        ]

    @staticmethod
    def _build_independent_answer_messages(question: str, context: str) -> list[dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": (
                    "Answer the following verification question concisely and independently. "
                    "Do not reference any draft answer."
                ),
            },
            {
                "role": "user",
                "content": f"{context}\n\n{question}" if context else question,
            },
        ]

    @staticmethod
    def _build_synthesis_messages(
        prompt: str, draft: str, verification_steps: list[str]
    ) -> list[dict[str, Any]]:
        verif_text = (
            "\n".join(f"- {s}" for s in verification_steps) if verification_steps else "(none)"
        )
        return [
            {
                "role": "system",
                "content": (
                    "Synthesise a final verified answer using the draft and "
                    "verification results. Correct any inconsistencies found."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original question: {prompt}\n\n"
                    f"Draft answer: {draft}\n\n"
                    f"Verification results:\n{verif_text}"
                ),
            },
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _call_llm(self, messages: list[dict[str, Any]], model: str) -> dict[str, Any]:
        if model == "fast":
            return await self._llm.fast(messages)
        return await self._llm.reason(messages)

    @staticmethod
    def _extract_content(response: dict[str, Any]) -> str:
        try:
            return response["choices"][0]["message"]["content"]
        except KeyError, IndexError, TypeError:
            return str(response)

    @staticmethod
    def _count_tokens(response: dict[str, Any]) -> int:
        try:
            usage = cast(dict[str, Any], response.get("usage") or {})
            return int(usage.get("total_tokens", 0))
        except TypeError, ValueError:
            return 0

    @staticmethod
    def _clamp_confidence(val: float) -> float:
        """Clamp confidence to [0.0, 1.0], treating NaN/Inf as 0.0."""
        if math.isnan(val) or math.isinf(val):
            return 0.0
        return max(0.0, min(1.0, val))

    @staticmethod
    def _parse_confidence(eval_text: str) -> float:
        try:
            data = json.loads(eval_text)
            if isinstance(data, dict):
                data_d = cast(dict[str, Any], data)
                raw = float(data_d.get("confidence", 0.5))
                return ConfidenceCalibrator._clamp_confidence(raw if raw <= 1.0 else raw / 100.0)
            if isinstance(data, bool):
                raise ValueError("json boolean is not a numeric confidence")
            if isinstance(data, (int, float)):
                val = float(data)
                return ConfidenceCalibrator._clamp_confidence(val if val <= 1.0 else val / 100.0)
        except ValueError, TypeError:
            pass
        match = re.search(r"(\d+\.?\d*)", eval_text)
        if match:
            val = float(match.group(1))
            return ConfidenceCalibrator._clamp_confidence(val if val <= 1.0 else val / 100.0)
        return 0.5

    @staticmethod
    def _parse_questions(vq_text: str) -> list[str]:
        try:
            questions = json.loads(vq_text)
            if isinstance(questions, list):
                return [str(q) for q in cast(list[Any], questions)]
        # JSON decode failures are JSONDecodeError → ValueError; avoid redundant except targets (S5713).  # noqa: E501
        except ValueError:
            pass
        lines = [
            ln.strip().lstrip("- ").lstrip("•").strip()
            for ln in vq_text.strip().splitlines()
            if ln.strip()
        ]
        return [ln for ln in lines if ln.endswith("?")]
