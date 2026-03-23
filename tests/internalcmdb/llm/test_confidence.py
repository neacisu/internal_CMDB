"""Teste stricte pentru calibrarea încrederii (CoVe) și parsere defensive.

Acoperă contracte stdlib (ierarhia JSONDecodeError), căi de eroare reale
în răspunsuri LLM malformate și pipeline-ul async ``calibrated_call``.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from internalcmdb.llm.confidence import (
    CONFIDENCE_THRESHOLDS,
    CalibratedResponse,
    ConfidenceCalibrator,
    _detect_domain,
)

# ---------------------------------------------------------------------------
# Contract stdlib — baza pentru except (S5713) și parsare JSON
# ---------------------------------------------------------------------------


def test_jsondecodeerror_subclasses_valueerror() -> None:
    """``JSONDecodeError`` trebuie să rămână subclasă a ``ValueError`` (CPython)."""
    assert issubclass(json.JSONDecodeError, ValueError)


def test_confidence_thresholds_are_valid_probabilities() -> None:
    """Pragurile sunt în (0, 1] — invariant pentru comparații cu ``confidence``."""
    assert CONFIDENCE_THRESHOLDS.keys() >= {
        "infrastructure",
        "security",
        "capacity",
        "reports",
        "general",
    }
    for name, thr in CONFIDENCE_THRESHOLDS.items():
        assert isinstance(thr, float), name
        assert 0.0 < thr <= 1.0, name


# ---------------------------------------------------------------------------
# _detect_domain
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Disk usage on prod server?", "infrastructure"),
        ("Check TLS certificate and CVE-2024", "security"),
        ("Scaling quota utilization trend", "capacity"),
        ("Fleet audit summary overview", "reports"),
        ("What is the weather?", "general"),
        ("HOST and MEMORY pressure", "infrastructure"),
    ],
)
def test_detect_domain_keyword_routing(prompt: str, expected: str) -> None:
    assert _detect_domain(prompt) == expected


def test_detect_domain_case_insensitive() -> None:
    assert _detect_domain("DISK and SERVER down") == "infrastructure"


def test_detect_domain_empty_string_is_general() -> None:
    assert _detect_domain("") == "general"


# ---------------------------------------------------------------------------
# CalibratedResponse
# ---------------------------------------------------------------------------


def test_calibrated_response_defaults() -> None:
    r = CalibratedResponse(content="x", confidence=0.9)
    assert r.verification_steps == []
    assert r.is_verified is False
    assert r.domain == "general"
    assert r.threshold == pytest.approx(0.75)
    assert r.requires_hitl is False
    assert r.raw_draft == ""
    assert r.tokens_used == 0


# ---------------------------------------------------------------------------
# Helpers statice — _extract_content, _count_tokens
# ---------------------------------------------------------------------------


class TestExtractContent:
    def test_openai_shape_returns_assistant_content(self) -> None:
        resp = {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        }
        assert ConfidenceCalibrator._extract_content(resp) == "ok"

    def test_missing_choices_returns_stringified_response(self) -> None:
        resp: dict[str, Any] = {"model": "x"}
        assert ConfidenceCalibrator._extract_content(resp) == str(resp)

    def test_empty_choices_indexerror_fallback(self) -> None:
        resp: dict[str, Any] = {"choices": []}
        out = ConfidenceCalibrator._extract_content(resp)
        assert out == str(resp)

    def test_missing_message_key_fallback(self) -> None:
        resp: dict[str, Any] = {"choices": [{}]}
        assert ConfidenceCalibrator._extract_content(resp) == str(resp)


class TestCountTokens:
    def test_total_tokens_present(self) -> None:
        resp = {"usage": {"total_tokens": 42}}
        assert ConfidenceCalibrator._count_tokens(resp) == 42

    def test_missing_usage_defaults_zero(self) -> None:
        assert ConfidenceCalibrator._count_tokens({}) == 0

    def test_usage_null_triggers_defensive_zero(self) -> None:
        """``usage`` explicit ``None`` — fără ``.get`` pe non-dict."""
        assert ConfidenceCalibrator._count_tokens({"usage": None}) == 0


# ---------------------------------------------------------------------------
# _parse_confidence — strict
# ---------------------------------------------------------------------------


class TestParseConfidence:
    def test_json_object_with_confidence(self) -> None:
        assert ConfidenceCalibrator._parse_confidence('{"confidence": 0.82}') == pytest.approx(0.82)

    def test_missing_confidence_key_defaults_half(self) -> None:
        assert ConfidenceCalibrator._parse_confidence("{}") == pytest.approx(0.5)

    def test_confidence_as_json_string(self) -> None:
        assert ConfidenceCalibrator._parse_confidence('{"confidence": "0.91"}') == pytest.approx(
            0.91
        )

    def test_invalid_json_falls_back_regex_decimal(self) -> None:
        assert ConfidenceCalibrator._parse_confidence("model says 0.73 here") == pytest.approx(
            0.73
        )

    def test_percent_style_greater_than_one_scaled(self) -> None:
        """Valori > 1.0 din regex sunt tratate ca procent (ex. 95 → 0.95)."""
        assert ConfidenceCalibrator._parse_confidence("confidence 95 percent") == pytest.approx(
            0.95
        )

    def test_json_scalar_float_is_confidence(self) -> None:
        """JSON scalar (ex. ``1.0``) — răspuns LLM valid, nu obiect cu cheie."""
        assert ConfidenceCalibrator._parse_confidence("1.0") == pytest.approx(1.0)

    def test_json_scalar_integer_percent_normalized(self) -> None:
        assert ConfidenceCalibrator._parse_confidence("95") == pytest.approx(0.95)

    def test_json_bool_falls_back_to_regex_or_default(self) -> None:
        """``true``/``false`` nu sunt scară 0-1; după JSON valid folosim regex / default."""
        assert ConfidenceCalibrator._parse_confidence("true") == pytest.approx(0.5)

    def test_no_digits_returns_default(self) -> None:
        assert ConfidenceCalibrator._parse_confidence("no numbers at all") == pytest.approx(0.5)

    def test_typeerror_from_float_nested_triggers_fallback(self) -> None:
        """``float`` pe tip necompatibil → TypeError → ramură regex / default."""
        raw = '{"confidence": [0.1]}'
        # Primul grup de cifre din text (din listă sau chei) — trebuie să fie determinist.
        out = ConfidenceCalibrator._parse_confidence(raw)
        assert isinstance(out, float)
        assert 0.0 <= out <= 1.0

    def test_jsondecodeerror_is_valueerror_subclass_handled(self) -> None:
        """Invalid JSON → JSONDecodeError (ValueError); trebuie să ajungă la fallback."""
        out = ConfidenceCalibrator._parse_confidence("{not json")
        assert out == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# _parse_questions — strict
# ---------------------------------------------------------------------------


class TestParseQuestions:
    def test_json_array_of_strings(self) -> None:
        assert ConfidenceCalibrator._parse_questions('["Is disk full?", "Is CPU high?"]') == [
            "Is disk full?",
            "Is CPU high?",
        ]

    def test_json_array_non_string_coerced(self) -> None:
        assert ConfidenceCalibrator._parse_questions("[1, 2]") == ["1", "2"]

    def test_json_non_list_falls_through_to_line_parser(self) -> None:
        """Obiect JSON valid dar non-listă: nu returnăm din try; parsăm linii din textul brut."""
        raw = '{"not": "a list"}'
        assert ConfidenceCalibrator._parse_questions(raw) == []

    def test_json_scalar_falls_through(self) -> None:
        assert ConfidenceCalibrator._parse_questions("42") == []

    def test_invalid_json_then_markdown_lines(self) -> None:
        text = "- Is the host reachable?\n• Does TLS verify?\nnot a question"
        out = ConfidenceCalibrator._parse_questions(text)
        assert out == ["Is the host reachable?", "Does TLS verify?"]

    def test_strip_and_empty_lines(self) -> None:
        text = "\n\n  What is uptime?  \n\n"
        assert ConfidenceCalibrator._parse_questions(text) == ["What is uptime?"]

    def test_empty_json_list(self) -> None:
        assert ConfidenceCalibrator._parse_questions("[]") == []


# ---------------------------------------------------------------------------
# Message builders — structură și conținut obligatoriu
# ---------------------------------------------------------------------------


class TestMessageBuilders:
    def test_build_draft_includes_context_when_provided(self) -> None:
        msgs = ConfidenceCalibrator._build_draft_messages("Q?", "CTX")
        assert msgs[0]["role"] == "system"
        assert "CTX" in msgs[1]["content"]
        assert "Q?" in msgs[1]["content"]

    def test_build_eval_contains_domain_and_json_instruction(self) -> None:
        msgs = ConfidenceCalibrator._build_eval_messages("P", "D", "security")
        assert "security" in msgs[0]["content"]
        assert "confidence" in msgs[0]["content"].lower()

    def test_build_verification_question_messages(self) -> None:
        msgs = ConfidenceCalibrator._build_verification_question_messages("P", "D")
        assert "JSON array" in msgs[0]["content"] or "json" in msgs[0]["content"].lower()
        user = msgs[1]["content"]
        assert "P" in user
        assert "D" in user

    def test_build_independent_answer_with_and_without_context(self) -> None:
        with_ctx = ConfidenceCalibrator._build_independent_answer_messages("Q?", "C")
        assert with_ctx[1]["content"].startswith("C")
        no_ctx = ConfidenceCalibrator._build_independent_answer_messages("Q?", "")
        assert no_ctx[1]["content"] == "Q?"

    def test_build_synthesis_includes_verification_bullets(self) -> None:
        steps = ["Q: a → A: b"]
        msgs = ConfidenceCalibrator._build_synthesis_messages("P", "D", steps)
        assert "Q: a" in msgs[1]["content"]


# ---------------------------------------------------------------------------
# Mock LLM cu coadă deterministă pentru integrare async
# ---------------------------------------------------------------------------


class _QueuedLLMClient:
    """Returnează răspunsuri în ordine; înregistrează apelurile.

    Un element din coadă poate fi un ``dict`` (răspuns API) sau o excepție
    de propagat — pentru simulare erori upstream pe un apel anume.
    """

    def __init__(self, queue: list[dict[str, Any] | BaseException]) -> None:
        self._queue = list(queue)
        self.calls: list[tuple[str, list[dict[str, Any]]]] = []

    def _pop_next(self) -> dict[str, Any]:
        if not self._queue:
            msg = "QueuedLLMClient: empty queue"
            raise RuntimeError(msg)
        item = self._queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def reason(self, messages: list[dict[str, Any]], **_kw: Any) -> dict[str, Any]:
        await asyncio.sleep(0)
        self.calls.append(("reason", messages))
        return self._pop_next()

    async def fast(self, messages: list[dict[str, Any]], **_kw: Any) -> dict[str, Any]:
        await asyncio.sleep(0)
        self.calls.append(("fast", messages))
        return self._pop_next()


def _choice(content: str, tokens: int = 10) -> dict[str, Any]:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"total_tokens": tokens},
    }


# ---------------------------------------------------------------------------
# _call_llm și calibrated_call — integrare
# ---------------------------------------------------------------------------


class TestCallLLMBranching:
    def test_fast_model_uses_fast_method(self) -> None:
        async def _run() -> None:
            client = _QueuedLLMClient([_choice("ok", 5)])
            cal = ConfidenceCalibrator(client)
            out = await cal._call_llm([], "fast")
            assert out["choices"][0]["message"]["content"] == "ok"
            assert client.calls[0][0] == "fast"

        asyncio.run(_run())

    def test_non_fast_uses_reason(self) -> None:
        async def _run() -> None:
            client = _QueuedLLMClient([_choice("r", 7)])
            cal = ConfidenceCalibrator(client)
            out = await cal._call_llm([], "reasoning")
            assert out["choices"][0]["message"]["content"] == "r"
            assert client.calls[0][0] == "reason"

        asyncio.run(_run())


class TestCalibratedCallIntegration:
    def test_draft_failure_returns_hitl_and_zero_confidence(self) -> None:
        async def _run() -> None:
            broken = AsyncMock()
            broken.reason = AsyncMock(side_effect=RuntimeError("upstream"))

            cal = ConfidenceCalibrator(broken)
            result = await cal.calibrated_call("disk on server", model="reasoning")

            assert "Draft generation failed" in result.content
            assert result.confidence == pytest.approx(0.0)
            assert result.requires_hitl is True
            assert result.domain == "infrastructure"

        asyncio.run(_run())

    def test_high_initial_confidence_skips_verification(self) -> None:
        async def _run() -> None:
            eval_json = json.dumps({"confidence": 0.97, "reasoning": "sure"})
            client = _QueuedLLMClient(
                [
                    _choice("draft answer", 100),
                    _choice(eval_json, 50),
                ]
            )
            cal = ConfidenceCalibrator(client)
            result = await cal.calibrated_call("report summary", model="reasoning")

            assert result.content == "draft answer"
            assert result.confidence == pytest.approx(0.97)
            assert result.is_verified is True
            assert "skipped" in result.verification_steps[0].lower()
            assert result.tokens_used == 150
            assert len(client.calls) == 2

        asyncio.run(_run())

    def test_full_pipeline_low_confidence_runs_verification_and_synthesis(self) -> None:
        async def _run() -> None:
            vq_json = json.dumps(["Verify disk?", "Verify service?"])
            synth = "synthesised final"
            client = _QueuedLLMClient(
                [
                    _choice("draft body", 10),
                    _choice('{"confidence": 0.5}', 10),
                    _choice(vq_json, 10),
                    _choice("ans disk", 5),
                    _choice("ans svc", 5),
                    _choice(synth, 20),
                ]
            )
            cal = ConfidenceCalibrator(client)
            result = await cal.calibrated_call("disk and service health", model="reasoning")

            assert result.content == synth
            assert len(result.verification_steps) == 2
            assert all("Q:" in s and "→ A:" in s for s in result.verification_steps)
            assert result.is_verified is True
            assert result.tokens_used == 60
            # infrastructură → prag 0.85; conf finală 0.5 + 0.2 = 0.7 < 0.85
            assert result.requires_hitl is True
            assert result.threshold == pytest.approx(CONFIDENCE_THRESHOLDS["infrastructure"])

        asyncio.run(_run())

    def test_eval_exception_yields_default_confidence_then_continues(self) -> None:
        """Eval LLM eșuează → ``initial_confidence`` 0.5; pipeline continuă."""

        async def _run() -> None:
            client = _QueuedLLMClient(
                [
                    _choice("draft", 1),
                    RuntimeError("eval down"),
                    _choice("[]", 1),
                    _choice("synth-after-eval-fail", 2),
                ]
            )
            cal = ConfidenceCalibrator(client)
            result = await cal.calibrated_call("hello", model="reasoning")
            assert result.confidence == pytest.approx(0.5)
            assert result.content == "synth-after-eval-fail"
            assert result.raw_draft == "draft"

        asyncio.run(_run())

    def test_verification_question_step_records_failure_string(self) -> None:
        async def _run() -> None:
            vq_json = json.dumps(["Only one question?"])
            client = _QueuedLLMClient(
                [
                    _choice("d", 1),
                    _choice('{"confidence": 0.1}', 1),
                    _choice(vq_json, 1),
                    OSError("network"),
                    _choice("final synth", 3),
                ]
            )
            cal = ConfidenceCalibrator(client)
            result = await cal.calibrated_call("x", model="reasoning")
            assert len(result.verification_steps) == 1
            assert "verification failed" in result.verification_steps[0]
            assert result.content == "final synth"

        asyncio.run(_run())

    def test_synthesis_failure_falls_back_to_draft(self) -> None:
        async def _run() -> None:
            client = _QueuedLLMClient(
                [
                    _choice("draftX", 1),
                    _choice('{"confidence": 0.5}', 1),
                    _choice("[]", 1),
                    RuntimeError("synth upstream"),
                ]
            )
            cal = ConfidenceCalibrator(client)
            result = await cal.calibrated_call("hello", model="reasoning")
            assert result.content == "draftX"
            assert result.raw_draft == "draftX"

        asyncio.run(_run())

    def test_verification_questions_fetch_failure_uses_empty_list(self) -> None:
        """Eșec la pasul de întrebări → ``[]``; sinteză tot rulează."""

        async def _run() -> None:
            client = _QueuedLLMClient(
                [
                    _choice("draftY", 1),
                    _choice('{"confidence": 0.5}', 1),
                    RuntimeError("vq fail"),
                    _choice("synth only", 1),
                ]
            )
            cal = ConfidenceCalibrator(client)
            result = await cal.calibrated_call("hello", model="reasoning")
            assert result.verification_steps == []
            assert result.is_verified is False
            assert result.content == "synth only"

        asyncio.run(_run())
