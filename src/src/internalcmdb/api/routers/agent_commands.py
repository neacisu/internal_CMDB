"""Agent Command Router — send commands to remote agents via Redis pub/sub.

Endpoints:
    POST /api/v1/agent-commands/{agent_id}/commands   — dispatch command
    GET  /api/v1/agent-commands/{agent_id}/commands/{command_id} — poll result
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_async_session
from ..middleware.rate_limit import rate_limit
from ..middleware.rbac import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-commands", tags=["agent-commands"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALLOWED_COMMAND_TYPES = frozenset({
    "run_diagnostic",
    "read_file",
    "service_status",
    "docker_inspect",
})

_COMMAND_TIMEOUT_S = 30

_MAX_OUTPUT_BYTES = 65_536  # 64 KB

# Read-only diagnostic commands that can be issued without HITL approval
_DIAGNOSTIC_COMMANDS: dict[str, list[str]] = {
    "run_diagnostic": [
        "df -h",
        "ps aux --sort=-%mem | head -20",
        "systemctl list-units --state=failed",
        "docker ps -a --format json",
        "journalctl -p err --since '1 hour ago' --no-pager | tail -100",
        "uptime",
        "free -h",
        "ss -tlnp",
    ],
    "read_file": [
        "/etc/ssh/sshd_config",
        "/etc/systemd/",
        "/etc/haproxy/",
        "/etc/nginx/",
        "/etc/fail2ban/",
    ],
    "service_status": [],  # any service name is allowed
    "docker_inspect": [],  # any container name is allowed
}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CommandRequest(BaseModel):
    """Request to send a command to an agent."""

    command_type: str = Field(
        ...,
        description="Command type: run_diagnostic, read_file, service_status, docker_inspect",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Command-specific payload (e.g. {'command': 'df -h'})",
    )
    timeout: int = Field(
        default=_COMMAND_TIMEOUT_S,
        ge=5,
        le=120,
        description="Command timeout in seconds",
    )


class CommandResponse(BaseModel):
    """Response from a command dispatch or poll."""

    command_id: str
    agent_id: str
    command_type: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int | None = None
    created_at: str
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_command(cmd: CommandRequest) -> None:
    """Validate command type and payload against allowlists."""
    if cmd.command_type not in _ALLOWED_COMMAND_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown command_type: {cmd.command_type}. "
            f"Allowed: {sorted(_ALLOWED_COMMAND_TYPES)}",
        )

    # Validate run_diagnostic commands against allowlist
    if cmd.command_type == "run_diagnostic":
        shell_cmd = cmd.payload.get("command", "")
        allowed = _DIAGNOSTIC_COMMANDS["run_diagnostic"]
        if not any(shell_cmd.startswith(a) for a in allowed):
            raise HTTPException(
                status_code=403,
                detail=f"Command not in diagnostic allowlist: {shell_cmd}",
            )

    # Validate read_file paths against allowlist
    if cmd.command_type == "read_file":
        file_path = cmd.payload.get("path", "")
        allowed_prefixes = _DIAGNOSTIC_COMMANDS["read_file"]
        if not any(file_path.startswith(p) for p in allowed_prefixes):
            raise HTTPException(
                status_code=403,
                detail=f"File path not in allowlist: {file_path}",
            )
        # Block path traversal
        if ".." in file_path:
            raise HTTPException(status_code=403, detail="Path traversal blocked")


def _sign_command(agent_token: str, command_id: str, payload_json: str) -> str:
    """HMAC-SHA256 sign a command for agent verification."""
    msg = f"{command_id}:{payload_json}".encode()
    return hmac.new(agent_token.encode(), msg, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{agent_id}/commands",
    response_model=CommandResponse,
    dependencies=[Depends(rate_limit), Depends(require_role("platform_admin", "operator"))],
)
async def send_command(
    agent_id: str,
    cmd: CommandRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> CommandResponse:
    """Send a command to a remote agent via Redis pub/sub."""
    _validate_command(cmd)

    # Verify agent exists and is online
    row = await db.execute(
        text("""
            SELECT a.agent_id, a.api_token, a.status
            FROM discovery.collector_agent a
            WHERE a.agent_id = :agent_id
        """),
        {"agent_id": agent_id},
    )
    agent = row.mappings().first()
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    if agent["status"] != "online":
        raise HTTPException(
            status_code=409,
            detail=f"Agent {agent_id} is {agent['status']}, cannot send commands",
        )

    command_id = str(uuid.uuid4())
    payload_json = json.dumps(cmd.payload, sort_keys=True)
    signature = _sign_command(str(agent["api_token"]), command_id, payload_json)
    now = datetime.now(tz=UTC)

    # Persist command to DB
    await db.execute(
        text("""
            INSERT INTO agent_control.command_log
                (command_id, agent_id, command_type, payload, status,
                 issued_by, expires_at, created_at)
            VALUES
                (:cmd_id, :agent_id, :cmd_type, :payload::json,
                 'pending', :issued_by,
                 now() + :timeout * interval '1 second', :created_at)
        """),
        {
            "cmd_id": command_id,
            "agent_id": agent_id,
            "cmd_type": cmd.command_type,
            "payload": payload_json,
            "issued_by": "api_user",
            "timeout": cmd.timeout,
            "created_at": now.isoformat(),
        },
    )
    await db.commit()

    # Publish to Redis channel for the agent
    try:
        import redis.asyncio as aioredis  # noqa: PLC0415

        from ..config import get_settings  # noqa: PLC0415

        settings = get_settings()
        r = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        try:
            channel = f"infraq:agent:{agent_id}:commands"
            message = json.dumps({
                "command_id": command_id,
                "command_type": cmd.command_type,
                "payload": cmd.payload,
                "timeout": cmd.timeout,
                "signature": signature,
            })
            await r.publish(channel, message)
            logger.info("Command %s published to %s", command_id, channel)
        finally:
            await r.aclose()
    except Exception:
        logger.warning("Redis publish failed for command %s — agent must poll", command_id)

    return CommandResponse(
        command_id=command_id,
        agent_id=agent_id,
        command_type=cmd.command_type,
        status="pending",
        created_at=now.isoformat(),
    )


@router.get(
    "/{agent_id}/commands/{command_id}",
    response_model=CommandResponse,
    dependencies=[Depends(rate_limit), Depends(require_role("platform_admin", "operator"))],
)
async def get_command_result(
    agent_id: str,
    command_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> CommandResponse:
    """Poll the result of a previously dispatched command."""
    row = await db.execute(
        text("""
            SELECT command_id, agent_id::text, command_type, status,
                   result, error, duration_ms,
                   created_at, completed_at
            FROM agent_control.command_log
            WHERE command_id = :cmd_id AND agent_id = :agent_id
        """),
        {"cmd_id": command_id, "agent_id": agent_id},
    )
    cmd = row.mappings().first()
    if cmd is None:
        raise HTTPException(status_code=404, detail="Command not found")

    return CommandResponse(
        command_id=str(cmd["command_id"]),
        agent_id=str(cmd["agent_id"]),
        command_type=cmd["command_type"],
        status=cmd["status"],
        result=cmd["result"],
        error=cmd["error"],
        duration_ms=cmd["duration_ms"],
        created_at=cmd["created_at"].isoformat() if cmd["created_at"] else "",
        completed_at=cmd["completed_at"].isoformat() if cmd["completed_at"] else None,
    )


@router.get(
    "/{agent_id}/commands",
    dependencies=[Depends(rate_limit), Depends(require_role("platform_admin", "operator"))],
)
async def list_commands(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    status: str = Query(default="", description="Filter by status"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[CommandResponse]:
    """List recent commands for an agent."""
    sql = """
        SELECT command_id, agent_id::text, command_type, status,
               result, error, duration_ms,
               created_at, completed_at
        FROM agent_control.command_log
        WHERE agent_id = :agent_id
    """
    params: dict[str, Any] = {"agent_id": agent_id, "limit": limit}

    if status:
        sql += " AND status = :status"
        params["status"] = status

    sql += " ORDER BY created_at DESC LIMIT :limit"

    rows = await db.execute(text(sql), params)
    result = []
    for r in rows.mappings():
        result.append(CommandResponse(
            command_id=str(r["command_id"]),
            agent_id=str(r["agent_id"]),
            command_type=r["command_type"],
            status=r["status"],
            result=r["result"],
            error=r["error"],
            duration_ms=r["duration_ms"],
            created_at=r["created_at"].isoformat() if r["created_at"] else "",
            completed_at=r["completed_at"].isoformat() if r["completed_at"] else None,
        ))
    return result


# ---------------------------------------------------------------------------
# SSE stream for command results
# ---------------------------------------------------------------------------


@router.get(
    "/{agent_id}/commands/{command_id}/stream",
    dependencies=[Depends(rate_limit), Depends(require_role("platform_admin", "operator"))],
)
async def stream_command_result(
    agent_id: str,
    command_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> Any:
    """Stream command result via SSE. Polls DB until completed or timeout."""
    import asyncio  # noqa: PLC0415

    from starlette.responses import StreamingResponse  # noqa: PLC0415

    async def _event_stream():  # noqa: ANN202
        max_polls = 60  # 60 * 0.5s = 30s max
        for _ in range(max_polls):
            row = await db.execute(
                text("""
                    SELECT status, result, error, duration_ms, completed_at
                    FROM agent_control.command_log
                    WHERE command_id = :cmd_id AND agent_id = :agent_id
                """),
                {"cmd_id": command_id, "agent_id": agent_id},
            )
            cmd = row.mappings().first()
            if cmd is None:
                yield f"data: {json.dumps({'error': 'Command not found'})}\n\n"
                return

            status = cmd["status"]
            payload = {
                "status": status,
                "result": cmd["result"],
                "error": cmd["error"],
                "duration_ms": cmd["duration_ms"],
            }
            yield f"data: {json.dumps(payload, default=str)}\n\n"

            if status in ("completed", "failed", "expired"):
                return

            await asyncio.sleep(0.5)

        yield f"data: {json.dumps({'status': 'timeout', 'error': 'SSE polling timeout'})}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Result callback (for agent daemon HTTP callback)
# ---------------------------------------------------------------------------


@router.post(
    "/{agent_id}/commands/{command_id}/result",
    dependencies=[Depends(rate_limit), Depends(require_role("platform_admin", "operator", "agent"))],
)
async def receive_command_result(
    agent_id: str,
    command_id: str,
    result_payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, str]:
    """Receive command execution result from an agent callback."""
    row = await db.execute(
        text("""
            SELECT command_id FROM agent_control.command_log
            WHERE command_id = :cmd_id AND agent_id = :agent_id
        """),
        {"cmd_id": command_id, "agent_id": agent_id},
    )
    if row.first() is None:
        raise HTTPException(status_code=404, detail="Command not found")

    await db.execute(
        text("""
            UPDATE agent_control.command_log
            SET status = 'completed',
                result = :result::json,
                error = :error,
                duration_ms = :duration_ms,
                completed_at = NOW()
            WHERE command_id = :cmd_id AND agent_id = :agent_id
        """),
        {
            "cmd_id": command_id,
            "agent_id": agent_id,
            "result": json.dumps(result_payload.get("result", result_payload), default=str),
            "error": result_payload.get("error"),
            "duration_ms": result_payload.get("duration_ms"),
        },
    )
    await db.commit()

    return {"status": "accepted"}
