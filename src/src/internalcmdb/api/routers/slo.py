"""Router: slo — Service Level Objectives, error budgets, burn rate analysis."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.slo.framework import SLOFramework

from ..deps import get_async_session

router = APIRouter(prefix="/slo", tags=["slo"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class SLODefineBody(BaseModel):
    service_id: str
    sli_type: str
    target: float = Field(ge=0.0, le=1.0)
    window_days: int = Field(default=30, ge=1, le=365)


class SLODefinitionOut(BaseModel):
    slo_id: str
    service_id: str | None = None
    sli_type: str
    target: float
    window_days: int
    burn_rate_fast: float | None = None
    burn_rate_slow: float | None = None
    is_active: bool = True
    created_at: str | None = None


class SLOBudgetOut(BaseModel):
    slo_id: str
    target: float
    window_days: int
    good_events: int
    total_events: int
    burn_rate: float
    budget_remaining_pct: float
    is_fast_burn: bool
    is_slow_burn: bool
    status: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: Any) -> dict[str, Any]:
    mapping = row._mapping
    return {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in mapping.items()}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/definitions", response_model=list[SLODefinitionOut])
async def list_definitions(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    active_only: bool = Query(True),
) -> list[dict[str, Any]]:
    """List all SLO definitions."""
    q = "SELECT * FROM telemetry.slo_definition"
    if active_only:
        q += " WHERE is_active = true"
    q += " ORDER BY created_at DESC"
    result = await session.execute(text(q))
    return [_row_to_dict(r) for r in result.fetchall()]


@router.get("/{slo_id}/budget", response_model=SLOBudgetOut)
async def slo_budget(
    slo_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Current error budget for a specific SLO."""
    fw = SLOFramework(session)
    result = await fw.current_budget(slo_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{slo_id}/history")
async def slo_history(
    slo_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """SLI measurement history for an SLO."""
    offset = (page - 1) * page_size
    result = await session.execute(
        text("""
            SELECT measurement_id, slo_id, good_events, total_events, measured_at
            FROM telemetry.slo_measurement
            WHERE slo_id = :slo_id
            ORDER BY measured_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"slo_id": slo_id, "limit": page_size, "offset": offset},
    )
    return {
        "slo_id": slo_id,
        "measurements": [_row_to_dict(r) for r in result.fetchall()],
    }


@router.get("/dashboard")
async def slo_dashboard(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Overview dashboard: all active SLOs with current budget status."""
    defs = await session.execute(
        text("SELECT slo_id FROM telemetry.slo_definition WHERE is_active = true")
    )
    slo_ids = [str(r[0]) for r in defs.fetchall()]

    fw = SLOFramework(session)
    budgets: list[dict[str, Any]] = []
    for sid in slo_ids:
        budget = await fw.current_budget(sid)
        if "error" not in budget:
            budgets.append(budget)

    return {"slos": budgets, "count": len(budgets)}


@router.post("/define")
async def define_slo(
    body: SLODefineBody,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Create a new SLO definition."""
    fw = SLOFramework(session)
    return await fw.define_slo(
        service_id=body.service_id,
        sli_type=body.sli_type,
        target=body.target,
        window_days=body.window_days,
    )
