"""Router: governance — policies, approvals, changelog."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from internalcmdb.models.governance import (  # pylint: disable=wrong-import-order
    ApprovalRecord,
    ChangeLog,
    PolicyRecord,
)

from ..deps import get_db
from ..schemas.common import Page, PageMeta, paginate
from ..schemas.domain import ApprovalRecordOut, ChangeLogOut, PolicyRecordOut

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/policies", response_model=list[PolicyRecordOut])
def list_policies(
    db: Annotated[Session, Depends(get_db)],
    active_only: bool = True,
) -> list[PolicyRecord]:
    q = select(PolicyRecord).order_by(PolicyRecord.policy_code)
    if active_only:
        q = q.where(PolicyRecord.is_active.is_(True))
    return db.scalars(q).all()  # type: ignore[return-value]


@router.get("/approvals", response_model=Page[ApprovalRecordOut])
def list_approvals(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
) -> Page[ApprovalRecordOut]:
    q = db.query(ApprovalRecord)
    if status is not None:
        q = q.filter(ApprovalRecord.status_text == status)
    q = q.order_by(ApprovalRecord.created_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


@router.get("/changelog", response_model=Page[ChangeLogOut])
def list_changelog(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[ChangeLogOut]:
    q = db.query(ChangeLog).order_by(ChangeLog.changed_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))
