"""Tests for the agent_commands router.

Endpoints:
    POST /{agent_id}/commands                        — send_command
    GET  /{agent_id}/commands/{command_id}           — get_command_result
    GET  /{agent_id}/commands                        — list_commands
    GET  /{agent_id}/commands/{command_id}/stream    — stream_command_result
    POST /{agent_id}/commands/{command_id}/result    — receive_command_result
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.middleware.rate_limit import rate_limit as _rate_limit
from internalcmdb.api.routers.agent_commands import (
    CommandRequest,
    _sign_command,
    _validate_command,
)
from internalcmdb.api.routers.agent_commands import (
    router as agent_commands_router,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _Row:
    """Lightweight dict-like row mapping for mock DB results."""

    def __init__(self, **kwargs: Any) -> None:
        self._data = kwargs

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


def _result_one(row: _Row | None = None) -> MagicMock:
    """Mock execute result for .mappings().first() and .first() access patterns."""
    result = MagicMock()
    mappings_mock = MagicMock()
    mappings_mock.first.return_value = row
    result.mappings.return_value = mappings_mock
    result.first.return_value = row
    return result


def _result_many(rows: list[_Row]) -> MagicMock:
    """Mock execute result for iteration over .mappings()."""
    result = MagicMock()
    mappings_mock = MagicMock()
    mappings_mock.__iter__ = lambda self: iter(rows)
    result.mappings.return_value = mappings_mock
    return result


def _make_session(*execute_results: Any) -> Any:
    """Return an async-generator factory suitable for get_async_session override."""

    async def _factory() -> AsyncGenerator[MagicMock]:
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=list(execute_results))
        session.commit = AsyncMock()
        yield session

    return _factory


async def _empty_session() -> AsyncGenerator[MagicMock]:
    """Async session mock that never reaches db.execute (for validation-only tests)."""
    session = AsyncMock()
    yield session


def _make_app(session_factory: Any = None) -> FastAPI:
    """Build a minimal FastAPI app with the agent_commands router and mocked deps."""
    app = FastAPI()
    app.dependency_overrides[get_async_session] = session_factory or _empty_session
    # Bypass rate-limiting in unit tests — it requires app.state.limiter to be configured.
    app.dependency_overrides[_rate_limit] = lambda: None
    app.include_router(agent_commands_router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# _validate_command — pure unit tests (no HTTP round-trip)
# ---------------------------------------------------------------------------


def test_validate_command_rejects_unknown_type() -> None:
    cmd = CommandRequest(command_type="rm_rf", payload={})
    with pytest.raises(HTTPException) as exc_info:
        _validate_command(cmd)
    assert exc_info.value.status_code == 400
    assert "rm_rf" in exc_info.value.detail


def test_validate_command_accepts_service_status() -> None:
    _validate_command(CommandRequest(command_type="service_status", payload={}))


def test_validate_command_accepts_docker_inspect() -> None:
    _validate_command(CommandRequest(command_type="docker_inspect", payload={}))


def test_validate_command_run_diagnostic_allowlisted_exact() -> None:
    _validate_command(
        CommandRequest(command_type="run_diagnostic", payload={"command": "df -h"})
    )


def test_validate_command_run_diagnostic_allowlisted_prefix() -> None:
    """Commands that *start with* an allowlisted entry are accepted."""
    _validate_command(
        CommandRequest(
            command_type="run_diagnostic",
            payload={"command": "ps aux --sort=-%mem | head -20 | grep python"},
        )
    )


def test_validate_command_run_diagnostic_blocked_arbitrary_command() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_command(
            CommandRequest(
                command_type="run_diagnostic",
                payload={"command": "cat /etc/shadow"},
            )
        )
    assert exc_info.value.status_code == 403


def test_validate_command_run_diagnostic_blocked_rm_rf() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_command(
            CommandRequest(command_type="run_diagnostic", payload={"command": "rm -rf /"})
        )
    assert exc_info.value.status_code == 403


def test_validate_command_run_diagnostic_empty_payload_blocked() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_command(CommandRequest(command_type="run_diagnostic", payload={}))
    assert exc_info.value.status_code == 403


def test_validate_command_read_file_allowlisted_ssh_config() -> None:
    _validate_command(
        CommandRequest(
            command_type="read_file",
            payload={"path": "/etc/ssh/sshd_config"},
        )
    )


def test_validate_command_read_file_allowlisted_nginx_dir() -> None:
    _validate_command(
        CommandRequest(
            command_type="read_file",
            payload={"path": "/etc/nginx/nginx.conf"},
        )
    )


def test_validate_command_read_file_blocked_arbitrary_path() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_command(
            CommandRequest(command_type="read_file", payload={"path": "/home/user/secrets.txt"})
        )
    assert exc_info.value.status_code == 403


def test_validate_command_read_file_blocked_etc_passwd() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_command(
            CommandRequest(command_type="read_file", payload={"path": "/etc/passwd"})
        )
    assert exc_info.value.status_code == 403


def test_validate_command_read_file_path_traversal_blocked() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_command(
            CommandRequest(
                command_type="read_file",
                payload={"path": "/etc/ssh/../shadow"},
            )
        )
    assert exc_info.value.status_code == 403


def test_validate_command_read_file_empty_path_blocked() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_command(CommandRequest(command_type="read_file", payload={}))
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# _sign_command — pure unit tests
# ---------------------------------------------------------------------------


def test_sign_command_is_deterministic() -> None:
    sig1 = _sign_command("token", "cmd-id", '{"key": "val"}')
    sig2 = _sign_command("token", "cmd-id", '{"key": "val"}')
    assert sig1 == sig2


def test_sign_command_differs_on_token() -> None:
    sig1 = _sign_command("token-a", "cmd-id", '{"key": "val"}')
    sig2 = _sign_command("token-b", "cmd-id", '{"key": "val"}')
    assert sig1 != sig2


def test_sign_command_differs_on_command_id() -> None:
    sig1 = _sign_command("token", "cmd-001", "{}")
    sig2 = _sign_command("token", "cmd-002", "{}")
    assert sig1 != sig2


def test_sign_command_differs_on_payload() -> None:
    sig1 = _sign_command("token", "cmd-id", '{"a": 1}')
    sig2 = _sign_command("token", "cmd-id", '{"a": 2}')
    assert sig1 != sig2


def test_sign_command_matches_expected_hmac_sha256() -> None:
    token, command_id, payload_json = "secret", "abc-123", '{"command": "df -h"}'
    msg = f"{command_id}:{payload_json}".encode()
    expected = hmac.new(token.encode(), msg, hashlib.sha256).hexdigest()
    assert _sign_command(token, command_id, payload_json) == expected


def test_sign_command_returns_hex_string() -> None:
    sig = _sign_command("tok", "id", "{}")
    assert all(c in "0123456789abcdef" for c in sig)
    assert len(sig) == 64  # SHA-256 produces 32 bytes = 64 hex chars


# ---------------------------------------------------------------------------
# POST /{agent_id}/commands — send_command
# ---------------------------------------------------------------------------


def test_send_command_invalid_type_returns_400_before_db() -> None:
    """Validation runs before any DB access; 400 emitted immediately."""
    client = TestClient(_make_app())
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands",
        json={"command_type": "exec_shell", "payload": {}},
    )
    assert r.status_code == 400


def test_send_command_blocked_diagnostic_returns_403() -> None:
    client = TestClient(_make_app())
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands",
        json={"command_type": "run_diagnostic", "payload": {"command": "rm -rf /"}},
    )
    assert r.status_code == 403


def test_send_command_blocked_read_file_path_returns_403() -> None:
    client = TestClient(_make_app())
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands",
        json={"command_type": "read_file", "payload": {"path": "/root/.ssh/id_rsa"}},
    )
    assert r.status_code == 403


def test_send_command_agent_not_found_returns_404() -> None:
    result = _result_one(None)
    client = TestClient(_make_app(_make_session(result)))
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands",
        json={"command_type": "service_status", "payload": {"service": "nginx"}},
    )
    assert r.status_code == 404
    assert "agent-001" in r.json()["detail"]


def test_send_command_agent_offline_returns_409() -> None:
    agent_row = _Row(agent_id="agent-001", api_token="tok", status="offline")
    result = _result_one(agent_row)
    client = TestClient(_make_app(_make_session(result)))
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands",
        json={"command_type": "docker_inspect", "payload": {"container": "myapp"}},
    )
    assert r.status_code == 409
    assert "offline" in r.json()["detail"]


def test_send_command_agent_degraded_returns_409() -> None:
    agent_row = _Row(agent_id="agent-001", api_token="tok", status="degraded")
    result = _result_one(agent_row)
    client = TestClient(_make_app(_make_session(result)))
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands",
        json={"command_type": "service_status", "payload": {}},
    )
    assert r.status_code == 409


def test_send_command_success_redis_unavailable_still_returns_pending() -> None:
    """Command is persisted in DB even when Redis publish raises an exception."""
    agent_row = _Row(agent_id="agent-001", api_token="secret-token", status="online")
    agent_result = _result_one(agent_row)
    insert_result = MagicMock()

    with patch("redis.asyncio.from_url", side_effect=Exception("Connection refused")):
        client = TestClient(_make_app(_make_session(agent_result, insert_result)))
        r = client.post(
            "/api/v1/agent-commands/agent-001/commands",
            json={"command_type": "service_status", "payload": {"service": "nginx"}},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["agent_id"] == "agent-001"
    assert data["command_type"] == "service_status"
    assert data["status"] == "pending"
    assert "command_id" in data
    assert data["created_at"]


def test_send_command_response_contains_valid_uuid_command_id() -> None:
    agent_row = _Row(agent_id="agent-002", api_token="tok2", status="online")
    agent_result = _result_one(agent_row)
    insert_result = MagicMock()

    with patch("redis.asyncio.from_url", side_effect=Exception("no redis")):
        client = TestClient(_make_app(_make_session(agent_result, insert_result)))
        r = client.post(
            "/api/v1/agent-commands/agent-002/commands",
            json={"command_type": "run_diagnostic", "payload": {"command": "uptime"}},
        )

    assert r.status_code == 200
    command_id = r.json()["command_id"]
    parsed = uuid.UUID(command_id)  # raises ValueError if not valid UUID
    assert str(parsed) == command_id


# ---------------------------------------------------------------------------
# GET /{agent_id}/commands/{command_id} — get_command_result
# ---------------------------------------------------------------------------


def test_get_command_result_not_found_returns_404() -> None:
    result = _result_one(None)
    client = TestClient(_make_app(_make_session(result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/nonexistent-cmd")
    assert r.status_code == 404


def test_get_command_result_completed_returns_200() -> None:
    now = datetime.now(tz=UTC)
    cmd_row = _Row(
        command_id="cmd-abc",
        agent_id="agent-001",
        command_type="service_status",
        status="completed",
        result={"exit_code": 0, "stdout": "active"},
        error=None,
        duration_ms=250,
        created_at=now,
        completed_at=now,
    )
    result = _result_one(cmd_row)
    client = TestClient(_make_app(_make_session(result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/cmd-abc")
    assert r.status_code == 200
    data = r.json()
    assert data["command_id"] == "cmd-abc"
    assert data["agent_id"] == "agent-001"
    assert data["status"] == "completed"
    assert data["duration_ms"] == 250
    assert data["completed_at"] is not None


def test_get_command_result_pending_has_null_completed_at() -> None:
    now = datetime.now(tz=UTC)
    cmd_row = _Row(
        command_id="cmd-xyz",
        agent_id="agent-001",
        command_type="docker_inspect",
        status="pending",
        result=None,
        error=None,
        duration_ms=None,
        created_at=now,
        completed_at=None,
    )
    result = _result_one(cmd_row)
    client = TestClient(_make_app(_make_session(result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/cmd-xyz")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert data["completed_at"] is None
    assert data["error"] is None


def test_get_command_result_failed_includes_error_field() -> None:
    now = datetime.now(tz=UTC)
    cmd_row = _Row(
        command_id="cmd-fail",
        agent_id="agent-001",
        command_type="run_diagnostic",
        status="failed",
        result=None,
        error="connection timed out",
        duration_ms=30000,
        created_at=now,
        completed_at=now,
    )
    result = _result_one(cmd_row)
    client = TestClient(_make_app(_make_session(result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/cmd-fail")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "failed"
    assert data["error"] == "connection timed out"


# ---------------------------------------------------------------------------
# GET /{agent_id}/commands — list_commands
# ---------------------------------------------------------------------------


def test_list_commands_empty_returns_empty_list() -> None:
    rows_result = _result_many([])
    client = TestClient(_make_app(_make_session(rows_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands")
    assert r.status_code == 200
    assert r.json() == []


def test_list_commands_single_item() -> None:
    now = datetime.now(tz=UTC)
    row = _Row(
        command_id="cmd-xyz",
        agent_id="agent-001",
        command_type="docker_inspect",
        status="pending",
        result=None,
        error=None,
        duration_ms=None,
        created_at=now,
        completed_at=None,
    )
    rows_result = _result_many([row])
    client = TestClient(_make_app(_make_session(rows_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["command_id"] == "cmd-xyz"
    assert data[0]["command_type"] == "docker_inspect"


def test_list_commands_multiple_items() -> None:
    now = datetime.now(tz=UTC)
    rows = [
        _Row(
            command_id=f"cmd-{i:03d}",
            agent_id="agent-001",
            command_type="service_status",
            status="completed",
            result={"exit_code": 0},
            error=None,
            duration_ms=100 + i,
            created_at=now,
            completed_at=now,
        )
        for i in range(5)
    ]
    rows_result = _result_many(rows)
    client = TestClient(_make_app(_make_session(rows_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    assert data[0]["command_id"] == "cmd-000"


def test_list_commands_accepts_status_query_param() -> None:
    rows_result = _result_many([])
    client = TestClient(_make_app(_make_session(rows_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands", params={"status": "completed"})
    assert r.status_code == 200


def test_list_commands_accepts_limit_query_param() -> None:
    rows_result = _result_many([])
    client = TestClient(_make_app(_make_session(rows_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands", params={"limit": 5})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /{agent_id}/commands/{command_id}/stream — stream_command_result
# ---------------------------------------------------------------------------


def test_stream_returns_sse_content_type_for_completed_command() -> None:
    """Generator terminates after the first completed poll (no asyncio.sleep called)."""
    now = datetime.now(tz=UTC)
    stream_row = _Row(
        status="completed",
        result={"exit_code": 0},
        error=None,
        duration_ms=100,
        completed_at=now,
    )
    stream_result = _result_one(stream_row)
    client = TestClient(_make_app(_make_session(stream_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/cmd-abc/stream")
    assert r.status_code == 200
    assert "event-stream" in r.headers.get("content-type", "")


def test_stream_body_starts_with_sse_data_frame() -> None:
    now = datetime.now(tz=UTC)
    stream_row = _Row(
        status="completed",
        result={"exit_code": 0},
        error=None,
        duration_ms=150,
        completed_at=now,
    )
    stream_result = _result_one(stream_row)
    client = TestClient(_make_app(_make_session(stream_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/cmd-abc/stream")
    assert r.text.startswith("data: ")


def test_stream_sse_payload_contains_status_completed() -> None:
    now = datetime.now(tz=UTC)
    stream_row = _Row(
        status="completed",
        result={"exit_code": 0},
        error=None,
        duration_ms=200,
        completed_at=now,
    )
    stream_result = _result_one(stream_row)
    client = TestClient(_make_app(_make_session(stream_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/cmd-abc/stream")
    first_event = r.text.split("data: ")[1].split("\n\n")[0]
    payload = json.loads(first_event)
    assert payload["status"] == "completed"


def test_stream_sse_payload_contains_status_failed() -> None:
    now = datetime.now(tz=UTC)
    stream_row = _Row(
        status="failed",
        result=None,
        error="agent unreachable",
        duration_ms=5000,
        completed_at=now,
    )
    stream_result = _result_one(stream_row)
    client = TestClient(_make_app(_make_session(stream_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/cmd-fail/stream")
    first_event = r.text.split("data: ")[1].split("\n\n")[0]
    payload = json.loads(first_event)
    assert payload["status"] == "failed"


def test_stream_not_found_yields_error_event() -> None:
    """When the command is not in DB, the stream yields a JSON error event."""
    not_found_result = _result_one(None)
    client = TestClient(_make_app(_make_session(not_found_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/missing/stream")
    assert r.status_code == 200
    assert "data: " in r.text
    first_event = r.text.split("data: ")[1].split("\n\n")[0]
    payload = json.loads(first_event)
    assert "error" in payload


def test_stream_cache_control_header_is_no_cache() -> None:
    now = datetime.now(tz=UTC)
    stream_row = _Row(
        status="completed", result={}, error=None, duration_ms=10, completed_at=now
    )
    stream_result = _result_one(stream_row)
    client = TestClient(_make_app(_make_session(stream_result)))
    r = client.get("/api/v1/agent-commands/agent-001/commands/cmd-abc/stream")
    assert r.headers.get("cache-control") == "no-cache"


# ---------------------------------------------------------------------------
# POST /{agent_id}/commands/{command_id}/result — receive_command_result
# ---------------------------------------------------------------------------


def test_receive_result_command_not_found_returns_404() -> None:
    not_found_result = MagicMock()
    not_found_result.first.return_value = None
    client = TestClient(_make_app(_make_session(not_found_result)))
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands/no-such-cmd/result",
        json={"result": {"exit_code": 0}, "duration_ms": 100},
    )
    assert r.status_code == 404


def test_receive_result_accepted_returns_status() -> None:
    found_result = MagicMock()
    found_result.first.return_value = MagicMock()
    update_result = MagicMock()
    client = TestClient(_make_app(_make_session(found_result, update_result)))
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands/cmd-abc/result",
        json={"result": {"exit_code": 0, "stdout": "OK"}, "duration_ms": 150},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "accepted"}


def test_receive_result_with_error_field_accepted() -> None:
    found_result = MagicMock()
    found_result.first.return_value = MagicMock()
    update_result = MagicMock()
    client = TestClient(_make_app(_make_session(found_result, update_result)))
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands/cmd-abc/result",
        json={"error": "connection timed out", "duration_ms": 30000},
    )
    assert r.status_code == 200
    assert r.json() is not None


def test_receive_result_empty_payload_accepted() -> None:
    """An empty result payload is valid — result_payload.get() handles missing keys."""
    found_result = MagicMock()
    found_result.first.return_value = MagicMock()
    update_result = MagicMock()
    client = TestClient(_make_app(_make_session(found_result, update_result)))
    r = client.post(
        "/api/v1/agent-commands/agent-001/commands/cmd-abc/result",
        json={},
    )
    assert r.status_code == 200
