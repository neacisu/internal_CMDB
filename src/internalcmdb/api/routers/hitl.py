"""Router: hitl — Human-In-The-Loop review queue, decisions, and accuracy."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.governance.hitl_workflow import HITLWorkflow

from ..deps import get_async_session
from ..middleware.rate_limit import rate_limit
from ..openapi_responses import RESP_400, RESP_403, RESP_404, merge_responses
from internalcmdb.api.middleware.rbac import AUTH_DEV_MODE, require_role

router = APIRouter(prefix="/hitl", tags=["hitl"])

_HITL_ITEM_NOT_FOUND_OR_DECIDED = "Item not found or already decided"

_HITL_NOT_FOUND_RESPONSES = merge_responses(RESP_404)
_HITL_APPROVE_RESPONSES = merge_responses(RESP_404, RESP_403)
_HITL_BULK_RESPONSES = merge_responses(RESP_400)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class DecisionBody(BaseModel):
    reason: str


class ModifyBody(DecisionBody):
    modifications: dict[str, Any] = Field(default_factory=dict)


class BulkDecideBody(BaseModel):
    item_ids: list[str]
    decision: str = Field(pattern=r"^(approved|rejected)$")
    reason: str


class HITLItemOut(BaseModel):
    item_id: str
    item_type: str
    risk_class: str
    priority: str
    status: str
    source_event_id: str | None = None
    correlation_id: str | None = None
    context_jsonb: dict[str, Any] | None = None
    llm_suggestion: dict[str, Any] | None = None
    llm_confidence: float | None = None
    llm_model_used: str | None = None
    decided_by: str | None = None
    decision: str | None = None
    decision_reason: str | None = None
    decision_jsonb: dict[str, Any] | None = None
    created_at: str | None = None
    expires_at: str | None = None
    decided_at: str | None = None
    escalated_to: str | None = None
    escalation_count: int = 0
    approvals_jsonb: list[dict[str, Any]] | None = None


class HITLStatsOut(BaseModel):
    pending_count: int
    escalated_count: int
    approved_count: int
    rejected_count: int
    blocked_count: int
    avg_decision_time_seconds: float | None = None
    accuracy: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: Any) -> dict[str, Any]:
    mapping = row._mapping
    return {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in mapping.items()}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/queue",
    response_model=list[HITLItemOut],
    dependencies=[Depends(require_role("hitl_reviewer", "platform_admin", "operator"))],
)
async def list_queue(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    status: Annotated[str, Query(description="Filter by status")] = "pending",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """List pending HITL items (paginated)."""
    offset = (page - 1) * page_size
    result = await session.execute(
        text("""
            SELECT * FROM governance.hitl_item
             WHERE status = :status
             ORDER BY
                 CASE priority
                     WHEN 'critical' THEN 1
                     WHEN 'high'     THEN 2
                     WHEN 'medium'   THEN 3
                     WHEN 'low'      THEN 4
                     ELSE 5
                 END,
                 created_at ASC
             LIMIT :limit OFFSET :offset
        """),
        {"status": status, "limit": page_size, "offset": offset},
    )
    return [_row_to_dict(r) for r in result.fetchall()]


@router.get(
    "/queue/{item_id}",
    response_model=HITLItemOut,
    responses=_HITL_NOT_FOUND_RESPONSES,
    dependencies=[Depends(require_role("hitl_reviewer", "platform_admin", "operator"))],
)
async def get_item(
    item_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Get a single HITL item by ID."""
    result = await session.execute(
        text("SELECT * FROM governance.hitl_item WHERE item_id = :item_id"),
        {"item_id": item_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="HITL item not found")
    return _row_to_dict(row)


@router.post(
    "/queue/{item_id}/approve",
    responses=_HITL_APPROVE_RESPONSES,
    dependencies=[Depends(require_role("hitl_reviewer", "platform_admin"))],
)
async def approve_item(
    item_id: str,
    body: DecisionBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Approve a pending HITL item.

    RC-3 items require ``platform_admin`` role and two distinct approvers.
    """
    risk_row = await session.execute(
        text("SELECT risk_class FROM governance.hitl_item WHERE item_id = :item_id"),
        {"item_id": item_id},
    )
    risk_item = risk_row.fetchone()
    if risk_item is None:
        raise HTTPException(status_code=404, detail="HITL item not found")

    risk_class = str(risk_item[0] or "")
    if risk_class == "RC-3":
        caller_role = getattr(request.state, "rbac_role", None)
        if caller_role != "platform_admin" and not AUTH_DEV_MODE:
            raise HTTPException(
                status_code=403,
                detail="RC-3 items require platform_admin role",
            )

    wf = HITLWorkflow(session)
    decided_by = getattr(request.state, "rbac_sub", "unknown")
    ok = await wf.approve(item_id, decided_by, body.reason)
    if not ok:
        raise HTTPException(status_code=404, detail=_HITL_ITEM_NOT_FOUND_OR_DECIDED)
    return {"item_id": item_id, "decision": "approved"}


@router.post(
    "/queue/{item_id}/reject",
    responses=_HITL_NOT_FOUND_RESPONSES,
    dependencies=[Depends(require_role("hitl_reviewer", "platform_admin"))],
)
async def reject_item(
    item_id: str,
    body: DecisionBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Reject a pending HITL item."""
    decided_by = getattr(request.state, "rbac_sub", "unknown")
    wf = HITLWorkflow(session)
    ok = await wf.reject(item_id, decided_by, body.reason)
    if not ok:
        raise HTTPException(status_code=404, detail=_HITL_ITEM_NOT_FOUND_OR_DECIDED)
    return {"item_id": item_id, "decision": "rejected"}


@router.post(
    "/queue/{item_id}/modify",
    responses=_HITL_NOT_FOUND_RESPONSES,
    dependencies=[Depends(require_role("hitl_reviewer", "platform_admin"))],
)
async def modify_item(
    item_id: str,
    body: ModifyBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Approve a HITL item with modifications."""
    decided_by = getattr(request.state, "rbac_sub", "unknown")
    wf = HITLWorkflow(session)
    ok = await wf.modify(item_id, decided_by, body.reason, body.modifications)
    if not ok:
        raise HTTPException(status_code=404, detail=_HITL_ITEM_NOT_FOUND_OR_DECIDED)
    return {"item_id": item_id, "decision": "approved_with_modifications"}


@router.post(
    "/queue/{item_id}/escalate",
    responses=_HITL_NOT_FOUND_RESPONSES,
    dependencies=[Depends(require_role("hitl_reviewer", "platform_admin", "operator"))],
)
async def escalate_item(
    item_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Manually escalate a HITL item."""
    wf = HITLWorkflow(session)
    ok = await wf.escalate(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found or cannot escalate")
    return {"item_id": item_id, "escalated": True}


@router.get(
    "/stats",
    response_model=HITLStatsOut,
    dependencies=[Depends(require_role("hitl_reviewer", "platform_admin", "operator", "viewer"))],
)
async def hitl_stats(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """KPIs: pending count, average decision time, accuracy."""
    result = await session.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending')    AS pending_count,
                COUNT(*) FILTER (WHERE status = 'escalated')  AS escalated_count,
                COUNT(*) FILTER (WHERE status = 'approved')   AS approved_count,
                COUNT(*) FILTER (WHERE status = 'rejected')   AS rejected_count,
                COUNT(*) FILTER (WHERE status = 'blocked')    AS blocked_count,
                EXTRACT(EPOCH FROM AVG(decided_at - created_at)
                    FILTER (WHERE decided_at IS NOT NULL))     AS avg_decision_time_seconds
            FROM governance.hitl_item
        """)
    )
    row = result.fetchone()
    stats = dict(row._mapping) if row else {}

    acc_result = await session.execute(
        text("""
            SELECT
                CASE WHEN COUNT(*) > 0
                     THEN ROUND(COUNT(*) FILTER (WHERE agreement = true)::numeric
                                / COUNT(*)::numeric, 4)
                     ELSE NULL
                END AS accuracy
            FROM governance.hitl_feedback
            WHERE agreement IS NOT NULL
        """)
    )
    acc_row = acc_result.fetchone()
    stats["accuracy"] = float(acc_row[0]) if acc_row and acc_row[0] is not None else None

    return stats


@router.get(
    "/history",
    response_model=list[HITLItemOut],
    dependencies=[Depends(require_role("hitl_reviewer", "platform_admin", "operator", "viewer"))],
)
async def hitl_history(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """Decision history (paginated) — items that have been decided."""
    offset = (page - 1) * page_size
    result = await session.execute(
        text("""
            SELECT * FROM governance.hitl_item
             WHERE status NOT IN ('pending', 'escalated')
             ORDER BY decided_at DESC NULLS LAST
             LIMIT :limit OFFSET :offset
        """),
        {"limit": page_size, "offset": offset},
    )
    return [_row_to_dict(r) for r in result.fetchall()]


@router.get(
    "/accuracy",
    dependencies=[Depends(require_role("hitl_reviewer", "platform_admin", "operator", "viewer"))],
)
async def hitl_accuracy(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """LLM accuracy versus human decisions."""
    result = await session.execute(
        text("""
            SELECT
                COUNT(*)                                         AS total_feedback,
                COUNT(*) FILTER (WHERE agreement = true)         AS agreed,
                COUNT(*) FILTER (WHERE agreement = false)        AS disagreed,
                COUNT(*) FILTER (WHERE agreement IS NULL)        AS unknown,
                CASE WHEN COUNT(*) FILTER (WHERE agreement IS NOT NULL) > 0
                     THEN ROUND(
                         COUNT(*) FILTER (WHERE agreement = true)::numeric
                         / COUNT(*) FILTER (WHERE agreement IS NOT NULL)::numeric, 4
                     )
                     ELSE NULL
                END                                              AS accuracy_rate
            FROM governance.hitl_feedback
        """)
    )
    row = result.fetchone()
    if row is None:
        return {
            "total_feedback": 0,
            "agreed": 0,
            "disagreed": 0,
            "unknown": 0,
            "accuracy_rate": None,
        }
    return {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in row._mapping.items()}


@router.post(
    "/bulk-decide",
    responses=_HITL_BULK_RESPONSES,
    dependencies=[Depends(require_role("platform_admin"))],
)
@rate_limit("5/minute")
async def bulk_decide(
    request: Request,
    body: BulkDecideBody,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Bulk approve/reject for RC-1/RC-2 items only."""
    allowed_rc = await session.execute(
        text("""
            SELECT item_id FROM governance.hitl_item
             WHERE item_id = ANY(:ids)
               AND risk_class IN ('RC-1', 'RC-2')
               AND status IN ('pending', 'escalated')
        """),
        {"ids": body.item_ids},
    )
    valid_ids = [str(r[0]) for r in allowed_rc.fetchall()]

    if not valid_ids:
        raise HTTPException(
            status_code=400,
            detail="No eligible items found (only RC-1/RC-2 pending items allowed for bulk)",
        )

    wf = HITLWorkflow(session)
    succeeded: list[str] = []
    failed: list[str] = []
    decided_by = getattr(request.state, "rbac_sub", "unknown")

    for iid in valid_ids:
        if body.decision == "approved":
            ok = await wf.approve(iid, decided_by, body.reason)
        else:
            ok = await wf.reject(iid, decided_by, body.reason)
        (succeeded if ok else failed).append(iid)

    return {
        "decision": body.decision,
        "succeeded": succeeded,
        "failed": failed,
        "total": len(succeeded),
    }
