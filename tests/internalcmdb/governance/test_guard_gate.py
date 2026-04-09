"""Tests for internalcmdb.governance.guard_gate."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.governance.guard_gate import (
    RC_1,
    RC_2,
    RC_3,
    RC_4,
    GateDecision,
    GuardGate,
    LevelTrace,
    _llm_guard_scan,
    classify_risk,
)

# ---------------------------------------------------------------------------
# Tests: classify_risk
# ---------------------------------------------------------------------------


class TestClassifyRisk:
    def test_read_action_is_rc1(self) -> None:
        result = classify_risk({"type": "read", "target": "host-01"}, {})
        assert result == RC_1

    def test_query_action_is_rc1(self) -> None:
        result = classify_risk({"type": "query", "target": "host-01"}, {})
        assert result == RC_1

    def test_read_on_critical_target_is_rc2(self) -> None:
        result = classify_risk({"type": "read", "target": "production"}, {})
        assert result == RC_2

    def test_create_action_is_rc2(self) -> None:
        result = classify_risk({"type": "create", "target": "host-01"}, {})
        assert result == RC_2

    def test_create_on_critical_target_is_rc3(self) -> None:
        result = classify_risk({"type": "create", "target": "production"}, {})
        assert result == RC_3

    def test_update_action_is_rc3(self) -> None:
        result = classify_risk({"type": "update", "target": "host-01"}, {})
        assert result == RC_3

    def test_update_on_critical_target_is_rc4(self) -> None:
        result = classify_risk({"type": "update", "target": "production"}, {})
        assert result == RC_4

    def test_delete_action_is_rc4(self) -> None:
        result = classify_risk({"type": "delete", "target": "host-01"}, {})
        assert result == RC_4

    def test_destroy_action_is_rc4(self) -> None:
        result = classify_risk({"type": "destroy", "target": "anything"}, {})
        assert result == RC_4

    def test_terminate_action_is_rc4(self) -> None:
        result = classify_risk({"type": "terminate", "target": "host-01"}, {})
        assert result == RC_4

    def test_unknown_action_in_production_env_is_rc3(self) -> None:
        result = classify_risk(
            {"type": "unknown_op", "target": "host-01"}, {"environment": "production"}
        )
        assert result == RC_3

    def test_unknown_action_no_context_is_rc2(self) -> None:
        result = classify_risk({"type": "custom_op", "target": "host-01"}, {})
        assert result == RC_2

    def test_restart_on_cluster_is_rc4(self) -> None:
        result = classify_risk({"type": "restart", "target": "cluster"}, {})
        assert result == RC_4

    def test_scale_on_database_is_rc4(self) -> None:
        result = classify_risk({"type": "scale", "target": "database"}, {})
        assert result == RC_4

    def test_missing_type_is_rc2(self) -> None:
        result = classify_risk({"target": "host-01"}, {})
        assert result == RC_2

    def test_prod_env_context_rc3(self) -> None:
        result = classify_risk(
            {"type": "something_else", "target": "host"}, {"environment": "prod"}
        )
        assert result == RC_3


# ---------------------------------------------------------------------------
# Tests: GateDecision dataclass
# ---------------------------------------------------------------------------


class TestGateDecision:
    def test_allowed_decision(self) -> None:
        d = GateDecision(
            allowed=True,
            risk_class=RC_1,
            blocked_at_level=None,
            reason="all-clear",
            requires_hitl=False,
        )
        assert d.allowed is True
        assert d.requires_hitl is False
        assert d.gate_trace == ()

    def test_blocked_decision(self) -> None:
        t = LevelTrace(level=1, name="input_sanitisation", passed=False, detail="pii found")
        d = GateDecision(
            allowed=False,
            risk_class=RC_4,
            blocked_at_level=1,
            reason="PII detected",
            requires_hitl=False,
            gate_trace=(t,),
        )
        assert d.allowed is False
        assert d.blocked_at_level == 1
        assert len(d.gate_trace) == 1


# ---------------------------------------------------------------------------
# Tests: _llm_guard_scan
# ---------------------------------------------------------------------------


class TestLLMGuardScan:
    @pytest.mark.asyncio
    async def test_llm_guard_returns_safe_on_200(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"safe": True, "detail": "ok"}

        with patch("internalcmdb.governance.guard_gate.httpx.AsyncClient") as MockClient:  # noqa: N806
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "internalcmdb.governance.guard_gate._LLM_GUARD_URL", "http://llm-guard:8000"
            ):
                safe, _detail = await _llm_guard_scan({"action": "test"})

        assert safe is True

    @pytest.mark.asyncio
    async def test_llm_guard_unsafe_response(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"safe": False, "detail": "prompt injection"}

        with patch("internalcmdb.governance.guard_gate.httpx.AsyncClient") as MockClient:  # noqa: N806
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "internalcmdb.governance.guard_gate._LLM_GUARD_URL", "http://llm-guard:8000"
            ):
                safe, detail = await _llm_guard_scan({"action": "inject"})

        assert safe is False
        assert "injection" in detail

    @pytest.mark.asyncio
    async def test_llm_guard_connection_error_fail_closed(self) -> None:
        with patch("internalcmdb.governance.guard_gate.httpx.AsyncClient") as MockClient:  # noqa: N806
            MockClient.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("connection refused")
            )
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            with (
                patch("internalcmdb.governance.guard_gate._LLM_GUARD_URL", "http://llm-guard:8000"),
                patch("internalcmdb.governance.guard_gate._LLM_GUARD_FAIL_CLOSED", True),
            ):
                safe, detail = await _llm_guard_scan({"action": "test"})

        assert safe is False
        assert "fail-closed" in detail or "unavailable" in detail


# ---------------------------------------------------------------------------
# Tests: GuardGate.evaluate
# ---------------------------------------------------------------------------


def _make_gate() -> tuple[GuardGate, MagicMock, MagicMock]:
    session = MagicMock()
    with (
        patch("internalcmdb.governance.guard_gate.RedactionScanner") as MockScanner,  # noqa: N806
        patch("internalcmdb.governance.guard_gate.PolicyEnforcer") as MockEnforcer,  # noqa: N806
    ):
        gate = GuardGate(session)
        return gate, MockScanner.return_value, MockEnforcer.return_value


class TestGuardGateEvaluate:
    @pytest.mark.asyncio
    async def test_l1_blocks_on_pii_detected(self) -> None:
        gate, mock_scanner, _mock_enforcer = _make_gate()

        scan_result = MagicMock()
        scan_result.safe = False
        scan_result.matched_patterns = ["CREDIT_CARD"]
        mock_scanner.scan_fact_payload.return_value = scan_result

        action = {"type": "read", "target": "host-01"}
        context: dict[str, Any] = {}

        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new=AsyncMock(return_value=(True, "ok")),
        ):
            decision = await gate.evaluate(action, context)

        assert decision.allowed is False
        assert decision.blocked_at_level == 1
        assert "L1" in decision.reason

    @pytest.mark.asyncio
    async def test_l2_blocks_on_llm_guard_unsafe(self) -> None:
        gate, mock_scanner, _mock_enforcer = _make_gate()

        scan_result = MagicMock()
        scan_result.safe = True
        scan_result.matched_patterns = []
        mock_scanner.scan_fact_payload.return_value = scan_result

        action = {"type": "read", "target": "host-01"}
        context: dict[str, Any] = {}

        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new=AsyncMock(return_value=(False, "jailbreak")),
        ):
            decision = await gate.evaluate(action, context)

        assert decision.allowed is False
        assert decision.blocked_at_level == 2
        assert "L2" in decision.reason

    @pytest.mark.asyncio
    async def test_l3_blocks_on_policy_violation(self) -> None:
        gate, mock_scanner, mock_enforcer = _make_gate()

        scan_result = MagicMock()
        scan_result.safe = True
        scan_result.matched_patterns = []
        mock_scanner.scan_fact_payload.return_value = scan_result

        v = MagicMock()
        v.reason = "blocked by policy"
        policy_result = MagicMock()
        policy_result.compliant = False
        policy_result.violations = [v]
        mock_enforcer.check.return_value = policy_result

        action = {"type": "read", "target": "host-01"}
        context: dict[str, Any] = {}

        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new=AsyncMock(return_value=(True, "ok")),
        ):
            decision = await gate.evaluate(action, context)

        assert decision.allowed is False
        assert decision.blocked_at_level == 3

    @pytest.mark.asyncio
    async def test_rc1_action_allowed(self) -> None:
        gate, mock_scanner, mock_enforcer = _make_gate()

        scan_result = MagicMock()
        scan_result.safe = True
        scan_result.matched_patterns = []
        mock_scanner.scan_fact_payload.return_value = scan_result

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_enforcer.check.return_value = policy_result

        action = {"type": "read", "target": "dev-host-01"}
        context: dict[str, Any] = {}

        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new=AsyncMock(return_value=(True, "ok")),
        ):
            decision = await gate.evaluate(action, context)

        assert decision.allowed is True
        assert decision.blocked_at_level is None
        assert decision.risk_class == RC_1
        assert decision.requires_hitl is False

    @pytest.mark.asyncio
    async def test_rc3_action_requires_hitl(self) -> None:
        gate, mock_scanner, mock_enforcer = _make_gate()

        scan_result = MagicMock()
        scan_result.safe = True
        scan_result.matched_patterns = []
        mock_scanner.scan_fact_payload.return_value = scan_result

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_enforcer.check.return_value = policy_result

        action = {"type": "update", "target": "dev-host-01"}
        context: dict[str, Any] = {}

        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new=AsyncMock(return_value=(True, "ok")),
        ):
            decision = await gate.evaluate(action, context)

        assert decision.allowed is False
        assert decision.requires_hitl is True
        assert decision.blocked_at_level == 5

    @pytest.mark.asyncio
    async def test_rc4_delete_requires_hitl(self) -> None:
        gate, mock_scanner, mock_enforcer = _make_gate()

        scan_result = MagicMock()
        scan_result.safe = True
        scan_result.matched_patterns = []
        mock_scanner.scan_fact_payload.return_value = scan_result

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_enforcer.check.return_value = policy_result

        action = {"type": "delete", "target": "host-01"}
        context: dict[str, Any] = {}

        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new=AsyncMock(return_value=(True, "ok")),
        ):
            decision = await gate.evaluate(action, context)

        assert decision.allowed is False
        assert decision.requires_hitl is True
        assert decision.risk_class == RC_4

    @pytest.mark.asyncio
    async def test_gate_trace_is_populated(self) -> None:
        gate, mock_scanner, mock_enforcer = _make_gate()

        scan_result = MagicMock()
        scan_result.safe = True
        scan_result.matched_patterns = []
        mock_scanner.scan_fact_payload.return_value = scan_result

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_enforcer.check.return_value = policy_result

        action = {"type": "read", "target": "host-01"}
        context: dict[str, Any] = {}

        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new=AsyncMock(return_value=(True, "ok")),
        ):
            decision = await gate.evaluate(action, context)

        assert len(decision.gate_trace) == 5
        levels = [t.level for t in decision.gate_trace]
        assert levels == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_rc2_allowed_list_action(self) -> None:
        gate, mock_scanner, mock_enforcer = _make_gate()

        scan_result = MagicMock()
        scan_result.safe = True
        scan_result.matched_patterns = []
        mock_scanner.scan_fact_payload.return_value = scan_result

        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        mock_enforcer.check.return_value = policy_result

        action = {"type": "list", "target": "secrets"}
        context: dict[str, Any] = {}

        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new=AsyncMock(return_value=(True, "ok")),
        ):
            decision = await gate.evaluate(action, context)

        assert decision.allowed is True
        assert decision.risk_class == RC_2
