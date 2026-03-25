"""Router: discovery — collection runs, observed facts, evidence artifacts."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from internalcmdb.models.collectors import CollectorAgent, CollectorSnapshot
from internalcmdb.models.discovery import (
    CollectionRun,
    DiscoverySource,
    EvidenceArtifact,
    ObservedFact,
)

from ..deps import get_db
from ..schemas.common import Page, PageMeta, paginate
from ..schemas.domain import (
    CollectionRunOut,
    DiscoverySourceOut,
    EvidenceArtifactOut,
    ObservedFactOut,
)

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


@router.get("/evidence", response_model=Page[EvidenceArtifactOut])
def list_evidence(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    run_id: uuid.UUID | None = None,
) -> Page[EvidenceArtifactOut]:
    q = db.query(EvidenceArtifact)
    if run_id is not None:
        q = q.filter(EvidenceArtifact.collection_run_id == run_id)
    q = q.order_by(EvidenceArtifact.created_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


@router.get("/stats")
def discovery_stats(
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Aggregate statistics across all discovery subsystems."""
    source_count = db.scalar(select(func.count()).select_from(DiscoverySource)) or 0
    run_count = db.scalar(select(func.count()).select_from(CollectionRun)) or 0
    fact_count = db.scalar(select(func.count()).select_from(ObservedFact)) or 0
    evidence_count = db.scalar(select(func.count()).select_from(EvidenceArtifact)) or 0

    fact_ns_rows = db.execute(
        select(ObservedFact.fact_namespace, func.count())
        .group_by(ObservedFact.fact_namespace)
        .order_by(func.count().desc())
    ).all()
    fact_namespaces = [{"namespace": r[0], "count": r[1]} for r in fact_ns_rows]

    agent_count = db.scalar(
        select(func.count()).select_from(CollectorAgent)
        .where(CollectorAgent.is_active.is_(True))
    ) or 0
    snapshot_count = db.scalar(select(func.count()).select_from(CollectorSnapshot)) or 0

    snap_kind_rows = db.execute(
        select(CollectorSnapshot.snapshot_kind, func.count())
        .group_by(CollectorSnapshot.snapshot_kind)
        .order_by(func.count().desc())
    ).all()
    snapshot_kinds = [{"kind": r[0], "count": r[1]} for r in snap_kind_rows]

    latest_run = db.execute(
        select(CollectionRun.started_at)
        .order_by(CollectionRun.started_at.desc())
        .limit(1)
    ).scalar()

    latest_snapshot = db.execute(
        select(CollectorSnapshot.collected_at)
        .order_by(CollectorSnapshot.collected_at.desc())
        .limit(1)
    ).scalar()

    return {
        "sources": source_count,
        "collection_runs": run_count,
        "observed_facts": fact_count,
        "evidence_artifacts": evidence_count,
        "fact_namespaces": fact_namespaces,
        "active_agents": agent_count,
        "total_snapshots": snapshot_count,
        "snapshot_kinds": snapshot_kinds,
        "latest_run_at": str(latest_run) if latest_run else None,
        "latest_snapshot_at": str(latest_snapshot) if latest_snapshot else None,
    }
