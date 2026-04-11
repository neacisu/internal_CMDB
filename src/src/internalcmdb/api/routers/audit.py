"""Router: audit — HTTP request audit trail and governance statistics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from internalcmdb.models.governance import (
    ApprovalRecord,
    AuditEvent,
    ChangeLog,
    PolicyRecord,
)

from ..deps import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@dataclass
class AuditFilterParams:
    """Query-parameter filter group for audit event listing."""

    actor: str | None = None
    status: str | None = None
    event_type: str | None = None


@router.get("/events")
def list_events(
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[AuditFilterParams, Depends()],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    q = db.query(AuditEvent)
    if filters.actor is not None:
        q = q.filter(AuditEvent.actor.ilike(f"%{filters.actor}%"))
    if filters.status is not None:
        q = q.filter(AuditEvent.status == filters.status)
    if filters.event_type is not None:
        q = q.filter(AuditEvent.event_type == filters.event_type)

    total = q.count()
    items = (
        q.order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "event_id": str(e.audit_event_id),
                "event_type": e.event_type,
                "actor": e.actor,
                "action": e.action,
                "target_entity": e.target_entity,
                "correlation_id": e.correlation_id,
                "duration_ms": e.duration_ms,
                "status": e.status,
                "ip_address": e.ip_address,
                "risk_level": e.risk_level,
                "created_at": str(e.created_at),
            }
            for e in items
        ],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/stats")
def audit_stats(
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Aggregate audit statistics across all governance tables."""
    total_events = db.scalar(select(func.count()).select_from(AuditEvent)) or 0
    total_changelogs = db.scalar(select(func.count()).select_from(ChangeLog)) or 0
    total_policies = db.scalar(select(func.count()).select_from(PolicyRecord)) or 0
    total_approvals = db.scalar(select(func.count()).select_from(ApprovalRecord)) or 0

    status_rows = db.execute(
        select(AuditEvent.status, func.count())
        .group_by(AuditEvent.status)
        .order_by(func.count().desc())
    ).all()
    status_breakdown = [{"status": r[0], "count": r[1]} for r in status_rows]

    top_actors = db.execute(
        select(AuditEvent.actor, func.count())
        .where(AuditEvent.actor.isnot(None))
        .group_by(AuditEvent.actor)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    actor_breakdown = [{"actor": r[0], "count": r[1]} for r in top_actors]

    top_endpoints = db.execute(
        select(AuditEvent.target_entity, func.count())
        .where(AuditEvent.target_entity.isnot(None))
        .group_by(AuditEvent.target_entity)
        .order_by(func.count().desc())
        .limit(15)
    ).all()
    endpoint_breakdown = [{"path": r[0], "count": r[1]} for r in top_endpoints]

    avg_duration = db.scalar(
        select(func.avg(AuditEvent.duration_ms)).where(AuditEvent.duration_ms.isnot(None))
    )

    error_count = (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.status.in_(["400", "401", "403", "404", "422", "500", "502", "503"]))
        )
        or 0
    )

    latest_event = db.scalar(
        select(AuditEvent.created_at).order_by(AuditEvent.created_at.desc()).limit(1)
    )

    return {
        "total_events": total_events,
        "total_changelogs": total_changelogs,
        "total_policies": total_policies,
        "total_approvals": total_approvals,
        "error_count": error_count,
        "avg_duration_ms": round(float(avg_duration), 1) if avg_duration else None,
        "status_breakdown": status_breakdown,
        "actor_breakdown": actor_breakdown,
        "endpoint_breakdown": endpoint_breakdown,
        "latest_event_at": str(latest_event) if latest_event else None,
    }
