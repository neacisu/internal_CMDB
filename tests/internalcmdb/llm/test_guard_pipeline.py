"""Tests for the GuardGate 5-level action evaluation pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.governance.guard_gate import (
    RC_1,
    RC_2,
    RC_3,
    RC_4,
    GuardGate,
    classify_risk,
)

# ---------------------------------------------------------------------------
# classify_risk (L4) — standalone function tests
# ---------------------------------------------------------------------------


class TestClassifyRisk:
    def test_read_action_is_rc1(self) -> None:
        assert classify_risk({"type": "read"}, {}) == RC_1

    def test_query_action_is_rc1(self) -> None:
        assert classify_risk({"type": "query"}, {}) == RC_1

    def test_create_action_is_rc2(self) -> None:
        assert classify_risk({"type": "create"}, {}) == RC_2

    def test_update_action_is_rc3(self) -> None:
        assert classify_risk({"type": "update"}, {}) == RC_3

    def test_delete_action_is_rc4(self) -> None:
        assert classify_risk({"type": "delete"}, {}) == RC_4

    def test_critical_target_escalates_to_rc4(self) -> None:
        assert classify_risk({"type": "update", "target": "production"}, {}) == RC_4

    def test_production_env_defaults_to_rc3(self) -> None:
        assert classify_risk({"type": "custom"}, {"environment": "production"}) == RC_3

    def test_unknown_action_non_prod_is_rc2(self) -> None:
        assert classify_risk({"type": "custom"}, {"environment": "staging"}) == RC_2


# ---------------------------------------------------------------------------
# GuardGate — full pipeline tests
# ---------------------------------------------------------------------------


class TestGuardGate:
    @pytest.fixture
    def mock_session(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def gate(self, mock_session: MagicMock) -> GuardGate:
        g = GuardGate.__new__(GuardGate)
        g._session = mock_session

        scanner = MagicMock()
        scan_result = MagicMock()
        scan_result.safe = True
        scan_result.matched_patterns = []
        scanner.scan_fact_payload.return_value = scan_result
        g._scanner = scanner

        enforcer = MagicMock()
        policy_result = MagicMock()
        policy_result.compliant = True
        policy_result.violations = []
        enforcer.check.return_value = policy_result
        g._enforcer = enforcer

        return g

    @pytest.mark.asyncio
    async def test_read_action_passes_all_levels(self, gate: GuardGate) -> None:
        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new_callable=AsyncMock,
            return_value=(True, "ok"),
        ):
            decision = await gate.evaluate({"type": "read"}, {})
        assert decision.allowed is True
        assert decision.risk_class == RC_1
        assert decision.blocked_at_level is None

    @pytest.mark.asyncio
    async def test_pii_blocked_at_l1(self, gate: GuardGate) -> None:
        scan_result = MagicMock()
        scan_result.safe = False
        scan_result.matched_patterns = ["email", "ssn"]
        gate._scanner.scan_fact_payload.return_value = scan_result

        decision = await gate.evaluate({"type": "create"}, {})
        assert decision.allowed is False
        assert decision.blocked_at_level == 1
        assert decision.risk_class == RC_4

    @pytest.mark.asyncio
    async def test_llm_guard_blocks_at_l2(self, gate: GuardGate) -> None:
        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new_callable=AsyncMock,
            return_value=(False, "prompt-injection-detected"),
        ):
            decision = await gate.evaluate({"type": "create"}, {})
        assert decision.allowed is False
        assert decision.blocked_at_level == 2

    @pytest.mark.asyncio
    async def test_policy_violation_blocks_at_l3(self, gate: GuardGate) -> None:
        policy_result = MagicMock()
        policy_result.compliant = False
        violation = MagicMock()
        violation.reason = "change-window-closed"
        policy_result.violations = [violation]
        gate._enforcer.check.return_value = policy_result

        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new_callable=AsyncMock,
            return_value=(True, "ok"),
        ):
            decision = await gate.evaluate({"type": "update"}, {})
        assert decision.allowed is False
        assert decision.blocked_at_level == 3

    @pytest.mark.asyncio
    async def test_delete_requires_hitl_at_l5(self, gate: GuardGate) -> None:
        with patch(
            "internalcmdb.governance.guard_gate._llm_guard_scan",
            new_callable=AsyncMock,
            return_value=(True, "ok"),
        ):
            decision = await gate.evaluate({"type": "delete"}, {})
        assert decision.allowed is False
        assert decision.blocked_at_level == 5
        assert decision.requires_hitl is True
        assert decision.risk_class == RC_4
