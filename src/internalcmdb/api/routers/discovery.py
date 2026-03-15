"""Router: discovery — collection runs, observed facts, evidence artifacts."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from internalcmdb.models.discovery import CollectionRun, DiscoverySource, ObservedFact

from ..deps import get_db
from ..schemas.common import Page, PageMeta, paginate
from ..schemas.domain import CollectionRunOut, DiscoverySourceOut, ObservedFactOut

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/sources", response_model=list[DiscoverySourceOut])
def list_sources(db: Annotated[Session, Depends(get_db)]) -> list[DiscoverySource]:
    stmt = select(DiscoverySource).order_by(DiscoverySource.source_code)
    return db.scalars(stmt).all()  # type: ignore[return-value]


@router.get("/runs", response_model=Page[CollectionRunOut])
def list_runs(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    source_id: uuid.UUID | None = None,
) -> Page[CollectionRunOut]:
    q = db.query(CollectionRun)
    if source_id is not None:
        q = q.filter(CollectionRun.discovery_source_id == source_id)
    q = q.order_by(CollectionRun.started_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


@router.get("/runs/{run_id}", response_model=CollectionRunOut)
def get_run(run_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> CollectionRun:
    run = db.get(CollectionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Collection run not found")
    return run


@router.get("/facts", response_model=Page[ObservedFactOut])
def list_facts(  # noqa: PLR0913
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    run_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    fact_namespace: str | None = None,
) -> Page[ObservedFactOut]:
    q = db.query(ObservedFact)
    if run_id is not None:
        q = q.filter(ObservedFact.collection_run_id == run_id)
    if entity_id is not None:
        q = q.filter(ObservedFact.entity_id == entity_id)
    if fact_namespace is not None:
        q = q.filter(ObservedFact.fact_namespace == fact_namespace)
    q = q.order_by(ObservedFact.observed_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))
