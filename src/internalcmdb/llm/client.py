"""LLM Client — unified async interface to self-hosted model backends.

Backends (HAProxy VIP 10.0.1.10):
    * reasoning  — vLLM  QwQ-32B-AWQ          :49001
    * fast       — vLLM  Qwen2.5-14B-AWQ      :49002
    * embed      — Ollama Qwen3-Embedding-8B   :49003
    * guard      — LLM Guard (orchestrator)    :8000

API formats follow LLM-005 Portable Model Registry.

Advanced features:
    * ``guided_json``  — structured output via vLLM's guided decoding
    * ``tool_call``    — OpenAI-compatible tool/function calling
    * Schema validation on structured responses
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    """Per-model connection descriptor."""

    name: str
    endpoint_url: str
    timeout: float
    model_id: str


# ---------------------------------------------------------------------------
# Circuit-breaker state (per-model)
# ---------------------------------------------------------------------------

_CIRCUIT_BREAKER_THRESHOLD = 5
_CIRCUIT_BREAKER_COOLDOWN = 60.0  # seconds before half-open probe
_EXPECTED_EMBED_DIM = 4096


class _CircuitState:
    """Track consecutive failures and degraded flag for a single backend.

    Implements a three-state circuit breaker: closed → open → half-open.
    After *_CIRCUIT_BREAKER_COOLDOWN* seconds the circuit enters half-open:
    the next request is allowed through as a probe.  A success closes it;
    a failure re-opens it.
    """

    __slots__ = ("degraded", "failures", "last_failure_ts")

    def __init__(self) -> None:
        self.failures: int = 0
        self.degraded: bool = False
        self.last_failure_ts: float = 0.0

    @property
    def should_allow_probe(self) -> bool:
        """True when enough cooldown has elapsed for a half-open probe."""
        if not self.degraded:
            return True
        return (time.monotonic() - self.last_failure_ts) >= _CIRCUIT_BREAKER_COOLDOWN

    def record_failure(self, model_name: str) -> None:
        self.failures += 1
        self.last_failure_ts = time.monotonic()
        if self.failures >= _CIRCUIT_BREAKER_THRESHOLD and not self.degraded:
            self.degraded = True
            logger.warning(
                "Model %s marked DEGRADED after %d consecutive failures",
                model_name,
                self.failures,
            )

    def record_success(self) -> None:
        if self.degraded:
            logger.info("Circuit breaker CLOSED — backend recovered")
        self.failures = 0
        self.degraded = False


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

_REASONING_TIMEOUT = 120.0
_FAST_TIMEOUT = 60.0
_EMBED_TIMEOUT = 30.0
_GUARD_TIMEOUT = 15.0

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # 1 s → 2 s → 4 s
_HTTP_SERVER_ERROR = 500


class LLMClient:
    """Async client for the four self-hosted LLM backends.

    Features:
        * Connection pooling via ``httpx.AsyncClient``
        * Retry with exponential back-off (1 s / 2 s / 4 s, max 3 retries)
        * Per-model circuit breaker (degraded after 5 consecutive failures)
        * Automatic fallback: reasoning → fast when reasoning is degraded
    """

    def __init__(
        self,
        reasoning_url: str = "http://10.0.1.10:49001",
        fast_url: str = "http://10.0.1.10:49002",
        embed_url: str = "http://10.0.1.10:49003",
        guard_url: str = "http://127.0.0.1:8000",
        *,
        guard_token: str = "",
    ) -> None:
        self.models: dict[str, ModelConfig] = {
            "reasoning": ModelConfig(
                name="reasoning",
                endpoint_url=reasoning_url,
                timeout=_REASONING_TIMEOUT,
                model_id="Qwen/QwQ-32B-AWQ",
            ),
            "fast": ModelConfig(
                name="fast",
                endpoint_url=fast_url,
                timeout=_FAST_TIMEOUT,
                model_id="Qwen/Qwen2.5-14B-Instruct-AWQ",
            ),
            "embed": ModelConfig(
                name="embed",
                endpoint_url=embed_url,
                timeout=_EMBED_TIMEOUT,
                model_id="qwen3-embedding-8b-q5km",
            ),
            "guard": ModelConfig(
                name="guard",
                endpoint_url=guard_url,
                timeout=_GUARD_TIMEOUT,
                model_id="llm-guard",
            ),
        }

        self._guard_token = guard_token
        self._circuits: dict[str, _CircuitState] = {
            name: _CircuitState() for name in self.models
        }

        self._client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
            follow_redirects=True,
        )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> LLMClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def reason(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Chat completion against the *reasoning* model (QwQ-32B).

        Falls back to the *fast* model when reasoning is degraded,
        unless the cooldown has elapsed (half-open probe).
        """
        circuit = self._circuits["reasoning"]
        if circuit.degraded and not circuit.should_allow_probe:
            logger.warning(
                "Reasoning model degraded — falling back to fast model",
            )
            return await self.fast(messages, **kwargs)

        if circuit.degraded:
            logger.info("Reasoning circuit half-open — sending probe request")

        cfg = self.models["reasoning"]
        body: dict[str, Any] = {
            "model": cfg.model_id,
            "messages": messages,
            **kwargs,
        }
        url = f"{cfg.endpoint_url}/v1/chat/completions"
        logger.info("Reasoning request → %s", url)
        return await self._request_with_retry("POST", url, "reasoning", json_body=body)

    async def fast(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Chat completion against the *fast* model (Qwen2.5-14B)."""
        cfg = self.models["fast"]
        body: dict[str, Any] = {
            "model": cfg.model_id,
            "messages": messages,
            **kwargs,
        }
        url = f"{cfg.endpoint_url}/v1/chat/completions"
        logger.info("Fast request → %s", url)
        return await self._request_with_retry("POST", url, "fast", json_body=body)

    async def reason_structured(
        self,
        messages: list[dict[str, Any]],
        json_schema: dict[str, Any],
        *,
        model_name: str = "reasoning",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Chat completion with ``guided_json`` structured output.

        Uses vLLM's ``guided_json`` parameter to constrain output to the
        provided JSON schema.  Falls back to free-form + manual parsing
        if the backend rejects the schema.

        Args:
            messages: Chat messages.
            json_schema: JSON Schema dict constraining the output.
            model_name: Which model backend to use (``reasoning`` or ``fast``).
            **kwargs: Additional API parameters.

        Returns:
            Parsed and validated response dict.

        Raises:
            ValueError: If response doesn't conform to schema after fallback.
        """
        cfg = self.models.get(model_name)
        if cfg is None:
            cfg = self.models["reasoning"]
            model_name = "reasoning"

        body: dict[str, Any] = {
            "model": cfg.model_id,
            "messages": messages,
            "guided_json": json_schema,
            **kwargs,
        }
        url = f"{cfg.endpoint_url}/v1/chat/completions"
        logger.info("Structured request (guided_json) → %s", url)

        try:
            raw = await self._request_with_retry("POST", url, model_name, json_body=body)
            content = self._extract_response_content(raw)
            parsed = self._validate_json_response(content, json_schema)
            raw["_parsed"] = parsed
            return raw
        except (httpx.HTTPStatusError, ValueError) as exc:
            logger.warning(
                "guided_json failed (%s), retrying as free-form with JSON instruction",
                exc,
            )

        body.pop("guided_json", None)
        schema_instruction = (
            f"\n\nRespond with ONLY valid JSON matching this schema:\n"
            f"```json\n{json.dumps(json_schema, indent=2)}\n```"
        )
        if messages:
            last_msg = messages[-1].copy()
            last_msg["content"] = last_msg.get("content", "") + schema_instruction
            body["messages"] = messages[:-1] + [last_msg]

        raw = await self._request_with_retry("POST", url, model_name, json_body=body)
        content = self._extract_response_content(raw)
        parsed = self._validate_json_response(content, json_schema)
        raw["_parsed"] = parsed
        return raw

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model_name: str = "reasoning",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """OpenAI-compatible tool/function calling.

        Args:
            messages: Chat messages.
            tools: Tool definitions in OpenAI function-calling format.
            model_name: Backend model to use.
            **kwargs: Additional API parameters.

        Returns:
            Raw API response including tool_calls in choices.

        Raises:
            ValueError: If no valid tool calls are returned.
        """
        cfg = self.models.get(model_name)
        if cfg is None:
            cfg = self.models["reasoning"]
            model_name = "reasoning"

        body: dict[str, Any] = {
            "model": cfg.model_id,
            "messages": messages,
            "tools": tools,
            **kwargs,
        }
        url = f"{cfg.endpoint_url}/v1/chat/completions"
        logger.info("Tool call request → %s (%d tools)", url, len(tools))

        raw = await self._request_with_retry("POST", url, model_name, json_body=body)

        choices = raw.get("choices", [])
        if not choices:
            raise ValueError("Tool call returned empty choices")

        first_choice = choices[0]
        msg = first_choice.get("message", {})
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                args = tc.get("function", {}).get("arguments")
                if isinstance(args, str):
                    try:
                        tc["function"]["arguments"] = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning("Could not parse tool call arguments as JSON")

        return raw

    @staticmethod
    def _extract_response_content(response: dict[str, Any]) -> str:
        """Extract text content from a chat completion response."""
        choices = response.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")

    @staticmethod
    def _validate_json_response(
        content: str, schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse and validate JSON content against the expected schema.

        Performs basic structural validation (required keys) without
        a full jsonschema dependency.
        """
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            content = "\n".join(lines).strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Response is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")

        required = schema.get("required", [])
        missing = [k for k in required if k not in parsed]
        if missing:
            raise ValueError(f"Missing required keys: {missing}")

        return parsed

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via the Ollama ``/api/embed`` endpoint.

        Returns a list of 4096-dimensional vectors (one per input text).
        Raises ``ValueError`` if the returned dimension does not match
        the expected 4096.
        """
        if not texts:
            return []

        cfg = self.models["embed"]
        body: dict[str, Any] = {
            "model": cfg.model_id,
            "input": texts,
        }
        url = f"{cfg.endpoint_url}/api/embed"
        logger.info("Embed request → %s (%d texts)", url, len(texts))
        resp = await self._request_with_retry("POST", url, "embed", json_body=body)
        embeddings: list[list[float]] = resp.get("embeddings", [])

        if embeddings:
            dim = len(embeddings[0])
            if dim != _EXPECTED_EMBED_DIM:
                raise ValueError(
                    f"Embedding dimension mismatch: got {dim}, "
                    f"expected {_EXPECTED_EMBED_DIM}"
                )

        return embeddings

    async def tokenize(self, text: str, model: str = "") -> dict[str, Any]:
        """Tokenize *text* via the vLLM ``/tokenize`` root endpoint.

        *model* defaults to the reasoning model ID.  Pass the fast model's
        ``model_id`` to tokenize against the 14B vocabulary.
        """
        if model == self.models["fast"].model_id:
            cfg = self.models["fast"]
            backend = "fast"
        else:
            cfg = self.models["reasoning"]
            backend = "reasoning"
            if not model:
                model = cfg.model_id

        body: dict[str, Any] = {"model": model, "prompt": text}
        url = f"{cfg.endpoint_url}/tokenize"
        logger.info("Tokenize request → %s", url)
        return await self._request_with_retry("POST", url, backend, json_body=body)

    async def guard_input(self, prompt: str) -> dict[str, Any]:
        """Scan a user prompt for injections, PII, toxicity."""
        self._warn_missing_guard_token()
        cfg = self.models["guard"]
        body: dict[str, Any] = {"prompt": prompt}
        url = f"{cfg.endpoint_url}/analyze/prompt"
        logger.info("Guard input scan → %s", url)
        return await self._request_with_retry(
            "POST", url, "guard", json_body=body, headers=self._guard_headers(),
        )

    async def guard_output(self, prompt: str, output: str) -> dict[str, Any]:
        """Scan model output for sensitive data, toxicity, relevance."""
        self._warn_missing_guard_token()
        cfg = self.models["guard"]
        body: dict[str, Any] = {"prompt": prompt, "output": output}
        url = f"{cfg.endpoint_url}/analyze/output"
        logger.info("Guard output scan → %s", url)
        return await self._request_with_retry(
            "POST", url, "guard", json_body=body, headers=self._guard_headers(),
        )

    async def health_check(self, model_name: str = "") -> dict[str, bool]:
        """Probe one or all backends and return their reachability.

        Returns a dict mapping model name to ``True``/``False``.
        """
        targets = [model_name] if model_name else list(self.models)
        results: dict[str, bool] = {}
        for name in targets:
            cfg = self.models.get(name)
            if cfg is None:
                results[name] = False
                continue
            if name == "guard":
                url = f"{cfg.endpoint_url}/healthz"
            elif name == "embed":
                url = f"{cfg.endpoint_url}/api/version"
            else:
                url = f"{cfg.endpoint_url}/health"
            try:
                resp = await self._client.get(url, timeout=5.0)
                results[name] = resp.status_code < 400
            except httpx.RequestError:
                results[name] = False
        return results

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying connection pool."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    _guard_token_warned: bool = False

    def _guard_headers(self) -> dict[str, str] | None:
        if self._guard_token:
            return {"Authorization": f"Bearer {self._guard_token}"}
        return None

    def _warn_missing_guard_token(self) -> None:
        if not self._guard_token and not self._guard_token_warned:
            logger.warning(
                "guard_token is empty — guard requests will likely "
                "fail with 401 Unauthorized"
            )
            self.__class__._guard_token_warned = True

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        model_name: str,
        *,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request with retry, back-off, and circuit-breaker."""
        circuit = self._circuits[model_name]
        effective_timeout = self.models[model_name].timeout
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                result = await self._single_request(
                    method, url, model_name, json_body, headers,
                    effective_timeout, circuit,
                )
                return result
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < _HTTP_SERVER_ERROR:
                    raise
                last_exc = exc
            except httpx.RequestError as exc:
                last_exc = exc

            circuit.record_failure(model_name)
            self._record_prometheus(
                model_name, url, 0.0, {}, f"error:{type(last_exc).__name__}",
            )
            self._log_retry(model_name, attempt, last_exc)  # type: ignore[arg-type]
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_BACKOFF_BASE * (2**attempt))

        assert last_exc is not None
        raise last_exc

    async def _single_request(
        self,
        method: str,
        url: str,
        model_name: str,
        json_body: dict[str, Any] | None,
        headers: dict[str, str] | None,
        effective_timeout: float,
        circuit: _CircuitState,
    ) -> dict[str, Any]:
        """Execute one HTTP round-trip and decode the JSON response."""
        t0 = time.monotonic()
        resp = await self._client.request(
            method, url, json=json_body, timeout=effective_timeout, headers=headers,
        )
        resp.raise_for_status()
        elapsed = time.monotonic() - t0
        circuit.record_success()
        try:
            result: dict[str, Any] = resp.json()
        except ValueError as exc:
            raise httpx.DecodingError(
                f"Invalid JSON from {model_name}: {exc}"
            ) from exc
        self._record_otel_span(model_name, result)
        self._record_prometheus(model_name, url, elapsed, result, "ok")
        return result

    @staticmethod
    def _record_otel_span(model_name: str, result: dict[str, Any]) -> None:
        """Attach GenAI span attributes to the current OTel span (if active)."""
        try:
            from opentelemetry import trace

            from internalcmdb.observability.tracing import (
                record_llm_span_attributes,
            )

            span = trace.get_current_span()
            if span is None or not span.is_recording():
                return
            usage = result.get("usage", {})
            choices = result.get("choices", [])
            finish = [c.get("finish_reason", "") for c in choices if isinstance(c, dict)]
            record_llm_span_attributes(
                span,
                model=result.get("model", model_name),
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                finish_reasons=finish or None,
            )
        except Exception:
            pass

    @staticmethod
    def _record_prometheus(
        model_name: str, url: str, elapsed: float,
        result: dict[str, Any], status: str,
    ) -> None:
        """Record LLM call duration and token counts to Prometheus metrics."""
        try:
            from internalcmdb.observability.metrics import (
                LLM_CALL_DURATION,
                LLM_TOKENS_TOTAL,
            )

            LLM_CALL_DURATION.labels(
                model=model_name, endpoint=url, status=status,
            ).observe(elapsed)

            usage = result.get("usage", {})
            in_tok = usage.get("prompt_tokens", 0)
            out_tok = usage.get("completion_tokens", 0)
            if in_tok:
                LLM_TOKENS_TOTAL.labels(model=model_name, direction="input").inc(in_tok)
            if out_tok:
                LLM_TOKENS_TOTAL.labels(model=model_name, direction="output").inc(out_tok)
        except Exception:
            pass

    @staticmethod
    def _log_retry(model_name: str, attempt: int, exc: Exception) -> None:
        if attempt < _MAX_RETRIES:
            delay = _BACKOFF_BASE * (2**attempt)
            logger.warning(
                "%s request attempt %d/%d failed, retrying in %.1fs — %s",
                model_name,
                attempt + 1,
                _MAX_RETRIES + 1,
                delay,
                exc,
            )
        else:
            logger.error(
                "%s request failed after %d attempts — %s",
                model_name,
                _MAX_RETRIES + 1,
                exc,
            )
