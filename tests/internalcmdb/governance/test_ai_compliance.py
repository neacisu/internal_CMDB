"""Tests for internalcmdb.governance.ai_compliance."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.governance.ai_compliance import (
    AIComplianceManager,
    AISystemEntry,
    _parse_entity_uuid,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager_no_session() -> AIComplianceManager:
    return AIComplianceManager(session=None)


def _make_manager_with_session() -> tuple[AIComplianceManager, AsyncMock]:
    session = AsyncMock()
    mgr = AIComplianceManager(session=session)
    return mgr, session


# ---------------------------------------------------------------------------
# Tests: AISystemEntry dataclass
# ---------------------------------------------------------------------------


class TestAISystemEntry:
    def test_entry_creation(self) -> None:
        entry = AISystemEntry(
            system_name="Test System",
            risk_level="limited",
            purpose="testing",
            data_types=["host_facts"],
            model_ids=["model-1"],
            deployed_since="2026-01-01",
            owner_team="platform",
            human_oversight_level="partial",
        )
        assert entry.system_name == "Test System"
        assert entry.risk_level == "limited"
        assert entry.last_audit is None

    def test_entry_with_last_audit(self) -> None:
        entry = AISystemEntry(
            system_name="High Risk System",
            risk_level="high",
            purpose="remediation",
            data_types=["host_state"],
            model_ids=["model-2"],
            deployed_since="2026-03-01",
            owner_team="platform",
            human_oversight_level="full",
            last_audit="2026-03-15",
        )
        assert entry.last_audit == "2026-03-15"


# ---------------------------------------------------------------------------
# Tests: _parse_entity_uuid helper
# ---------------------------------------------------------------------------


class TestParseEntityUUID:
    def test_valid_uuid_parsed(self) -> None:
        uid = str(uuid.uuid4())
        result = _parse_entity_uuid(uid)
        assert result is not None
        assert isinstance(result, uuid.UUID)

    def test_invalid_uuid_returns_none(self) -> None:
        result = _parse_entity_uuid("not-a-uuid")
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        result = _parse_entity_uuid("")
        assert result is None

    def test_uuid_with_whitespace_parsed(self) -> None:
        uid = str(uuid.uuid4())
        result = _parse_entity_uuid(f"  {uid}  ")
        assert result is not None


# ---------------------------------------------------------------------------
# Tests: AIComplianceManager — inventory (no session)
# ---------------------------------------------------------------------------


class TestGetAIInventoryNoSession:
    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self) -> None:
        mgr = _make_manager_no_session()
        inventory = await mgr.get_ai_inventory()

        assert isinstance(inventory, list)
        assert len(inventory) >= 1
        for item in inventory:
            assert isinstance(item, dict)
            assert "system_name" in item
            assert "risk_level" in item

    @pytest.mark.asyncio
    async def test_inventory_contains_expected_systems(self) -> None:
        mgr = _make_manager_no_session()
        inventory = await mgr.get_ai_inventory()

        names = [item["system_name"] for item in inventory]
        assert "Self-Healing Remediation Engine" in names
        assert "Guard Gate (LLM Guard)" in names

    @pytest.mark.asyncio
    async def test_high_risk_system_present(self) -> None:
        mgr = _make_manager_no_session()
        inventory = await mgr.get_ai_inventory()

        high_risk = [item for item in inventory if item["risk_level"] == "high"]
        assert len(high_risk) >= 1


# ---------------------------------------------------------------------------
# Tests: AIComplianceManager — inventory (with session)
# ---------------------------------------------------------------------------


class TestGetAIInventoryWithSession:
    @pytest.mark.asyncio
    async def test_enriches_inventory_with_call_counts(self) -> None:
        mgr, session = _make_manager_with_session()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("Qwen/QwQ-32B-AWQ", 150),
            ("qwen3-embedding-8b-q5km", 50),
        ]
        session.execute = AsyncMock(return_value=mock_result)

        inventory = await mgr.get_ai_inventory()

        assert isinstance(inventory, list)
        for item in inventory:
            assert "llm_calls_last_30d" in item
            assert "llm_calls_by_model_30d" in item

    @pytest.mark.asyncio
    async def test_db_error_returns_inventory_without_counts(self) -> None:
        from sqlalchemy.exc import ProgrammingError

        mgr, session = _make_manager_with_session()
        session.execute = AsyncMock(
            side_effect=ProgrammingError("relation not found", {}, None)
        )

        inventory = await mgr.get_ai_inventory()

        assert isinstance(inventory, list)
        assert len(inventory) >= 1
        for item in inventory:
            assert item.get("llm_calls_last_30d", 0) == 0


# ---------------------------------------------------------------------------
# Tests: check_article_52_transparency
# ---------------------------------------------------------------------------


class TestCheckArticle52:
    def test_returns_dict_with_required_keys(self) -> None:
        mgr = _make_manager_no_session()
        result = mgr.check_article_52_transparency()

        assert "overall_compliant" in result
        assert "systems" in result
        assert isinstance(result["systems"], list)

    def test_all_systems_have_fields(self) -> None:
        mgr = _make_manager_no_session()
        result = mgr.check_article_52_transparency()

        for sys in result["systems"]:
            assert "system_name" in sys
            assert "transparency_marker" in sys
            assert "purpose_documented" in sys
            assert "risk_classified" in sys

    def test_overall_compliant_is_bool(self) -> None:
        mgr = _make_manager_no_session()
        result = mgr.check_article_52_transparency()
        assert isinstance(result["overall_compliant"], bool)


# ---------------------------------------------------------------------------
# Tests: check_article_15
# ---------------------------------------------------------------------------


class TestCheckArticle15:
    def test_returns_dict_with_keys(self) -> None:
        mgr = _make_manager_no_session()
        result = mgr.check_article_15()

        assert "overall_compliant" in result
        assert "high_risk_systems" in result
        assert isinstance(result["high_risk_systems"], list)

    def test_high_risk_systems_have_fields(self) -> None:
        mgr = _make_manager_no_session()
        result = mgr.check_article_15()

        for hr in result["high_risk_systems"]:
            assert "system_name" in hr
            assert "has_recent_audit" in hr
            assert "full_human_oversight" in hr


# ---------------------------------------------------------------------------
# Tests: compliance schedule
# ---------------------------------------------------------------------------


class TestComplianceSchedule:
    def test_record_then_not_overdue(self) -> None:
        mgr = _make_manager_no_session()
        mgr.record_compliance_check()
        assert not mgr.is_compliance_check_overdue()

    def test_initially_overdue_or_false(self) -> None:
        mgr = _make_manager_no_session()
        result = mgr.is_compliance_check_overdue()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Tests: generate_compliance_report
# ---------------------------------------------------------------------------


class TestGenerateComplianceReport:
    @pytest.mark.asyncio
    async def test_report_is_string(self) -> None:
        mgr = _make_manager_no_session()

        with patch.object(mgr, "check_article_12", new=AsyncMock(return_value={
            "audit_trail": True,
            "decision_logging": True,
            "model_versioning": True,
            "data_lineage": True,
            "hitl_feedback": True,
            "overall_compliant": True,
        })):
            report = await mgr.generate_compliance_report()

        assert isinstance(report, str)
        assert len(report) > 100

    @pytest.mark.asyncio
    async def test_report_contains_article_sections(self) -> None:
        mgr = _make_manager_no_session()

        with patch.object(mgr, "check_article_12", new=AsyncMock(return_value={
            "audit_trail": True,
            "decision_logging": True,
            "model_versioning": True,
            "data_lineage": True,
            "hitl_feedback": True,
            "overall_compliant": True,
        })):
            report = await mgr.generate_compliance_report()

        assert "Article" in report or "EU AI Act" in report
        assert "Article 9" in report or "Risk Management" in report

    @pytest.mark.asyncio
    async def test_report_contains_overall_assessment(self) -> None:
        mgr = _make_manager_no_session()

        with patch.object(mgr, "check_article_12", new=AsyncMock(return_value={
            "audit_trail": True,
            "decision_logging": True,
            "model_versioning": True,
            "data_lineage": True,
            "hitl_feedback": True,
            "overall_compliant": True,
        })):
            report = await mgr.generate_compliance_report()

        assert "Overall Assessment" in report or "COMPLIANT" in report or "REVIEW NEEDED" in report
