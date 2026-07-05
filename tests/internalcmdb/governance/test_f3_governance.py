"""F3 Governance integration tests — policy gate, dual HITL, guard pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.governance.guard_gate import _llm_guard_scan
from internalcmdb.governance.hitl_workflow import HITLWorkflow
from internalcmdb.llm.guard_pipeline import GuardResult, scan_output, scan_prompt


# ---------------------------------------------------------------------------
# guard_gate — /analyze/prompt endpoint
# ---------------------------------------------------------------------------


class TestGuardGateEndpoint:
    @pytest.mark.asyncio
    async def test_llm_guard_scan_uses_analyze_prompt(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"is_valid": True, "scanners": {"Injection": 0.01}}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with (
            patch(
                "internalcmdb.governance.guard_gate._get_guard_runtime_config",
                new=AsyncMock(return_value=("http://guard:8000", 5.0, True)),
            ),
            patch("internalcmdb.governance.guard_gate.httpx.AsyncClient", return_value=mock_client),
        ):
            ok, detail = await _llm_guard_scan({"type": "read"})

        assert ok is True
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "http://guard:8000/analyze/prompt"
        assert "prompt" in call_kwargs[1]["json"]

    @pytest.mark.asyncio
    async def test_llm_guard_scan_fail_closed_on_error(self) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=ConnectionError("unreachable"))

        with (
            patch(
                "internalcmdb.governance.guard_gate._get_guard_runtime_config",
                new=AsyncMock(return_value=("http://guard:8000", 5.0, True)),
            ),
            patch("internalcmdb.governance.guard_gate.httpx.AsyncClient", return_value=mock_client),
        ):
            ok, detail = await _llm_guard_scan({"type": "read"})

        assert ok is False
        assert "fail-closed" in detail


# ---------------------------------------------------------------------------
# guard_pipeline — fail-closed scan helpers
# ---------------------------------------------------------------------------


class TestGuardPipelineHelpers:
    @pytest.mark.asyncio
    async def test_scan_prompt_fail_closed_on_error(self) -> None:
        client = MagicMock()
        client.guard_input = AsyncMock(side_effect=RuntimeError("down"))
        result = await scan_prompt(client, "test prompt")
        assert result.is_valid is False
        assert result.details.get("_error") == "scan_failed"

    @pytest.mark.asyncio
    async def test_scan_output_fail_closed_on_error(self) -> None:
        client = MagicMock()
        client.guard_output = AsyncMock(side_effect=RuntimeError("down"))
        result = await scan_output(client, "prompt", "output")
        assert result.is_valid is False


# ---------------------------------------------------------------------------
# HITLWorkflow — RC-3 dual approval
# ---------------------------------------------------------------------------


class TestRC3DualApproval:
    @pytest.mark.asyncio
    async def test_rc3_first_approval_stays_pending(self) -> None:
        session = AsyncMock()
        wf = HITLWorkflow(session)

        fetch_result = MagicMock()
        fetch_result.fetchone.return_value = ("RC-3", "pending", [])

        update_result = MagicMock()
        session.execute = AsyncMock(side_effect=[fetch_result, update_result])

        with patch("internalcmdb.governance.hitl_workflow._notify", new=AsyncMock()):
            ok = await wf.approve("item-1", "alice", "looks ok")

        assert ok is True
        session.commit.assert_awaited()
        # Partial approval — _decide not reached (only 2 execute calls)
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_rc3_rejects_duplicate_approver(self) -> None:
        session = AsyncMock()
        wf = HITLWorkflow(session)

        fetch_result = MagicMock()
        fetch_result.fetchone.return_value = (
            "RC-3",
            "pending",
            [{"decided_by": "alice", "reason": "ok"}],
        )
        session.execute = AsyncMock(return_value=fetch_result)

        with patch("internalcmdb.governance.hitl_workflow._notify", new=AsyncMock()):
            ok = await wf.approve("item-1", "alice", "duplicate")
        assert ok is False


# ---------------------------------------------------------------------------
# tool_executor — PolicyEnforcer gate
# ---------------------------------------------------------------------------


class TestToolExecutorPolicyGate:
    @pytest.mark.asyncio
    async def test_rc1_blocked_by_policy(self) -> None:
        from internalcmdb.cognitive.tool_executor import ToolExecutor  # noqa: PLC0415

        mock_tool = MagicMock()
        mock_tool.tool_id = "query_host_health"
        mock_tool.name = "Query Host Health"
        mock_tool.risk_class = MagicMock()
        mock_tool.risk_class.value = "RC-1"
        mock_tool.cooldown_s = 0
        mock_tool.execute = AsyncMock(return_value={"ok": True})

        with (
            patch("internalcmdb.cognitive.tool_registry.get_registry") as mock_reg,
            patch.object(
                ToolExecutor,
                "_check_policy",
                new=AsyncMock(return_value="Action blocked by policy"),
            ),
            patch.object(ToolExecutor, "_persist_audit", new=AsyncMock()),
        ):
            mock_reg.return_value.get.return_value = mock_tool
            result = await ToolExecutor().execute("query_host_health", {"host_code": "hz.1"})

        assert result.success is False
        assert "policy" in result.error.lower()
        mock_tool.execute.assert_not_called()
