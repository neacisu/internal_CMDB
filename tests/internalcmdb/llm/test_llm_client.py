"""Tests for the LLM Client — circuit breaker, retry, and fallback logic."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from internalcmdb.llm.client import (
    LLMClient,
    _BACKOFF_BASE,
    _CIRCUIT_BREAKER_THRESHOLD,
    _CircuitState,
    _MAX_RETRIES,
)


# ---------------------------------------------------------------------------
# CircuitState unit tests
# ---------------------------------------------------------------------------


class TestCircuitState:
    def test_initial_state(self) -> None:
        cs = _CircuitState()
        assert cs.failures == 0
        assert cs.degraded is False

    def test_record_failure_increments(self) -> None:
        cs = _CircuitState()
        cs.record_failure("test-model")
        assert cs.failures == 1
        assert cs.degraded is False

    def test_trips_at_threshold(self) -> None:
        cs = _CircuitState()
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD):
            cs.record_failure("test-model")
        assert cs.degraded is True

    def test_record_success_resets(self) -> None:
        cs = _CircuitState()
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD):
            cs.record_failure("test-model")
        cs.record_success()
        assert cs.failures == 0
        assert cs.degraded is False


# ---------------------------------------------------------------------------
# LLMClient tests with mocked httpx
# ---------------------------------------------------------------------------


class TestLLMClient:
    @pytest.fixture
    def client(self) -> LLMClient:
        return LLMClient(
            reasoning_url="http://mock-reason:49001",
            fast_url="http://mock-fast:49002",
            embed_url="http://mock-embed:49003",
            guard_url="http://mock-guard:8000",
        )

    @pytest.mark.asyncio
    async def test_reason_success(self, client: LLMClient) -> None:
        expected = {
            "choices": [{"message": {"content": "answer"}}],
            "model": "test",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = expected
        mock_resp.raise_for_status = MagicMock()

        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.reason([{"role": "user", "content": "hello"}])
        assert result["choices"][0]["message"]["content"] == "answer"
        assert client._circuits["reasoning"].failures == 0

    @pytest.mark.asyncio
    async def test_fast_success(self, client: LLMClient) -> None:
        expected = {"choices": [{"message": {"content": "fast reply"}}]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = expected
        mock_resp.raise_for_status = MagicMock()

        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.fast([{"role": "user", "content": "hi"}])
        assert result["choices"][0]["message"]["content"] == "fast reply"

    @pytest.mark.asyncio
    async def test_embed_returns_vectors(self, client: LLMClient) -> None:
        dim = 4096
        vec_a = [0.1] * dim
        vec_b = [0.2] * dim
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"embeddings": [vec_a, vec_b]}
        mock_resp.raise_for_status = MagicMock()

        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.embed(["text1", "text2"])
        assert len(result) == 2
        assert len(result[0]) == dim

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, client: LLMClient) -> None:
        error_resp = MagicMock()
        error_resp.status_code = 500
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=error_resp
        )

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        ok_resp.raise_for_status = MagicMock()

        client._client.request = AsyncMock(side_effect=[error_resp, ok_resp])

        with patch("internalcmdb.llm.client.asyncio.sleep", new_callable=AsyncMock):
            result = await client.fast([{"role": "user", "content": "test"}])
        assert result["choices"][0]["message"]["content"] == "ok"

    @pytest.mark.asyncio
    async def test_circuit_breaker_fallback_reason_to_fast(
        self, client: LLMClient
    ) -> None:
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD):
            client._circuits["reasoning"].record_failure("reasoning")
        assert client._circuits["reasoning"].degraded is True

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "fallback"}}]}
        mock_resp.raise_for_status = MagicMock()
        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.reason([{"role": "user", "content": "test"}])
        assert result["choices"][0]["message"]["content"] == "fallback"
        call_url = client._client.request.call_args[0][1]
        assert "49002" in call_url

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self, client: LLMClient) -> None:
        error_resp = MagicMock()
        error_resp.status_code = 400
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400", request=MagicMock(), response=error_resp
        )

        client._client.request = AsyncMock(return_value=error_resp)

        with pytest.raises(httpx.HTTPStatusError):
            await client.fast([{"role": "user", "content": "bad"}])
        assert client._client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self, client: LLMClient) -> None:
        error_resp = MagicMock()
        error_resp.status_code = 503
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=error_resp
        )

        client._client.request = AsyncMock(return_value=error_resp)

        with (
            patch("internalcmdb.llm.client.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await client.fast([{"role": "user", "content": "fail"}])
        assert client._client.request.call_count == _MAX_RETRIES + 1
