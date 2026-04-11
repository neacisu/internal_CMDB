"""Router: compliance — AI inventory, EU AI Act report, data lineage, Article 12."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_async_session

router = APIRouter(prefix="/compliance", tags=["compliance"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AISystemOut(BaseModel):
    system_name: str
    risk_level: str
    purpose: str
    data_types: list[str] = Field(default_factory=list)
    model_ids: list[str] = Field(default_factory=list)
    deployed_since: str = ""
    owner_team: str = ""
    human_oversight_level: str = ""
    last_audit: str | None = None


class ComplianceReportOut(BaseModel):
    report: str
    generated_at: str


class DataLineageOut(BaseModel):
    entity_id: str
    lineage_stages: list[dict[str, Any]] = Field(default_factory=list)
    checked_at: str = ""


class Article12Out(BaseModel):
    audit_trail: bool = False
    audit_trail_detail: str = ""
    decision_logging: bool = False
    decision_logging_detail: str = ""
    model_versioning: bool = False
    model_versioning_detail: str = ""
    data_lineage: bool = False
    data_lineage_detail: str = ""
    hitl_feedback: bool = False
    hitl_feedback_detail: str = ""
    overall_compliant: bool = False
    checked_at: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/inventory", response_model=list[AISystemOut])
async def ai_inventory(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[dict[str, Any]]:
    """Return the full AI system inventory (EU AI Act Article 13)."""
    from internalcmdb.governance.ai_compliance import AIComplianceManager  # noqa: PLC0415

    mgr = AIComplianceManager(session)
    return await mgr.get_ai_inventory()


@router.get("/report", response_model=ComplianceReportOut)
async def compliance_report(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Generate an EU AI Act compliance report."""
    from datetime import UTC, datetime  # noqa: PLC0415

    from internalcmdb.governance.ai_compliance import AIComplianceManager  # noqa: PLC0415

    mgr = AIComplianceManager(session)
    report = await mgr.generate_compliance_report()
    return {
        "report": report,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


@router.get("/data-lineage/{entity_id}", response_model=DataLineageOut)
async def data_lineage(
    entity_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Trace data lineage for a specific entity through the CMDB pipeline."""
    from internalcmdb.governance.ai_compliance import AIComplianceManager  # noqa: PLC0415

    mgr = AIComplianceManager(session)
    return await mgr.audit_data_lineage(entity_id)


@router.get("/article-12", response_model=Article12Out)
async def article_12_check(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Verify EU AI Act Article 12 transparency requirements."""
    from internalcmdb.governance.ai_compliance import AIComplianceManager  # noqa: PLC0415

    mgr = AIComplianceManager(session)
    return await mgr.check_article_12()
