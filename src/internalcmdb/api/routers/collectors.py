"""Router: collectors — agent enrollment, telemetry ingestion, fleet health."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from internalcmdb.collectors.schedule_tiers import DEFAULT_AGENT_CONFIG
from internalcmdb.models.collectors import (
    CollectorAgent,
    CollectorSnapshot,
    SnapshotDiff,
)
from internalcmdb.models.discovery import EvidenceArtifact
from internalcmdb.models.registry import Host

from ..config import get_settings
from ..deps import get_db
from ..schemas.collectors import (
    AgentConfigUpdate,
    AgentOut,
    EnrollRequest,
    EnrollResponse,
    FleetHealthSummary,
    HeartbeatRequest,
    HeartbeatResponse,
    HostHealth,
    IngestRequest,
    IngestResponse,
    LiveWorkerStatus,
    ReportGenerateRequest,
    ReportOut,
    SnapshotDiffOut,
    SnapshotOut,
)

router = APIRouter(prefix="/collectors", tags=["collectors"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_agent_token(agent_id: uuid.UUID, secret: str) -> str:
    """HMAC-SHA256 token derived from agent_id and app secret."""
    return hmac.new(
        secret.encode(),
        str(agent_id).encode(),
        hashlib.sha256,
    ).hexdigest()


def _next_snapshot_version(db: Session, agent_id: uuid.UUID) -> int:
    """Return the next monotonic snapshot version for a given agent."""
    current_max = db.scalar(
        select(func.max(CollectorSnapshot.snapshot_version)).where(
            CollectorSnapshot.agent_id == agent_id
        )
    )
    return (current_max or 0) + 1


# ---------------------------------------------------------------------------
# Agent enrollment & management
# ---------------------------------------------------------------------------


@router.post("/enroll", response_model=EnrollResponse, status_code=201)
def enroll_agent(
    body: EnrollRequest,
    db: Annotated[Session, Depends(get_db)],
) -> EnrollResponse:
    """Agent self-registers and receives an ID, schedule config, and auth token."""
    # Resolve host_id from host_code if possible
    host = db.execute(select(Host.host_id).where(Host.hostname == body.host_code)).first()
    host_id = host[0] if host else None

    agent_id = uuid.uuid4()
    agent = CollectorAgent(
        agent_id=agent_id,
        host_id=host_id,
        host_code=body.host_code,
        agent_version=body.agent_version,
        agent_config_jsonb={
            **DEFAULT_AGENT_CONFIG,
            "capabilities": body.capabilities,
        },
        status="online",
    )
    db.add(agent)
    db.commit()

    settings = get_settings()
    token = _generate_agent_token(agent_id, settings.postgres_password)

    tiers: dict[str, int] = DEFAULT_AGENT_CONFIG["tiers"]  # type: ignore[assignment]
    collectors: list[str] = DEFAULT_AGENT_CONFIG["enabled_collectors"]  # type: ignore[assignment]

    return EnrollResponse(
        agent_id=agent_id,
        schedule_tiers=tiers,
        enabled_collectors=collectors,
        api_token=token,
    )


@router.get("/agents", response_model=list[AgentOut])
def list_agents(
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    active_only: bool = True,
) -> list[CollectorAgent]:
    stmt = select(CollectorAgent)
    if active_only:
        stmt = stmt.where(CollectorAgent.is_active.is_(True))
    if status:
        stmt = stmt.where(CollectorAgent.status == status)
    stmt = stmt.order_by(CollectorAgent.host_code)
    return db.scalars(stmt).all()  # type: ignore[return-value]


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> CollectorAgent:
    agent = db.get(CollectorAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}/config", response_model=AgentOut)
def update_agent_config(
    agent_id: uuid.UUID,
    body: AgentConfigUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CollectorAgent:
    agent = db.get(CollectorAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    config = dict(agent.agent_config_jsonb or {})
    if body.tiers is not None:
        config["tiers"] = body.tiers
    if body.enabled_collectors is not None:
        config["enabled_collectors"] = body.enabled_collectors
    agent.agent_config_jsonb = config
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/agents/{agent_id}", status_code=204)
def retire_agent(
    agent_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    agent = db.get(CollectorAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = False
    agent.status = "retired"
    db.commit()


# ---------------------------------------------------------------------------
# Telemetry ingestion
# ---------------------------------------------------------------------------


@router.post("/ingest", response_model=IngestResponse)
def ingest_snapshots(
    body: IngestRequest,
    db: Annotated[Session, Depends(get_db)],
) -> IngestResponse:
    """Receive a batch of snapshots from an agent."""
    agent = db.get(CollectorAgent, body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    accepted = 0
    deduplicated = 0
    errors: list[str] = []

    for item in body.snapshots:
        # Check for dedup — same agent + kind + hash
        existing = db.execute(
            select(CollectorSnapshot.snapshot_id)
            .where(
                CollectorSnapshot.agent_id == body.agent_id,
                CollectorSnapshot.snapshot_kind == item.snapshot_kind,
                CollectorSnapshot.payload_hash == item.payload_hash,
            )
            .order_by(CollectorSnapshot.collected_at.desc())
            .limit(1)
        ).first()

        if existing:
            deduplicated += 1
            continue

        version = _next_snapshot_version(db, body.agent_id)
        snapshot = CollectorSnapshot(
            snapshot_id=uuid.uuid4(),
            agent_id=body.agent_id,
            snapshot_version=version,
            snapshot_kind=item.snapshot_kind,
            payload_jsonb=item.payload,
            payload_hash=item.payload_hash,
            collected_at=item.collected_at,
            tier_code=item.tier_code,
        )
        db.add(snapshot)
        db.flush()

        # Generate diff against previous snapshot of same kind
        prev = db.execute(
            select(CollectorSnapshot)
            .where(
                CollectorSnapshot.agent_id == body.agent_id,
                CollectorSnapshot.snapshot_kind == item.snapshot_kind,
                CollectorSnapshot.snapshot_id != snapshot.snapshot_id,
            )
            .order_by(CollectorSnapshot.collected_at.desc())
            .limit(1)
        ).first()

        if prev:
            prev_snap = prev[0]
            diff = SnapshotDiff(
                diff_id=uuid.uuid4(),
                snapshot_id=snapshot.snapshot_id,
                previous_snapshot_id=prev_snap.snapshot_id,
                diff_jsonb={"note": "diff computation deferred"},
                change_summary="Payload changed",
            )
            db.add(diff)

        accepted += 1

    # Update heartbeat timestamp
    agent.last_heartbeat_at = str(datetime.now(UTC))
    agent.status = "online"
    db.commit()

    return IngestResponse(accepted=accepted, deduplicated=deduplicated, errors=errors)


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(
    body: HeartbeatRequest,
    db: Annotated[Session, Depends(get_db)],
) -> HeartbeatResponse:
    """Lightweight keep-alive from an agent."""
    agent = db.get(CollectorAgent, body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.last_heartbeat_at = str(datetime.now(UTC))
    agent.agent_version = body.agent_version
    agent.status = "online"

    # Store heartbeat as a snapshot
    payload = {
        "uptime_seconds": body.uptime_seconds,
        "load_avg": body.load_avg,
        "memory_pct": body.memory_pct,
    }
    payload_bytes = str(sorted(payload.items())).encode()
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()

    # Dedup heartbeat
    existing = db.execute(
        select(CollectorSnapshot.snapshot_id)
        .where(
            CollectorSnapshot.agent_id == body.agent_id,
            CollectorSnapshot.snapshot_kind == "heartbeat",
            CollectorSnapshot.payload_hash == payload_hash,
        )
        .order_by(CollectorSnapshot.collected_at.desc())
        .limit(1)
    ).first()

    if not existing:
        version = _next_snapshot_version(db, body.agent_id)
        snapshot = CollectorSnapshot(
            snapshot_id=uuid.uuid4(),
            agent_id=body.agent_id,
            snapshot_version=version,
            snapshot_kind="heartbeat",
            payload_jsonb=payload,
            payload_hash=payload_hash,
            collected_at=str(datetime.now(UTC)),
            tier_code="5s",
        )
        db.add(snapshot)

    db.commit()

    # Check if agent needs config update
    config_update = None
    if agent.agent_config_jsonb:
        config_update = agent.agent_config_jsonb

    return HeartbeatResponse(
        ok=True,
        config_update=config_update,
        update_available=False,
    )


# ---------------------------------------------------------------------------
# Fleet health
# ---------------------------------------------------------------------------


@router.get("/health", response_model=FleetHealthSummary)
def fleet_health(db: Annotated[Session, Depends(get_db)]) -> FleetHealthSummary:
    """Aggregate health across all active agents."""
    rows = db.execute(
        select(CollectorAgent.status, func.count(CollectorAgent.agent_id))
        .where(CollectorAgent.is_active.is_(True))
        .group_by(CollectorAgent.status)
    ).all()
    counts: dict[str, int] = {r[0]: r[1] for r in rows}
    total = sum(counts.values())
    return FleetHealthSummary(
        online=counts.get("online", 0),
        degraded=counts.get("degraded", 0),
        offline=counts.get("offline", 0),
        retired=counts.get("retired", 0),
        total=total,
    )


@router.get("/health/{host_code}", response_model=HostHealth)
def host_health(
    host_code: str,
    db: Annotated[Session, Depends(get_db)],
) -> HostHealth:
    """Per-host live health from the latest heartbeat snapshot."""
    agent = db.execute(
        select(CollectorAgent)
        .where(
            CollectorAgent.host_code == host_code,
            CollectorAgent.is_active.is_(True),
        )
        .limit(1)
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="No agent for host")

    # Fetch latest heartbeat snapshot
    latest_hb = db.execute(
        select(CollectorSnapshot)
        .where(
            CollectorSnapshot.agent_id == agent.agent_id,
            CollectorSnapshot.snapshot_kind == "heartbeat",
        )
        .order_by(CollectorSnapshot.collected_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    payload = latest_hb.payload_jsonb if latest_hb else {}

    return HostHealth(
        agent_id=agent.agent_id,
        host_code=agent.host_code,
        status=agent.status,
        agent_version=agent.agent_version,
        last_heartbeat_at=agent.last_heartbeat_at,
        uptime_seconds=payload.get("uptime_seconds") if payload else None,
        load_avg=payload.get("load_avg", []) if payload else [],
        memory_pct=payload.get("memory_pct") if payload else None,
    )


# ---------------------------------------------------------------------------
# Snapshots query
# ---------------------------------------------------------------------------


@router.get("/snapshots", response_model=list[SnapshotOut])
def list_snapshots(
    db: Annotated[Session, Depends(get_db)],
    agent_id: uuid.UUID | None = None,
    kind: str | None = None,
    since: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> list[CollectorSnapshot]:
    stmt = select(CollectorSnapshot)
    if agent_id:
        stmt = stmt.where(CollectorSnapshot.agent_id == agent_id)
    if kind:
        stmt = stmt.where(CollectorSnapshot.snapshot_kind == kind)
    if since:
        stmt = stmt.where(text("collected_at >= :since").bindparams(since=since))
    stmt = stmt.order_by(CollectorSnapshot.collected_at.desc()).limit(limit)
    return db.scalars(stmt).all()  # type: ignore[return-value]


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotOut)
def get_snapshot(
    snapshot_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> CollectorSnapshot:
    snap = db.get(CollectorSnapshot, snapshot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


@router.get(
    "/snapshots/{snapshot_id}/diff",
    response_model=SnapshotDiffOut | None,
)
def get_snapshot_diff(
    snapshot_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> SnapshotDiff | None:
    diff = db.execute(
        select(SnapshotDiff).where(SnapshotDiff.snapshot_id == snapshot_id).limit(1)
    ).scalar_one_or_none()
    return diff


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.post("/reports/generate", response_model=ReportOut, status_code=201)
def generate_report(
    body: ReportGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ReportOut:
    """Generate a versioned report from the latest snapshots."""
    # Get latest version for this report kind
    latest_version_row = db.execute(
        select(func.max(text("(metadata_jsonb->>'report_version')::int"))).where(
            EvidenceArtifact.metadata_jsonb["report_kind"].astext == body.report_kind
        )
    ).first()
    next_version = ((latest_version_row[0] or 0) + 1) if latest_version_row else 1

    now = datetime.now(UTC).isoformat()

    artifact = EvidenceArtifact(
        evidence_artifact_id=uuid.uuid4(),
        # collection_run_id will be linked if one exists
        collection_run_id=None,  # type: ignore[arg-type]
        evidence_kind_term_id=None,  # type: ignore[arg-type]
        content_excerpt_text=f"{body.report_kind} report v{next_version}",
        metadata_jsonb={
            "report_kind": body.report_kind,
            "report_version": next_version,
            "generated_at": now,
            "scope": body.scope,
        },
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    return ReportOut(
        evidence_artifact_id=artifact.evidence_artifact_id,
        report_kind=body.report_kind,
        report_version=next_version,
        generated_at=now,
        content_excerpt=artifact.content_excerpt_text,
    )


@router.get("/reports", response_model=list[ReportOut])
def list_reports(
    db: Annotated[Session, Depends(get_db)],
    report_kind: str | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> list[ReportOut]:
    stmt = select(EvidenceArtifact).where(
        EvidenceArtifact.metadata_jsonb["report_kind"].astext.isnot(None)
    )
    if report_kind:
        stmt = stmt.where(EvidenceArtifact.metadata_jsonb["report_kind"].astext == report_kind)
    stmt = stmt.order_by(EvidenceArtifact.created_at.desc()).limit(limit)
    artifacts = db.scalars(stmt).all()

    return [
        ReportOut(
            evidence_artifact_id=a.evidence_artifact_id,
            report_kind=a.metadata_jsonb.get("report_kind", "") if a.metadata_jsonb else "",
            report_version=a.metadata_jsonb.get("report_version", 0) if a.metadata_jsonb else 0,
            generated_at=a.metadata_jsonb.get("generated_at", "") if a.metadata_jsonb else "",
            content_excerpt=a.content_excerpt_text,
        )
        for a in artifacts
    ]


@router.get("/reports/latest/{report_kind}", response_model=ReportOut | None)
def get_latest_report(
    report_kind: str,
    db: Annotated[Session, Depends(get_db)],
) -> ReportOut | None:
    artifact = db.execute(
        select(EvidenceArtifact)
        .where(EvidenceArtifact.metadata_jsonb["report_kind"].astext == report_kind)
        .order_by(EvidenceArtifact.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if artifact is None:
        return None

    meta = artifact.metadata_jsonb or {}
    return ReportOut(
        evidence_artifact_id=artifact.evidence_artifact_id,
        report_kind=meta.get("report_kind", ""),
        report_version=meta.get("report_version", 0),
        generated_at=meta.get("generated_at", ""),
        content_excerpt=artifact.content_excerpt_text,
    )


# ---------------------------------------------------------------------------
# Live worker status
# ---------------------------------------------------------------------------


@router.get("/workers/live", response_model=list[LiveWorkerStatus])
def live_workers(
    db: Annotated[Session, Depends(get_db)],
    host_code: str | None = None,
) -> list[LiveWorkerStatus]:
    """Aggregate latest docker_state snapshots to show live worker/container status."""
    stmt = (
        select(CollectorSnapshot)
        .join(
            CollectorAgent,
            CollectorAgent.agent_id == CollectorSnapshot.agent_id,
        )
        .where(CollectorSnapshot.snapshot_kind == "docker_state")
    )
    if host_code:
        stmt = stmt.where(CollectorAgent.host_code == host_code)

    # Get latest per agent using distinct on
    stmt = stmt.order_by(
        CollectorSnapshot.agent_id,
        CollectorSnapshot.collected_at.desc(),
    )

    snapshots = db.scalars(stmt).all()
    seen: set[uuid.UUID] = set()
    results: list[LiveWorkerStatus] = []

    for snap in snapshots:
        if snap.agent_id in seen:
            continue
        seen.add(snap.agent_id)

        # Get host_code from agent
        agent = db.get(CollectorAgent, snap.agent_id)
        hc = agent.host_code if agent else "unknown"
        containers: list[dict[str, Any]] = cast(
            list[dict[str, Any]],
            snap.payload_jsonb.get("containers", []) if snap.payload_jsonb else [],
        )

        for container in containers:
            results.append(
                LiveWorkerStatus(
                    host_code=hc,
                    container_name=container.get("name", ""),
                    image=container.get("image"),
                    status=container.get("status", "unknown"),
                    started_at=container.get("started_at"),
                )
            )

    return results
