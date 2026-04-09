"""Shared pytest fixtures for internalcmdb tests."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from internalcmdb.models.agent_control import (  # pylint: disable=import-error
    ActionRequest,
    AgentRun,
)


async def _mock_async_tick() -> None:
    """Yield once to the running loop.

    Test doubles mirror production ``async`` APIs; a zero-delay sleep keeps
    behaviour deterministic while satisfying static analysis (no fire-and-forget
    ``async def`` without suspension points) and avoids blocking the loop when
    tests compose multiple awaitables.
    """
    await asyncio.sleep(0)


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    """Return a MagicMock that satisfies the ``Session`` interface."""
    session = MagicMock(spec=Session)
    session.add = MagicMock()
    session.flush = MagicMock()
    return session


# ---------------------------------------------------------------------------
# AgentRun stub factory
# ---------------------------------------------------------------------------


def make_agent_run(
    status: str = "pending",
    run_code: str = "RUN-TEST-001",
    agent_run_id: uuid.UUID | None = None,
) -> MagicMock:
    """Return a lightweight AgentRun mock with the attributes we mutate in tests."""
    run = MagicMock(spec=AgentRun)
    run.agent_run_id = agent_run_id or uuid.uuid4()
    run.run_code = run_code
    run.status_text = status
    run.requested_scope_jsonb = {}
    run.summary_jsonb = {}  # dict[str, Any]; inline annotation unsupported on mock attrs
    return run


# ---------------------------------------------------------------------------
# ActionRequest stub factory
# ---------------------------------------------------------------------------


def make_action_request(
    status: str = "pending",
    action_class: str = "AC-003",
    action_request_id: uuid.UUID | None = None,
    target_entity_ids: list[uuid.UUID] | None = None,
    snapshot_exists: bool = False,
    approval_record_id: uuid.UUID | None = None,
) -> MagicMock:
    """Return a lightweight ActionRequest mock."""
    req = MagicMock(spec=ActionRequest)
    req.action_request_id = action_request_id or uuid.uuid4()
    req.request_code = f"REQ-{action_class}-TEST"
    req.status_text = status
    req.action_class_text = action_class
    entity_ids = target_entity_ids or []
    req.target_scope_jsonb = {
        "entity_ids": [str(e) for e in entity_ids],
        "requested_by": "test-agent",
        "task_type_code": "TT-001",
        "snapshot_exists": snapshot_exists,
    }
    req.requested_change_jsonb = None
    req.approval_record_id = approval_record_id
    req.executed_at = None
    return req


# ---------------------------------------------------------------------------
# MockLLMClient — deterministic responses for reason/fast/embed/guard
# ---------------------------------------------------------------------------


class MockLLMClient:
    """Deterministic LLM client for tests — no network calls."""

    def __init__(self) -> None:
        self.call_log: list[dict[str, Any]] = []

    async def reason(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        await _mock_async_tick()
        self.call_log.append({"method": "reason", "messages": messages})
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Mock reasoning response."},
                    "finish_reason": "stop",
                }
            ],
            "model": "mock-reasoning",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

    async def fast(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        await _mock_async_tick()
        self.call_log.append({"method": "fast", "messages": messages})
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Mock fast response."},
                    "finish_reason": "stop",
                }
            ],
            "model": "mock-fast",
            "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
        }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        await _mock_async_tick()
        self.call_log.append({"method": "embed", "texts": texts})
        return [[0.1] * 4096 for _ in texts]

    async def guard_input(self, prompt: str) -> dict[str, Any]:
        await _mock_async_tick()
        self.call_log.append({"method": "guard_input", "prompt": prompt})
        return {"safe": True, "categories": [], "scores": {}}

    async def guard_output(self, prompt: str, output: str) -> dict[str, Any]:
        await _mock_async_tick()
        self.call_log.append({"method": "guard_output", "prompt": prompt, "output": output})
        return {"safe": True, "categories": [], "scores": {}}

    async def close(self) -> None:
        """No persistent handles — mirror production lifecycle for ``async with``."""
        await _mock_async_tick()

    async def __aenter__(self) -> MockLLMClient:
        await _mock_async_tick()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()  # includes cooperative yield + no-op shutdown


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    """Deterministic LLM client — returns canned responses for all endpoints."""
    return MockLLMClient()


class MockLLMClientFailing:
    """LLM client that raises on every call — tests error paths."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or RuntimeError("mock LLM backend unavailable")

    async def reason(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        raise self._error

    async def fast(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        raise self._error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise self._error

    async def guard_input(self, prompt: str) -> dict[str, Any]:
        raise self._error

    async def guard_output(self, prompt: str, output: str) -> dict[str, Any]:
        raise self._error

    async def close(self) -> None:
        await _mock_async_tick()

    async def __aenter__(self) -> MockLLMClientFailing:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


@pytest.fixture
def mock_llm_client_failing() -> MockLLMClientFailing:
    """LLM client that always raises — use for error-path tests."""
    return MockLLMClientFailing()


# ---------------------------------------------------------------------------
# MockGuardPipeline — always-pass mode for non-guard tests
# ---------------------------------------------------------------------------


class MockGuardPipeline:
    """Guard pipeline that always allows actions through."""

    async def evaluate(self, action: dict[str, Any], context: dict[str, Any]) -> Any:
        await _mock_async_tick()
        from dataclasses import dataclass  # noqa: PLC0415

        @dataclass(frozen=True)
        class _Decision:
            allowed: bool = True
            risk_class: str = "RC-1"
            blocked_at_level: int | None = None
            reason: str = "mock-always-pass"
            requires_hitl: bool = False

        return _Decision()


@pytest.fixture
def mock_guard_pipeline() -> MockGuardPipeline:
    """Guard pipeline that always passes — use for non-guard tests."""
    return MockGuardPipeline()


class MockGuardPipelineBlocking:
    """Guard pipeline that always blocks — use for guard-rejection tests."""

    def __init__(self, reason: str = "mock-always-block", risk_class: str = "RC-4") -> None:
        self._reason = reason
        self._risk_class = risk_class

    async def evaluate(self, action: dict[str, Any], context: dict[str, Any]) -> Any:
        await _mock_async_tick()
        from dataclasses import dataclass  # noqa: PLC0415

        @dataclass(frozen=True)
        class _Decision:
            allowed: bool = False
            risk_class: str = self._risk_class
            blocked_at_level: int | None = 5
            reason: str = self._reason
            requires_hitl: bool = True

        return _Decision()


@pytest.fixture
def mock_guard_pipeline_blocking() -> MockGuardPipelineBlocking:
    """Guard pipeline that always blocks — use for guard-rejection tests."""
    return MockGuardPipelineBlocking()


# ---------------------------------------------------------------------------
# MockEventBus — in-memory implementation
# ---------------------------------------------------------------------------


class MockEventBus:
    """In-memory event bus for tests — no Redis dependency."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []
        self._pending: dict[str, list[dict[str, Any]]] = {}
        self._acked: list[tuple[str, str, str]] = []

    async def publish(self, stream: str, event: Any) -> str:
        await _mock_async_tick()
        data = event.to_dict() if hasattr(event, "to_dict") else event
        msg_id = f"mock-{len(self.published)}"
        self.published.append((stream, data))
        self._pending.setdefault(stream, []).append({**data, "_msg_id": msg_id})
        return msg_id

    async def subscribe(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 0,
    ) -> list[Any]:
        await _mock_async_tick()
        from internalcmdb.nervous.event_bus import Event  # noqa: PLC0415

        pending = self._pending.get(stream, [])[:count]
        events: list[Any] = []
        for item in pending:
            msg_id = item.get("_msg_id", "mock-0")
            payload = {k: v for k, v in item.items() if k != "_msg_id"}
            evt = Event.from_dict(payload)
            evt.redis_message_id = msg_id
            events.append(evt)
        return events

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        await _mock_async_tick()
        self._acked.append((stream, group, message_id))
        pending = self._pending.get(stream, [])
        self._pending[stream] = [p for p in pending if p.get("_msg_id") != message_id]

    async def ensure_groups(self) -> None:
        """Redis XGROUP CREATE is a no-op for this in-memory stand-in."""
        await _mock_async_tick()

    async def close(self) -> None:
        """No connections — included for API parity with :class:`EventBus`."""
        await _mock_async_tick()


@pytest.fixture
def mock_event_bus() -> MockEventBus:
    """In-memory event bus — no Redis required."""
    return MockEventBus()


# ---------------------------------------------------------------------------
# Auth / Redis mocks — isolate revocation and lockout from live Redis
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_revocation():
    """Stub out Redis for token revocation — always returns not-revoked (fail-open)."""
    revocation_client = MagicMock()
    revocation_client.setex = MagicMock(return_value=True)
    revocation_client.exists = MagicMock(return_value=0)  # Redis: falsy means not revoked

    with patch("internalcmdb.auth.revocation._get_redis_client", return_value=revocation_client):
        yield revocation_client


@pytest.fixture
def mock_redis_lockout():
    """Stub out Redis for brute-force lockout — always returns not-locked (fail-open)."""
    lockout_client = MagicMock()
    lockout_client.get = MagicMock(return_value=None)  # None = no lockout entry
    lockout_client.incr = MagicMock(return_value=1)
    lockout_client.expire = MagicMock(return_value=True)
    lockout_client.delete = MagicMock(return_value=1)

    with patch("internalcmdb.auth.lockout._get_redis_client", return_value=lockout_client):
        yield lockout_client


@pytest.fixture
def auth_admin_user():
    """Return a minimal admin User ORM mock for auth dependency tests."""
    user = MagicMock()
    user.user_id = uuid.uuid4()
    user.email = "admin@example.com"
    user.username = "admin"
    user.role = "admin"
    user.is_active = True
    user.force_password_change = False
    return user
