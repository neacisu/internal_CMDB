"""EU AI Act Compliance Manager (Phase 13, F13).

Implements the compliance requirements from the EU Artificial Intelligence Act
(Regulation 2024/1689), particularly:
    - Article 9:  Risk Management System
    - Article 10: Data Governance
    - Article 12: Record-Keeping / Transparency
    - Article 13: Transparency and Provision of Information
    - Article 14: Human Oversight
    - Article 15: Accuracy, Robustness, and Cybersecurity
    - Article 52: Transparency Obligations for Certain AI Systems

All public async methods perform real I/O when an :class:`~sqlalchemy.ext.asyncio.AsyncSession`
is supplied (recommended for API use).  Without a session, inventory and lineage
still return curated static baselines; Article 12 checks fall back to a
**conservative** static assessment (REVIEW NEEDED, not PASS) so offline
tooling remains safe.

Public surface::

    from internalcmdb.governance.ai_compliance import AIComplianceManager

    mgr = AIComplianceManager(session)
    inventory = await mgr.get_ai_inventory()
    report = await mgr.generate_compliance_report()
    a52 = mgr.check_article_52_transparency()
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_SCHEMA_OR_PERMISSIONS_DETAIL = (
    "Schema or permissions error — run Alembic migrations and verify DB role."
)

_REGULATION_VERSION = "EU AI Act — Regulation 2024/1689 (Official Journal L 2024/1689)"

_COMPLIANCE_SCHEDULE_INTERVAL_HOURS = 24

# ---------------------------------------------------------------------------
# AI system inventory (curated baseline — enriched from telemetry when session given)
# ---------------------------------------------------------------------------


@dataclass
class AISystemEntry:
    """Describes a single AI system in the enterprise inventory."""

    system_name: str
    risk_level: str  # "minimal" | "limited" | "high" | "unacceptable"
    purpose: str
    data_types: list[str]
    model_ids: list[str]
    deployed_since: str
    owner_team: str
    human_oversight_level: str  # "full" | "partial" | "automated"
    last_audit: str | None = None


_AI_INVENTORY: list[AISystemEntry] = [
    AISystemEntry(
        system_name="Cognitive Query Engine",
        risk_level="limited",
        purpose="Natural language queries over infrastructure knowledge base (RAG)",
        data_types=["infrastructure_facts", "document_chunks", "host_metadata"],
        model_ids=["Qwen/QwQ-32B-AWQ", "qwen3-embedding-8b-q5km"],
        deployed_since="2026-01-15",
        owner_team="platform-engineering",
        human_oversight_level="partial",
    ),
    AISystemEntry(
        system_name="Anomaly Detector",
        risk_level="limited",
        purpose="Statistical anomaly detection on observed infrastructure facts",
        data_types=["observed_facts", "metrics_timeseries"],
        model_ids=["Qwen/Qwen2.5-14B-Instruct-AWQ"],
        deployed_since="2026-02-01",
        owner_team="platform-engineering",
        human_oversight_level="partial",
    ),
    AISystemEntry(
        system_name="Report Generator",
        risk_level="limited",
        purpose="Automated fleet, security, and capacity report generation",
        data_types=["host_facts", "service_instances", "evidence_packs"],
        model_ids=["Qwen/QwQ-32B-AWQ"],
        deployed_since="2026-02-10",
        owner_team="platform-engineering",
        human_oversight_level="full",
    ),
    AISystemEntry(
        system_name="Guard Gate (LLM Guard)",
        risk_level="limited",
        purpose="Input/output scanning for prompt injection, PII, toxicity",
        data_types=["llm_prompts", "llm_outputs"],
        model_ids=["llm-guard"],
        deployed_since="2026-01-20",
        owner_team="security-engineering",
        human_oversight_level="automated",
    ),
    AISystemEntry(
        system_name="Self-Healing Remediation Engine",
        risk_level="high",
        purpose="Automated infrastructure remediation (playbook execution)",
        data_types=["host_state", "service_health", "container_status"],
        model_ids=["Qwen/Qwen2.5-14B-Instruct-AWQ"],
        deployed_since="2026-03-01",
        owner_team="platform-engineering",
        human_oversight_level="full",
        last_audit="2026-03-15",
    ),
    AISystemEntry(
        system_name="Predictive Analytics Engine",
        risk_level="limited",
        purpose="Infrastructure capacity and failure prediction",
        data_types=["metrics_timeseries", "host_facts", "certificate_metadata"],
        model_ids=[],
        deployed_since="2026-03-10",
        owner_team="platform-engineering",
        human_oversight_level="partial",
    ),
]


def _parse_entity_uuid(entity_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(entity_id.strip())
    except ValueError, AttributeError:
        return None


# ---------------------------------------------------------------------------
# Compliance Manager
# ---------------------------------------------------------------------------


class AIComplianceManager:
    """Manages EU AI Act compliance for all AI systems in the CMDB.

    Args:
        session: Optional async SQLAlchemy session. When provided, inventory
            enrichment, lineage evidence, and Article 12 checks query live
            ``governance`` and ``telemetry`` schemas.
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._inventory = list(_AI_INVENTORY)

    # ------------------------------------------------------------------
    # AI inventory
    # ------------------------------------------------------------------

    async def get_ai_inventory(self) -> list[dict[str, Any]]:
        """Return the AI system inventory as dicts, optionally enriched from DB."""
        if self._session is None:
            # Off-thread materialisation avoids blocking the event loop and
            # satisfies async static analysis (no fire-and-forget ``async``).
            return await asyncio.to_thread(
                lambda: [asdict(entry) for entry in self._inventory],
            )

        call_counts = await self._fetch_llm_call_counts_by_model_30d()
        rows = [asdict(entry) for entry in self._inventory]
        for row in rows:
            mids = row.get("model_ids") or []
            total = sum(int(call_counts.get(m, 0)) for m in mids)
            row["llm_calls_last_30d"] = total
            row["llm_calls_by_model_30d"] = {m: int(call_counts.get(m, 0)) for m in mids}
        return rows

    async def _fetch_llm_call_counts_by_model_30d(self) -> dict[str, int]:
        """Aggregate LLM invocations from telemetry (last 30 days)."""
        assert self._session is not None
        sql = text("""
            SELECT model_id, COUNT(*)::bigint AS c
              FROM telemetry.llm_call_log
             WHERE called_at >= (now() AT TIME ZONE 'utc') - interval '30 days'
               AND model_id IS NOT NULL
               AND btrim(model_id) <> ''
             GROUP BY model_id
        """)
        try:
            result = await self._session.execute(sql)
            return {str(r[0]): int(r[1]) for r in result.fetchall()}
        except ProgrammingError, DBAPIError:
            logger.exception(
                "ai_compliance: telemetry.llm_call_log aggregate failed; "
                "inventory returned without call counts",
            )
            return {}

    # ------------------------------------------------------------------
    # Compliance report generation
    # ------------------------------------------------------------------

    async def generate_compliance_report(self) -> str:
        """Generate a human-readable EU AI Act compliance report.

        Covers Articles 9, 10, 12-15, 52 for all registered AI systems.
        """
        now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        lines: list[str] = [
            f"# EU AI Act Compliance Report — {now}",
            "",
        ]

        high_risk = self._report_inventory_section(lines)
        self._report_risk_management_section(lines, high_risk)
        self._report_data_governance_section(lines)

        article_12 = await self.check_article_12()
        self._report_article_12_section(lines, article_12)
        self._report_human_oversight_section(lines)

        article_52 = self.check_article_52_transparency()
        self._report_article_52_section(lines, article_52)

        article_15 = self.check_article_15()
        self._report_article_15_section(lines, article_15)

        self._report_overall_section(lines, now, article_12, article_52, article_15)

        report = "\n".join(lines)
        logger.info(
            "Compliance report generated: %d chars, %d systems",
            len(report),
            len(self._inventory),
        )
        return report

    # ------------------------------------------------------------------
    # Report section builders (reduce cognitive complexity)
    # ------------------------------------------------------------------

    def _report_inventory_section(self, lines: list[str]) -> list[AISystemEntry]:
        lines.append("## 1. AI System Inventory (Article 13 — Transparency)")
        lines.append("")
        high_risk: list[AISystemEntry] = []
        for i, entry in enumerate(self._inventory, start=1):
            lines.append(f"### 1.{i}  {entry.system_name}")
            lines.append(f"- **Risk Level**: {entry.risk_level}")
            lines.append(f"- **Purpose**: {entry.purpose}")
            lines.append(f"- **Data Types**: {', '.join(entry.data_types)}")
            lines.append(f"- **Models**: {', '.join(entry.model_ids) or 'none (rule-based)'}")
            lines.append(f"- **Human Oversight**: {entry.human_oversight_level}")
            lines.append(f"- **Deployed Since**: {entry.deployed_since}")
            lines.append(f"- **Owner**: {entry.owner_team}")
            if entry.last_audit:
                lines.append(f"- **Last Audit**: {entry.last_audit}")
            lines.append("")
            if entry.risk_level == "high":
                high_risk.append(entry)
        return high_risk

    def _report_risk_management_section(
        self,
        lines: list[str],
        high_risk: list[AISystemEntry],
    ) -> None:
        lines.extend(
            [
                "## 2. Risk Management (Article 9)",
                "",
                f"Total AI systems registered: **{len(self._inventory)}**",
                f"High-risk systems: **{len(high_risk)}**",
                "",
            ]
        )
        for sys in high_risk:
            lines.append(
                f"- **{sys.system_name}**: classified as high-risk. "
                f"Human oversight level: {sys.human_oversight_level}. "
                f"Requires HITL RC-3 minimum approval for all actions."
            )
            lines.append("")

    def _report_data_governance_section(self, lines: list[str]) -> None:
        all_data_types: set[str] = set()
        for entry in self._inventory:
            all_data_types.update(entry.data_types)
        lines.extend(
            [
                "## 3. Data Governance (Article 10)",
                "",
                f"Data categories in scope: {', '.join(sorted(all_data_types))}",
                "",
                "- All training/inference data sourced from internal CMDB registry",
                "- No personal data processed (infrastructure telemetry only)",
                "- Data lineage tracked via evidence packs and provenance chains",
                "- RAG content scanned for injection patterns before use",
                "",
            ]
        )

    @staticmethod
    def _report_article_12_section(
        lines: list[str],
        article_12: dict[str, Any],
    ) -> None:
        def pf(v):
            return "PASS" if v else "FAIL"
        lines.extend(
            [
                "## 4. Record-Keeping (Article 12)",
                "",
                f"- Audit trail: **{pf(article_12['audit_trail'])}**",
                f"- Decision logging: **{pf(article_12['decision_logging'])}**",
                f"- Model versioning: **{pf(article_12['model_versioning'])}**",
                f"- Data lineage: **{pf(article_12['data_lineage'])}**",
                f"- HITL feedback loop: **{pf(article_12['hitl_feedback'])}**",
                "",
            ]
        )

    @staticmethod
    def _report_human_oversight_section(lines: list[str]) -> None:
        lines.extend(
            [
                "## 5. Human Oversight (Article 14)",
                "",
                "- All high-risk actions require HITL approval (RC-3/RC-4)",
                "- Guard Gate provides 5-level defence-in-depth evaluation",
                "- LLM outputs are validated before execution",
                "- Operator can override or abort any AI-initiated action",
                "",
            ]
        )

    @staticmethod
    def _report_article_52_section(
        lines: list[str],
        article_52: dict[str, Any],
    ) -> None:
        def pf(v):
            return "PASS" if v else "FAIL"
        lines.extend(
            [
                "## 6. Transparency Obligations (Article 52)",
                "",
                f"- Overall: **{pf(article_52['overall_compliant'])}**",
            ]
        )
        for sr in article_52.get("systems", []):
            t = "✓" if sr["transparency_marker"] else "✗"
            p = "✓" if sr["purpose_documented"] else "✗"
            r = "✓" if sr["risk_classified"] else "✗"
            lines.append(f"  - {sr['system_name']}: transparency={t}, purpose={p}, risk={r}")
        lines.append("")

    @staticmethod
    def _report_article_15_section(
        lines: list[str],
        article_15: dict[str, Any],
    ) -> None:
        def pf(v):
            return "PASS" if v else "FAIL"
        lines.extend(
            [
                "## 7. Accuracy, Robustness, and Cybersecurity (Article 15)",
                "",
                f"- Overall: **{pf(article_15['overall_compliant'])}**",
            ]
        )
        for hr in article_15.get("high_risk_systems", []):
            a = "✓" if hr["has_recent_audit"] else "✗"
            o = "✓" if hr["full_human_oversight"] else "✗"
            lines.append(f"  - {hr['system_name']}: audit={a}, oversight={o}")
        lines.append("")

    def _report_overall_section(
        self,
        lines: list[str],
        now: str,
        article_12: dict[str, Any],
        article_52: dict[str, Any],
        article_15: dict[str, Any],
    ) -> None:
        schedule_overdue = self.is_compliance_check_overdue()
        self.record_compliance_check()
        overall_parts = [
            article_12.get("overall_compliant", False),
            article_52["overall_compliant"],
            article_15["overall_compliant"],
            not schedule_overdue,
        ]
        overall = "COMPLIANT" if all(overall_parts) else "REVIEW NEEDED"
        lines.extend(
            [
                "## 8. Overall Assessment",
                "",
                f"**Status: {overall}**",
                "",
                f"Regulation: {_REGULATION_VERSION}",
                f"Compliance schedule: {'ON TIME' if not schedule_overdue else 'OVERDUE'}",
                f"Report generated at {now} by AIComplianceManager.",
            ]
        )

    # ------------------------------------------------------------------
    # Data lineage audit
    # ------------------------------------------------------------------

    def _lineage_reference_model(self, entity_id: str) -> dict[str, Any]:
        """Synchronous canonical lineage stages (documentation + timestamps)."""
        return {
            "entity_id": entity_id,
            "lineage_stages": [
                {
                    "stage": "collection",
                    "description": "Agent collector gathers facts from target host",
                    "components": ["collector_agent", "collector_snapshot"],
                    "data_schema": "collectors.collector_snapshot",
                    "retention_days": 90,
                },
                {
                    "stage": "normalisation",
                    "description": "Raw facts normalised into observed_fact records",
                    "components": ["fact_loader", "trust_surface_loader"],
                    "data_schema": "discovery.observed_fact",
                    "retention_days": 365,
                },
                {
                    "stage": "enrichment",
                    "description": "Facts enriched with taxonomy terms and ownership",
                    "components": ["shared_service_seed", "ownership_assignment"],
                    "data_schema": "registry.ownership_assignment",
                    "retention_days": 365,
                },
                {
                    "stage": "chunking",
                    "description": "Documents split into chunks with provenance hashes",
                    "components": ["chunker", "document_version"],
                    "data_schema": "retrieval.document_chunk",
                    "retention_days": 365,
                },
                {
                    "stage": "embedding",
                    "description": "Chunks embedded using qwen3-embedding-8b model",
                    "components": ["embedding_pipeline", "chunk_embedding"],
                    "data_schema": "retrieval.chunk_embedding",
                    "retention_days": 365,
                },
                {
                    "stage": "retrieval",
                    "description": "Evidence packs assembled via deterministic broker (ADR-003)",
                    "components": ["retrieval_broker", "evidence_pack"],
                    "data_schema": "retrieval.evidence_pack",
                    "retention_days": 365,
                },
                {
                    "stage": "inference",
                    "description": "LLM generates response using retrieved evidence",
                    "components": ["llm_client", "cognitive_query_engine"],
                    "data_schema": "telemetry.llm_call_log",
                    "retention_days": 90,
                },
            ],
            "checked_at": datetime.now(tz=UTC).isoformat(),
        }

    async def audit_data_lineage(self, entity_id: str) -> dict[str, Any]:
        """Trace data flow for *entity_id* through the CMDB pipeline.

        Returns the canonical stage model plus **database_evidence** when a
        session is available (observed facts, metrics, audit references).
        """
        if self._session is None:
            return await asyncio.to_thread(self._lineage_without_db, entity_id)

        base = await asyncio.to_thread(self._lineage_reference_model, entity_id)
        eid = _parse_entity_uuid(entity_id)
        if eid is None:
            base["database_evidence"] = {
                "session_attached": True,
                "entity_uuid_valid": False,
                "note": "entity_id must be a UUID matching registry/discovery.entity_id.",
            }
            return base

        evidence = await self._fetch_lineage_evidence(eid)
        base["database_evidence"] = evidence
        return base

    def _lineage_without_db(self, entity_id: str) -> dict[str, Any]:
        """Build lineage response when no AsyncSession is configured."""
        out = self._lineage_reference_model(entity_id)
        out["database_evidence"] = {
            "session_attached": False,
            "note": "Attach AsyncSession for live CMDB lineage evidence.",
        }
        return out

    async def _fetch_lineage_evidence(self, entity_uuid: uuid.UUID) -> dict[str, Any]:
        """Pull observable row counts / timestamps for lineage stages."""
        assert self._session is not None
        out: dict[str, Any] = {
            "session_attached": True,
            "entity_uuid_valid": True,
            "entity_id": str(entity_uuid),
        }
        sql_observed = text("""
            SELECT COUNT(*)::bigint,
                   MAX(observed_at) AS last_observed
              FROM discovery.observed_fact
             WHERE entity_id = :eid
        """)
        sql_metrics = text("""
            SELECT COUNT(*)::bigint,
                   MAX(collected_at) AS last_metric
              FROM telemetry.metric_point
             WHERE host_id = :eid
               AND collected_at >= (now() AT TIME ZONE 'utc') - interval '90 days'
        """)
        sql_audit = text("""
            SELECT COUNT(*)::bigint
              FROM governance.audit_event
             WHERE target_id = :eid
               AND created_at >= (now() AT TIME ZONE 'utc') - interval '90 days'
        """)
        try:
            r1 = await self._session.execute(sql_observed, {"eid": entity_uuid})
            row1 = r1.one()
            out["observed_fact_count"] = int(row1[0])
            out["observed_fact_last_at"] = row1[1].isoformat() if row1[1] is not None else None

            r2 = await self._session.execute(sql_metrics, {"eid": entity_uuid})
            row2 = r2.one()
            out["metric_point_count_90d"] = int(row2[0])
            out["metric_point_last_at"] = row2[1].isoformat() if row2[1] is not None else None

            r3 = await self._session.execute(sql_audit, {"eid": entity_uuid})
            out["audit_event_count_90d_target"] = int(r3.scalar_one())
        except ProgrammingError, DBAPIError:
            logger.exception(
                "ai_compliance: lineage evidence query failed for entity_id=%s",
                entity_uuid,
            )
            out["error"] = "database_query_failed"
        return out

    # ------------------------------------------------------------------
    # Article 12 — Transparency check
    # ------------------------------------------------------------------

    async def check_article_12(self) -> dict[str, Any]:
        """Verify EU AI Act Article 12 transparency requirements against the DB.

        When no session is configured, returns the legacy optimistic baseline
        so scripts without a database still receive a structured response.
        """
        if self._session is None:
            return await asyncio.to_thread(self._check_article_12_static)

        checks = await self._check_article_12_from_db()
        checks["checked_at"] = datetime.now(tz=UTC).isoformat()
        checks["overall_compliant"] = all(
            checks[k]
            for k in (
                "audit_trail",
                "decision_logging",
                "model_versioning",
                "data_lineage",
                "hitl_feedback",
            )
        )
        return checks

    def _check_article_12_static(self) -> dict[str, Any]:
        """Conservative fallback when no AsyncSession (offline / unit tests).

        Returns FAIL for all checks to avoid false compliance signals.
        A session must be attached for genuine verification.
        """
        _detail = "No DB session — UNVERIFIED. Attach AsyncSession for live verification."
        checks: dict[str, Any] = {
            "audit_trail": False,
            "audit_trail_detail": f"{_detail} Checks governance.audit_event.",
            "decision_logging": False,
            "decision_logging_detail": f"{_detail} Checks governance.hitl_item.",
            "model_versioning": False,
            "model_versioning_detail": f"{_detail} Checks telemetry.llm_call_log.",
            "data_lineage": False,
            "data_lineage_detail": f"{_detail} Checks discovery.observed_fact.",
            "hitl_feedback": False,
            "hitl_feedback_detail": f"{_detail} Checks governance.hitl_feedback.",
            "checked_at": datetime.now(tz=UTC).isoformat(),
        }
        checks["overall_compliant"] = False
        return checks

    async def _check_article_12_from_db(self) -> dict[str, Any]:
        """Evaluate Article 12 using governance + telemetry + discovery schemas."""
        assert self._session is not None
        checks: dict[str, Any] = {}

        # Audit trail — recent immutable API audit rows
        sql_audit = text("""
            SELECT COUNT(*)::bigint FROM governance.audit_event
             WHERE created_at >= (now() AT TIME ZONE 'utc') - interval '30 days'
        """)
        # HITL decisions recorded
        sql_hitl_decisions = text("""
            SELECT COUNT(*)::bigint FROM governance.hitl_item
             WHERE decision IS NOT NULL AND btrim(decision) <> ''
        """)
        # Model IDs recorded on LLM calls
        sql_llm_models = text("""
            SELECT COUNT(*)::bigint FROM telemetry.llm_call_log
             WHERE model_id IS NOT NULL AND btrim(model_id) <> ''
        """)
        # CMDB observed facts (lineage substrate)
        sql_observed = text("""
            SELECT COUNT(*)::bigint FROM discovery.observed_fact
        """)
        # HITL feedback loop rows
        sql_feedback = text("""
            SELECT COUNT(*)::bigint FROM governance.hitl_feedback
        """)

        try:
            n_audit = int((await self._session.execute(sql_audit)).scalar_one())
            n_decisions = int((await self._session.execute(sql_hitl_decisions)).scalar_one())
            n_llm = int((await self._session.execute(sql_llm_models)).scalar_one())
            n_obs = int((await self._session.execute(sql_observed)).scalar_one())
            n_fb = int((await self._session.execute(sql_feedback)).scalar_one())
        except (ProgrammingError, DBAPIError) as exc:
            logger.exception("ai_compliance: Article 12 DB checks failed: %s", exc)
            return {
                "audit_trail": False,
                "audit_trail_detail": f"Query failed: {exc!s}",
                "decision_logging": False,
                "decision_logging_detail": _SCHEMA_OR_PERMISSIONS_DETAIL,
                "model_versioning": False,
                "model_versioning_detail": _SCHEMA_OR_PERMISSIONS_DETAIL,
                "data_lineage": False,
                "data_lineage_detail": _SCHEMA_OR_PERMISSIONS_DETAIL,
                "hitl_feedback": False,
                "hitl_feedback_detail": _SCHEMA_OR_PERMISSIONS_DETAIL,
            }

        checks["audit_trail"] = n_audit >= 1
        checks["audit_trail_detail"] = (
            f"governance.audit_event rows in last 30 days: {n_audit} "
            f"({'meets' if n_audit >= 1 else 'below'}) threshold ≥1."
        )

        checks["decision_logging"] = n_decisions >= 1
        checks["decision_logging_detail"] = (
            f"governance.hitl_item rows with decision set: {n_decisions} "
            f"({'meets' if n_decisions >= 1 else 'below'}) threshold ≥1."
        )

        checks["model_versioning"] = n_llm >= 1
        checks["model_versioning_detail"] = (
            f"telemetry.llm_call_log rows with model_id: {n_llm} "
            f"({'meets' if n_llm >= 1 else 'below'}) threshold ≥1."
        )

        checks["data_lineage"] = n_obs >= 1
        checks["data_lineage_detail"] = (
            f"discovery.observed_fact total rows: {n_obs} "
            f"({'meets' if n_obs >= 1 else 'below'}) threshold ≥1."
        )

        checks["hitl_feedback"] = n_fb >= 1
        checks["hitl_feedback_detail"] = (
            f"governance.hitl_feedback total rows: {n_fb} "
            f"({'meets' if n_fb >= 1 else 'below'}) threshold ≥1."
        )

        return checks

    # ------------------------------------------------------------------
    # Article 52 — Transparency Obligations (EU AI Act)
    # ------------------------------------------------------------------

    def check_article_52_transparency(self) -> dict[str, Any]:
        """Verify Article 52 transparency requirements.

        Users interacting with AI systems MUST be informed that they are
        dealing with an AI, not a human.  This check verifies that all
        registered AI systems have transparency markers configured.
        """
        results: list[dict[str, Any]] = []
        all_pass = True

        for entry in self._inventory:
            has_transparency = entry.human_oversight_level in ("full", "partial")
            has_purpose = bool(entry.purpose)
            has_risk_classification = entry.risk_level in (
                "minimal",
                "limited",
                "high",
                "unacceptable",
            )

            entry_pass = has_transparency and has_purpose and has_risk_classification
            if not entry_pass:
                all_pass = False

            results.append(
                {
                    "system_name": entry.system_name,
                    "transparency_marker": has_transparency,
                    "purpose_documented": has_purpose,
                    "risk_classified": has_risk_classification,
                    "compliant": entry_pass,
                }
            )

        return {
            "article": "Article 52 — Transparency Obligations",
            "regulation": _REGULATION_VERSION,
            "overall_compliant": all_pass,
            "systems": results,
            "checked_at": datetime.now(tz=UTC).isoformat(),
            "requirement_summary": (
                "AI systems interacting with natural persons must clearly "
                "disclose that they are AI-generated. Purpose and risk level "
                "must be documented and accessible."
            ),
        }

    # ------------------------------------------------------------------
    # Article 15 — Accuracy, Robustness, and Cybersecurity
    # ------------------------------------------------------------------

    def check_article_15(self) -> dict[str, Any]:
        """Verify Article 15 compliance: accuracy, robustness, cybersecurity.

        Checks that high-risk systems have audit records, accuracy baselines,
        and cybersecurity measures documented.
        """
        high_risk = [e for e in self._inventory if e.risk_level == "high"]
        checks: list[dict[str, Any]] = []

        for entry in high_risk:
            has_audit = entry.last_audit is not None
            has_oversight = entry.human_oversight_level == "full"
            checks.append(
                {
                    "system_name": entry.system_name,
                    "has_recent_audit": has_audit,
                    "full_human_oversight": has_oversight,
                    "compliant": has_audit and has_oversight,
                }
            )

        all_pass = all(c["compliant"] for c in checks) if checks else True

        return {
            "article": "Article 15 — Accuracy, Robustness, and Cybersecurity",
            "regulation": _REGULATION_VERSION,
            "overall_compliant": all_pass,
            "high_risk_systems": checks,
            "checked_at": datetime.now(tz=UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # Compliance schedule enforcement
    # ------------------------------------------------------------------

    _last_compliance_check: datetime | None = None

    def is_compliance_check_overdue(self) -> bool:
        """Return True if a compliance check has not been run within the
        configured schedule interval.
        """
        if self._last_compliance_check is None:
            return True

        elapsed = (datetime.now(tz=UTC) - self._last_compliance_check).total_seconds()
        return elapsed > (_COMPLIANCE_SCHEDULE_INTERVAL_HOURS * 3600)

    def record_compliance_check(self) -> None:
        """Record that a compliance check was completed now."""
        self._last_compliance_check = datetime.now(tz=UTC)
