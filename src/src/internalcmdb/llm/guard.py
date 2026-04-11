"""F1.3 — Guard Pipeline: pre/post-scan wrapper around LLM generation.

Wraps every LLM call in an input→generate→output scan pipeline using
the LLM Guard service (``/analyze/prompt`` and ``/analyze/output``).

The pipeline enforces guardrails defined in LLM-005 (Portable Model Registry)
and routed through the Traefik gateway at ``https://infraq.app/llm/v1/guard``.

Guard endpoints (Bearer auth required):
  POST /analyze/prompt  — scan user input  (injection, PII, toxicity)
  POST /analyze/output  — scan model output (sensitive data, toxicity, relevance)

Response format from guard:
  {"is_valid": bool, "scanners": {"ScannerName": float, ...}}

Usage::

    from internalcmdb.llm.guard import GuardPipeline

    pipeline = GuardPipeline(llm_client)
    result = await pipeline.guarded_call("Explain quantum computing")
    if result.blocked:
        print(f"Blocked: {result.input_scan or result.output_scan}")
    else:
        print(result.content)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from internalcmdb.llm.client import LLMClient

logger = logging.getLogger(__name__)
_audit_logger = logging.getLogger("internalcmdb.guard.audit")

_VALID_MODELS = frozenset({"reasoning", "fast"})


@dataclass(frozen=True)
class GuardResult:
    """Outcome of a single guard scan (input or output).

    Attributes:
        is_valid: Whether the content passed all scanners.
        score:    Aggregate risk score (0.0 = clean, higher = riskier).
                  Computed as the max of all individual scanner scores.
        details:  Per-scanner score mapping as returned by the guard service.
    """

    is_valid: bool
    score: float
    details: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))


@dataclass(frozen=True)
class GuardedResponse:
    """Complete result from a guarded LLM call.

    Attributes:
        blocked:     True when either the input or output scan rejected the content.
        content:     The generated text (None when input was blocked before generation).
        input_scan:  Result from the pre-generation input scan, if performed.
        output_scan: Result from the post-generation output scan, if performed.
    """

    blocked: bool
    content: str | None = None
    input_scan: GuardResult | None = None
    output_scan: GuardResult | None = None


def _parse_guard_response(raw: dict[str, Any]) -> GuardResult:
    """Parse the guard service JSON response into a ``GuardResult``."""
    is_valid = bool(raw.get("is_valid", False))
    scanners: dict[str, float] = raw.get("scanners", {})
    score = max(scanners.values()) if scanners else 0.0
    return GuardResult(is_valid=is_valid, score=score, details=dict(scanners))


class GuardPipeline:
    """Pre/post-scan pipeline wrapping LLM generation with guardrails.

    Args:
        llm_client: An ``LLMClient`` instance (F1.2) that exposes
                     ``guard_input``, ``guard_output``, ``reason``, and ``fast``
                     async methods.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client
        self.stats_passed: int = 0
        self.stats_blocked_input: int = 0
        self.stats_blocked_output: int = 0
        self.stats_errors: int = 0

    async def guarded_call(
        self,
        prompt: str,
        model: str = "reasoning",
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> GuardedResponse:
        """Execute a full guard→generate→guard pipeline.

        Steps:
          1. Pre-scan the user prompt via ``/analyze/prompt``.
          2. If blocked → return immediately with ``blocked=True``.
          3. Generate a response using the requested model.
          4. Post-scan the generated output via ``/analyze/output``.
          5. If blocked → return with ``blocked=True`` but include the content.
          6. Return ``blocked=False`` with both scan results attached.

        Args:
            prompt:        The user prompt to scan and send to the model.
            model:         Which model to use — ``"reasoning"`` (default) or ``"fast"``.
            system_prompt: Optional system prompt prepended to the conversation.
            **kwargs:      Extra keyword arguments forwarded to the LLM generation call.

        Returns:
            A :class:`GuardedResponse` with the scan outcomes and generated text.
        """
        if model not in _VALID_MODELS:
            raise ValueError(f"Unknown model {model!r}; expected one of {sorted(_VALID_MODELS)}")

        if not prompt or not prompt.strip():
            self.stats_blocked_input += 1
            return GuardedResponse(
                blocked=True,
                content=None,
                input_scan=GuardResult(
                    is_valid=False,
                    score=1.0,
                    details={"_error": "empty_prompt"},
                ),
                output_scan=None,
            )

        ts = datetime.now(tz=UTC).isoformat()

        # --- Step 1: Pre-scan input ---
        input_scan = await self._scan_input(prompt)

        if not input_scan.is_valid:
            self.stats_blocked_input += 1
            logger.warning(
                "guard.input.blocked | ts=%s model=%s score=%.3f scanners=%s",
                ts,
                model,
                input_scan.score,
                input_scan.details,
            )
            self._emit_audit("input_blocked", ts, model, input_scan, None)
            return GuardedResponse(
                blocked=True,
                content=None,
                input_scan=input_scan,
                output_scan=None,
            )

        logger.info(
            "guard.input.passed | ts=%s model=%s score=%.3f",
            ts,
            model,
            input_scan.score,
        )

        # --- Step 2: Generate response ---
        try:
            response_text = await self._generate(
                prompt, model=model, system_prompt=system_prompt, **kwargs
            )
        except Exception:
            self.stats_errors += 1
            logger.exception("guard._generate failed — treating as blocked")
            return GuardedResponse(
                blocked=True,
                content=None,
                input_scan=input_scan,
                output_scan=GuardResult(
                    is_valid=False,
                    score=1.0,
                    details={"_error": "generation_failed"},
                ),
            )

        # --- Step 3: Post-scan output ---
        output_scan = await self._scan_output(prompt, response_text)

        if not output_scan.is_valid:
            self.stats_blocked_output += 1
            logger.warning(
                "guard.output.blocked | ts=%s model=%s score=%.3f scanners=%s",
                ts,
                model,
                output_scan.score,
                output_scan.details,
            )
            self._emit_audit("output_blocked", ts, model, input_scan, output_scan)
            return GuardedResponse(
                blocked=True,
                content=response_text,
                input_scan=input_scan,
                output_scan=output_scan,
            )

        self.stats_passed += 1
        logger.info(
            "guard.output.passed | ts=%s model=%s input_score=%.3f output_score=%.3f",
            ts,
            model,
            input_scan.score,
            output_scan.score,
        )
        self._emit_audit("passed", ts, model, input_scan, output_scan)

        return GuardedResponse(
            blocked=False,
            content=response_text,
            input_scan=input_scan,
            output_scan=output_scan,
        )

    @staticmethod
    def _emit_audit(
        decision: str,
        ts: str,
        model: str,
        input_scan: GuardResult | None,
        output_scan: GuardResult | None,
    ) -> None:
        """Write a structured JSON audit record to the dedicated audit logger."""
        import json as _json  # noqa: PLC0415

        record = {
            "event": "guard_decision",
            "decision": decision,
            "timestamp": ts,
            "model": model,
            "input_score": input_scan.score if input_scan else None,
            "input_details": input_scan.details if input_scan else None,
            "output_score": output_scan.score if output_scan else None,
            "output_details": output_scan.details if output_scan else None,
        }
        _audit_logger.info(_json.dumps(record, default=str))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _scan_input(self, prompt: str) -> GuardResult:
        """Call the guard service ``/analyze/prompt`` endpoint."""
        try:
            raw = await self._client.guard_input(prompt)
            return _parse_guard_response(raw)
        except Exception:
            logger.exception("guard.input.error — treating as blocked for safety")
            return GuardResult(is_valid=False, score=1.0, details={"_error": "scan_failed"})

    async def _scan_output(self, prompt: str, output: str) -> GuardResult:
        """Call the guard service ``/analyze/output`` endpoint."""
        try:
            raw = await self._client.guard_output(prompt, output)
            return _parse_guard_response(raw)
        except Exception:
            logger.exception("guard.output.error — treating as blocked for safety")
            return GuardResult(is_valid=False, score=1.0, details={"_error": "scan_failed"})

    async def _generate(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str | None,
        **kwargs: Any,
    ) -> str:
        """Dispatch to the appropriate LLM generation method based on *model*.

        Converts the raw *prompt* string into the ``messages`` list format
        expected by :meth:`LLMClient.reason` / :meth:`LLMClient.fast` and
        extracts the assistant text from the chat-completion response dict.
        """
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if model == "reasoning":
            resp = await self._client.reason(messages, **kwargs)
        else:
            resp = await self._client.fast(messages, **kwargs)

        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            self.stats_errors += 1
            available_keys: list[str] = list(resp.keys())
            logger.error(
                "guard._generate: unexpected response structure (available_keys=%s)",
                available_keys,
            )
            raise ValueError(
                f"LLM response missing choices[0].message.content (keys={available_keys})"
            ) from exc
