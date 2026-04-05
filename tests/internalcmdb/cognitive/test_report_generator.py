"""Teste pentru ReportGenerator (F2.5) — fleet, security, capacity reports."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.cognitive.report_generator import ReportGenerator, _truncate_value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm(analysis_text: str = "LLM analysis text.") -> MagicMock:
    llm = MagicMock()
    llm.reason = AsyncMock(return_value={
        "choices": [{"message": {"content": analysis_text}}],
    })
    llm.guard_output = AsyncMock(return_value={"is_valid": True})
    return llm


def _host_row(
    host_id: str = "h-1",
    host_code: str = "HOST-01",
    hostname: str = "web01.example.com",
    lifecycle_status: str = "active",
) -> MagicMock:
    row = MagicMock()
    row._mapping = {
        "host_id": host_id,
        "host_code": host_code,
        "hostname": hostname,
        "lifecycle_status": lifecycle_status,
    }
    return row


def _service_row(
    svc_id: str = "svc-1",
    code: str = "SVC-01",
    name: str = "postgres",
    is_active: bool = True,
) -> MagicMock:
    row = MagicMock()
    row._mapping = {
        "shared_service_id": svc_id,
        "service_code": code,
        "name": name,
        "is_active": is_active,
    }
    return row


def _fact_row(
    namespace: str = "cpu",
    key: str = "usage_percent",
    value: Any = {"value": 72},
    entity_id: str = "host-1",
) -> MagicMock:
    row = MagicMock()
    row._mapping = {
        "fact_namespace": namespace,
        "fact_key": key,
        "fact_value_jsonb": value,
        "entity_id": entity_id,
        "observed_at": "2024-06-01T10:00:00",
    }
    return row


def _make_session(
    hosts: list | None = None,
    services: list | None = None,
    facts: list | None = None,
) -> MagicMock:
    session = MagicMock()
    call_count = 0

    async def execute_se(stmt, params=None):
        await asyncio.sleep(0)
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.all.return_value = hosts or []
        elif call_count == 2:
            result.all.return_value = services or []
        else:
            result.all.return_value = facts or []
        return result

    session.execute = execute_se
    return session


# ---------------------------------------------------------------------------
# generate_fleet_report
# ---------------------------------------------------------------------------


class TestGenerateFleetReport:
    @pytest.mark.asyncio
    async def test_fleet_report_contains_header(self) -> None:
        session = _make_session(hosts=[], services=[], facts=[])
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_fleet_report()
        assert "# Fleet Health Report" in report

    @pytest.mark.asyncio
    async def test_fleet_report_includes_host_count(self) -> None:
        hosts = [_host_row(host_code=f"H-{i}", hostname=f"h{i}.local") for i in range(3)]
        session = _make_session(hosts=hosts, services=[], facts=[])
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_fleet_report()
        assert "3" in report

    @pytest.mark.asyncio
    async def test_fleet_report_llm_analysis_included(self) -> None:
        session = _make_session()
        gen = ReportGenerator(_make_llm(analysis_text="All systems green."), session)
        report = await gen.generate_fleet_report()
        assert "All systems green." in report

    @pytest.mark.asyncio
    async def test_fleet_report_no_hosts_shows_placeholder(self) -> None:
        session = _make_session(hosts=[], services=[], facts=[])
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_fleet_report()
        assert "_No hosts found._" in report

    @pytest.mark.asyncio
    async def test_fleet_report_counts_active_hosts(self) -> None:
        hosts = [
            _host_row(host_code="H-1", lifecycle_status="active"),
            _host_row(host_code="H-2", lifecycle_status="decommissioned"),
        ]
        session = _make_session(hosts=hosts, services=[], facts=[])
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_fleet_report()
        assert "Active Hosts" in report

    @pytest.mark.asyncio
    async def test_fleet_report_llm_failure_graceful(self) -> None:
        llm = _make_llm()
        llm.reason = AsyncMock(side_effect=RuntimeError("LLM down"))
        session = _make_session()
        gen = ReportGenerator(llm, session)
        report = await gen.generate_fleet_report()
        assert "# Fleet Health Report" in report
        assert "unavailable" in report.lower()


# ---------------------------------------------------------------------------
# generate_security_report
# ---------------------------------------------------------------------------


class TestGenerateSecurityReport:
    @pytest.mark.asyncio
    async def test_security_report_contains_header(self) -> None:
        session = _make_session(hosts=[], services=[], facts=[])
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_security_report()
        assert "# Security Posture Report" in report

    @pytest.mark.asyncio
    async def test_security_report_critical_count(self) -> None:
        facts = [_fact_row(namespace="security", key="critical_vuln")]
        session = _make_session(hosts=[], services=[], facts=facts)
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_security_report()
        assert "Critical Findings" in report

    @pytest.mark.asyncio
    async def test_security_report_no_findings_placeholder(self) -> None:
        session = _make_session(hosts=[], services=[], facts=[])
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_security_report()
        assert "_No security observations found._" in report

    @pytest.mark.asyncio
    async def test_security_report_includes_recommendations(self) -> None:
        session = _make_session()
        gen = ReportGenerator(_make_llm(analysis_text="Patch your servers."), session)
        report = await gen.generate_security_report()
        assert "Patch your servers." in report


# ---------------------------------------------------------------------------
# generate_capacity_report
# ---------------------------------------------------------------------------


class TestGenerateCapacityReport:
    @pytest.mark.asyncio
    async def test_capacity_report_contains_header(self) -> None:
        session = _make_session(hosts=[], services=[], facts=[])
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_capacity_report()
        assert "# Capacity Planning Report" in report

    @pytest.mark.asyncio
    async def test_capacity_report_no_data_placeholder(self) -> None:
        session = _make_session(hosts=[], services=[], facts=[])
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_capacity_report()
        assert "_No capacity data available._" in report

    @pytest.mark.asyncio
    async def test_capacity_report_facts_included(self) -> None:
        session = MagicMock()
        call_n = 0

        async def execute_se(stmt, params=None):
            await asyncio.sleep(0)
            nonlocal call_n
            call_n += 1
            result = MagicMock()
            if call_n == 1:
                result.all.return_value = []
            else:
                result.all.return_value = [_fact_row(namespace="cpu", key="usage_percent")]
            return result

        session.execute = execute_se
        gen = ReportGenerator(_make_llm(), session)
        report = await gen.generate_capacity_report()
        assert "cpu.usage_percent" in report

    @pytest.mark.asyncio
    async def test_capacity_report_growth_trends_from_llm(self) -> None:
        session = _make_session()
        gen = ReportGenerator(_make_llm(analysis_text="Disk growing at 5%/month."), session)
        report = await gen.generate_capacity_report()
        assert "Disk growing at 5%/month." in report


# ---------------------------------------------------------------------------
# _truncate_value
# ---------------------------------------------------------------------------


class TestTruncateValue:
    def test_short_value_unchanged(self) -> None:
        assert _truncate_value("short") == "short"

    def test_long_value_truncated(self) -> None:
        long_val = "x" * 200
        result = _truncate_value(long_val, max_len=50)
        assert len(result) <= 50
        assert result.endswith("…")

    def test_dict_converted_to_string(self) -> None:
        result = _truncate_value({"key": "value"})
        assert isinstance(result, str)
