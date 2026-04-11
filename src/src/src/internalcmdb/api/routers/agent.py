"""Router: agent — agent runs, action requests, prompt templates."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from internalcmdb.models.agent_control import ActionRequest, AgentRun, PromptTemplateRegistry

from ..deps import get_db
from ..schemas.common import Page, PageMeta, paginate
from ..schemas.domain import ActionRequestOut, AgentRunOut, PromptTemplateOut

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/templates", response_model=list[PromptTemplateOut])
def list_templates(
    db: Annotated[Session, Depends(get_db)],
    active_only: bool = True,
) -> list[PromptTemplateRegistry]:
    q = select(PromptTemplateRegistry).order_by(PromptTemplateRegistry.template_code)
    if active_only:
        q = q.where(PromptTemplateRegistry.is_active.is_(True))
    return db.scalars(q).all()  # type: ignore[return-value]


@router.get("/runs", response_model=Page[AgentRunOut])
def list_runs(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
) -> Page[AgentRunOut]:
    q = db.query(AgentRun)
    if status is not None:
        q = q.filter(AgentRun.status_text == status)
    q = q.order_by(AgentRun.started_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


@router.get("/runs/{run_id}", response_model=AgentRunOut)
def get_run(run_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


@router.get("/actions", response_model=Page[ActionRequestOut])
def list_actions(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
) -> Page[ActionRequestOut]:
    q = db.query(ActionRequest)
    if status is not None:
        q = q.filter(ActionRequest.status_text == status)
    q = q.order_by(ActionRequest.created_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))
