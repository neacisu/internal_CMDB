"""F2.5 — Report Generator: LLM-powered markdown reports for fleet, security, and capacity.

Queries the InternalCMDB database for live metrics and entity state, assembles
a data payload, and uses the reasoning LLM to produce professional markdown
reports.

Usage::

    from internalcmdb.cognitive.report_generator import ReportGenerator

    gen = ReportGenerator(llm_client, db_session)
    md = await gen.generate_fleet_report()
    print(md)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.llm.client import LLMClient
from internalcmdb.models.discovery import ObservedFact
from internalcmdb.models.registry import Host, SharedService
from internalcmdb.models.taxonomy import TaxonomyTerm

logger = logging.getLogger(__name__)

_REPORT_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S UTC"


# ---------------------------------------------------------------------------
# Templates (variable substitution via str.format_map)
# ---------------------------------------------------------------------------

_FLEET_TEMPLATE = """\
# Fleet Health Report

**Generated:** {timestamp}

## Summary

| Metric | Value |
|--------|-------|
| Total Hosts | {total_hosts} |
| Active Hosts | {active_hosts} |
| Total Services | {total_services} |
| Active Services | {active_services} |

## Host Inventory

{host_details}

## Observations

{observations}

## LLM Analysis

{llm_analysis}
"""

_SECURITY_TEMPLATE = """\
# Security Posture Report

**Generated:** {timestamp}

## Summary

| Metric | Value |
|--------|-------|
| Hosts Audited | {hosts_audited} |
| Security Facts | {security_facts_count} |
| Critical Findings | {critical_count} |

## Security Observations

{security_observations}

## Risk Assessment

{risk_assessment}

## Recommendations

{recommendations}
"""

_CAPACITY_TEMPLATE = """\
# Capacity Planning Report

**Generated:** {timestamp}

## Summary

| Metric | Value |
|--------|-------|
| Total Hosts | {total_hosts} |
| Capacity Facts | {capacity_facts_count} |

## Resource Utilisation

{resource_utilisation}

## Growth Trends

{growth_trends}

## Capacity Recommendations

