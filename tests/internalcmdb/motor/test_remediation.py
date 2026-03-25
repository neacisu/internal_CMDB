"""Tests for the Remediation Engine — risk classification and action routing."""

from __future__ import annotations

from typing import Any

import pytest

from internalcmdb.motor.remediation import (
    RC_1,
    RC_2,
    RC_3,
    RC_4,
    RemediationAction,
    RemediationEngine,
    RemediationPlan,
)


class TestRemediationEngine:
    @pytest.fixture
    def engine(self) -> RemediationEngine:
        return RemediationEngine()

    # ------------------------------------------------------------------
    # Risk classification
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_log_observation_is_rc1(self, engine: RemediationEngine) -> None:
        plan = await engine.propose({"type": "unknown_event", "target_entity": "host-1"})
        assert plan.risk_class == RC_1
        assert plan.status == "pending_approval"

    @pytest.mark.asyncio
    async def test_restart_container_is_rc2(self, engine: RemediationEngine) -> None:
        plan = await engine.propose({
            "type": "container_crash",
            "target_entity": "api-container",
        })
        assert plan.risk_class == RC_2
        assert plan.status == "pending_approval"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == "restart_container"

    @pytest.mark.asyncio
    async def test_rotate_certificate_is_rc3(self, engine: RemediationEngine) -> None:
        plan = await engine.propose({
            "type": "cert_expiry",
            "target_entity": "web-cert",
        })
        assert plan.risk_class == RC_3
        assert plan.status == "pending_approval"

    @pytest.mark.asyncio
    async def test_disk_cleanup_is_rc2(self, engine: RemediationEngine) -> None:
        plan = await engine.propose({
            "type": "high_disk_usage",
            "target_entity": "hz.113:/var",
            "params": {"threshold_pct": 90},
        })
        assert plan.risk_class == RC_2
        assert plan.actions[0].action_type == "clear_disk_space"

    @pytest.mark.asyncio
    async def test_gpu_rebalance_is_rc3(self, engine: RemediationEngine) -> None:
        plan = await engine.propose({
            "type": "gpu_imbalance",
            "target_entity": "gpu-cluster",
        })
        assert plan.risk_class == RC_3

    @pytest.mark.asyncio
    async def test_security_alert_is_rc2(self, engine: RemediationEngine) -> None:
        plan = await engine.propose({
            "type": "security_alert",
            "target_entity": "firewall-1",
            "severity": "high",
        })
        assert plan.risk_class == RC_2
        assert plan.actions[0].action_type == "alert_escalate"

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_rich_context_increases_confidence(
        self, engine: RemediationEngine
    ) -> None:
        sparse = await engine.propose({"type": "container_crash", "target_entity": "x"})
        rich = await engine.propose({
            "type": "container_crash",
            "target_entity": "x",
            "source": "agent-hz113",
            "evidence": {"crash_count": 5},
            "severity": "critical",
        })
        assert rich.confidence > sparse.confidence

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_rc1_with_rich_context_auto_approved(self, engine: RemediationEngine) -> None:
        plan = await engine.propose({
            "type": "info_event",
            "target_entity": "x",
            "source": "agent-hz113",
            "evidence": {"detail": "routine check"},
            "severity": "low",
        })
        assert plan.status == "auto_approved"

    @pytest.mark.asyncio
    async def test_plan_has_valid_ids(self, engine: RemediationEngine) -> None:
        plan = await engine.propose({"type": "container_crash", "target_entity": "x"})
        assert plan.plan_id
        assert plan.insight_id
        assert plan.created_at

    # ------------------------------------------------------------------
    # Action derivation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_llm_latency_produces_restart_engine(
        self, engine: RemediationEngine
    ) -> None:
        plan = await engine.propose({
            "type": "llm_latency_spike",
            "target_entity": "vllm-reasoning",
        })
        assert plan.actions[0].action_type == "restart_llm_engine"
        assert plan.risk_class == RC_3

    @pytest.mark.asyncio
    async def test_unknown_type_falls_back_to_log(
        self, engine: RemediationEngine
    ) -> None:
        plan = await engine.propose({
            "type": "completely_new_event",
            "target_entity": "something",
        })
        assert plan.actions[0].action_type == "log_observation"
        assert plan.risk_class == RC_1
