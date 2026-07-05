"""Tests for ToolExecutor timeout handling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.cognitive.tool_executor import ToolExecutor
from internalcmdb.cognitive.tool_registry import RiskClass


@pytest.mark.asyncio
async def test_execute_times_out_when_tool_exceeds_timeout_s() -> None:
    tool = MagicMock()
    tool.tool_id = "slow_tool"
    tool.name = "Slow Tool"
    tool.risk_class = RiskClass.RC1
    tool.cooldown_s = 0
    tool.timeout_s = 1

    async def slow_execute(_params: dict) -> dict:
        await asyncio.sleep(2)
        return {"ok": True}

    tool.execute = slow_execute

    registry = MagicMock()
    registry.get.return_value = tool

    with (
        patch(
            "internalcmdb.cognitive.tool_registry.get_registry",
            return_value=registry,
        ),
        patch.object(ToolExecutor, "_check_policy", new_callable=AsyncMock, return_value=""),
        patch.object(ToolExecutor, "_persist_audit", new_callable=AsyncMock),
        patch.object(ToolExecutor, "_guard_scan_params", new_callable=AsyncMock, return_value=""),
        patch.object(ToolExecutor, "_guard_scan_output", return_value=""),
    ):
        executor = ToolExecutor()
        result = await executor.execute("slow_tool", {})

    assert result.success is False
    assert "timed out" in result.error.lower()