{capacity_recommendations}
"""


class ReportGenerator:
    """Generate markdown reports using LLM reasoning over CMDB data.

    Args:
        llm:     An :class:`LLMClient` instance for reasoning calls.
        session: An ``AsyncSession`` connected to the InternalCMDB database.
    """

    def __init__(self, llm: LLMClient, session: AsyncSession) -> None:
        self._llm = llm
        self._session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_fleet_report(self) -> str:
        """Generate a comprehensive fleet health report in markdown."""
        ts = datetime.now(tz=UTC).strftime(_REPORT_TIMESTAMP_FMT)

        hosts = await self._fetch_hosts()
        services = await self._fetch_services()
        recent_facts = await self._fetch_recent_facts(limit=50)

        host_details = self._format_host_table(hosts)
        observations = self._format_facts_summary(recent_facts)

        data_summary = (
            f"Fleet: {len(hosts)} hosts, {len(services)} services.\n"
            f"Recent observations:\n{observations}"
        )
        llm_analysis = await self._llm_analyze(
            "Analyse the fleet health based on the data below. "
            "Identify any hosts that may need attention, services at risk, "
            "and overall fleet readiness. Be concise and actionable.",
            data_summary,
        )

        return _FLEET_TEMPLATE.format_map(
            {
                "timestamp": ts,
                "total_hosts": len(hosts),
                "active_hosts": sum(1 for h in hosts if h.get("is_active")),
                "total_services": len(services),
                "active_services": sum(1 for s in services if s.get("is_active")),
                "host_details": host_details,
                "observations": observations or "_No recent observations._",
                "llm_analysis": llm_analysis,
            }
        )

    async def generate_security_report(self) -> str:
        """Generate a security posture report in markdown."""
        ts = datetime.now(tz=UTC).strftime(_REPORT_TIMESTAMP_FMT)

        hosts = await self._fetch_hosts()
        security_facts = await self._fetch_facts_by_namespace(
            namespaces=["security", "sshd", "tls", "firewall"],
            limit=100,
        )

        security_observations = self._format_facts_summary(security_facts)
        critical_count = sum(
            1
            for f in security_facts
            if f.get("fact_key", "").startswith("critical")
            or "vulnerability" in f.get("fact_key", "").lower()
        )

        data_summary = (
            f"Security audit scope: {len(hosts)} hosts.\n"
            f"Security-related observations ({len(security_facts)}):\n"
            f"{security_observations}"
        )

        risk_assessment = await self._llm_analyze(
            "Perform a risk assessment based on the security observations below. "
            "Rate overall risk as LOW / MEDIUM / HIGH / CRITICAL. "
            "List specific risks with affected entities.",
            data_summary,
        )

        recommendations = await self._llm_analyze(
            "Based on the security observations, provide prioritised "
            "remediation recommendations. Format as a numbered list.",
            data_summary,
        )

        return _SECURITY_TEMPLATE.format_map(
            {
                "timestamp": ts,
                "hosts_audited": len(hosts),
                "security_facts_count": len(security_facts),
                "critical_count": critical_count,
                "security_observations": security_observations
                or "_No security observations found._",
                "risk_assessment": risk_assessment,
                "recommendations": recommendations,
            }
        )

    async def generate_capacity_report(self) -> str:
        """Generate a capacity planning report in markdown."""
        ts = datetime.now(tz=UTC).strftime(_REPORT_TIMESTAMP_FMT)

        hosts = await self._fetch_hosts()
        capacity_facts = await self._fetch_facts_by_namespace(
            namespaces=["cpu", "memory", "disk", "filesystem", "storage"],
            limit=100,
        )

        resource_utilisation = self._format_facts_summary(capacity_facts)

        data_summary = (
            f"Capacity scope: {len(hosts)} hosts.\n"
            f"Resource observations ({len(capacity_facts)}):\n"
            f"{resource_utilisation}"
        )

        growth_trends = await self._llm_analyze(
            "Analyse resource utilisation trends from the data below. "
            "Identify any hosts approaching capacity limits. "
            "Estimate when thresholds might be breached if trends continue.",
            data_summary,
        )

        capacity_recommendations = await self._llm_analyze(
            "Based on the capacity data, provide actionable recommendations "
            "for scaling, rebalancing, or decommissioning resources. "
            "Prioritise by urgency.",
            data_summary,
        )

        return _CAPACITY_TEMPLATE.format_map(
            {
                "timestamp": ts,
                "total_hosts": len(hosts),
                "capacity_facts_count": len(capacity_facts),
                "resource_utilisation": resource_utilisation or "_No capacity data available._",
                "growth_trends": growth_trends,
                "capacity_recommendations": capacity_recommendations,
            }
        )

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def _fetch_hosts(self) -> list[dict[str, Any]]:
        lifecycle_alias = TaxonomyTerm.__table__.alias("lifecycle_term")
        stmt = (
            select(
                Host.host_id,
                Host.host_code,
                Host.hostname,
                lifecycle_alias.c.term_code.label("lifecycle_status"),
            )
            .join(
                lifecycle_alias,
                lifecycle_alias.c.taxonomy_term_id == Host.lifecycle_term_id,
            )
            .order_by(Host.host_code)
        )

        result = await self._session.execute(stmt)
        rows: list[dict[str, Any]] = []
        _active_codes = {"active", "degraded"}
        for r in result.all():
            row = dict(r._mapping)
            row["is_active"] = row.get("lifecycle_status") in _active_codes
            rows.append(row)
        return rows

    async def _fetch_services(self) -> list[dict[str, Any]]:
        stmt = select(
            SharedService.shared_service_id,
            SharedService.service_code,
            SharedService.name,
            SharedService.is_active,
        ).order_by(SharedService.service_code)

        result = await self._session.execute(stmt)
        return [dict(r._mapping) for r in result.all()]

    async def _fetch_recent_facts(self, limit: int = 50) -> list[dict[str, Any]]:
        stmt = (
            select(
                ObservedFact.fact_namespace,
                ObservedFact.fact_key,
                ObservedFact.fact_value_jsonb,
                ObservedFact.entity_id,
                ObservedFact.observed_at,
            )
            .order_by(ObservedFact.observed_at.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return [dict(r._mapping) for r in result.all()]

    async def _fetch_facts_by_namespace(
        self,
        namespaces: list[str],
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                ObservedFact.fact_namespace,
                ObservedFact.fact_key,
                ObservedFact.fact_value_jsonb,
                ObservedFact.entity_id,
                ObservedFact.observed_at,
            )
            .where(ObservedFact.fact_namespace.in_(namespaces))
            .order_by(ObservedFact.observed_at.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return [dict(r._mapping) for r in result.all()]

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_host_table(hosts: list[dict[str, Any]]) -> str:
        if not hosts:
            return "_No hosts found._"

        lines = ["| Host Code | Hostname | Active |", "|-----------|----------|--------|"]
        for h in hosts:
            active = "Yes" if h.get("is_active") else "No"
            lines.append(f"| {h.get('host_code', '?')} | {h.get('hostname', '?')} | {active} |")
        return "\n".join(lines)

    @staticmethod
    def _format_facts_summary(facts: list[dict[str, Any]]) -> str:
        if not facts:
            return ""

        lines: list[str] = []
        for f in facts[:30]:
            ns = f.get("fact_namespace", "?")
            key = f.get("fact_key", "?")
            val = f.get("fact_value_jsonb", {})
            entity = str(f.get("entity_id", "?"))[:12]
            lines.append(f"- **{ns}.{key}** (entity: {entity}…): {_truncate_value(val)}")

        if len(facts) > 30:  # noqa: PLR2004
            lines.append(f"- _… and {len(facts) - 30} more observations._")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # LLM integration
    # ------------------------------------------------------------------

    async def _llm_analyze(self, instruction: str, data: str) -> str:
        """Send data + instruction to the reasoning LLM and return the response text.

        Performs LLM Guard output scanning when available to redact sensitive
        information before including the analysis in the report.
        """
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are the InternalCMDB cognitive brain generating an infrastructure report. "
                    "Be precise, data-driven, and actionable. Use markdown formatting. "
                    "NEVER include credentials, tokens, passwords, or private keys in the output."
                ),
            },
            {
                "role": "user",
                "content": f"{instruction}\n\n--- DATA ---\n{data}\n--- END DATA ---",
            },
        ]

        try:
            response = await self._llm.reason(messages, temperature=0.2, max_tokens=1500)
            choices = response.get("choices", [])
            if not choices:
                return "_The model returned an empty response._"
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return "_Analysis unavailable._"
        except Exception:
            logger.exception("LLM analysis call failed")
            return "_LLM analysis unavailable due to a backend error._"

        try:
            guard_result = await self._llm.guard_output(
                prompt=instruction,
                output=content,
            )
            if guard_result.get("is_valid") is False:
                sanitized = guard_result.get("sanitized_output", "")
                if sanitized:
                    logger.warning("Guard redacted sensitive content from report section")
                    return sanitized
                return "_Analysis redacted — contained sensitive information._"
        except Exception:
            logger.debug("Guard output scan unavailable — returning raw analysis")

        return content


def _truncate_value(val: Any, max_len: int = 120) -> str:
    s = str(val)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"
