"""Router: collectors — agent enrollment, telemetry ingestion, fleet health."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from internalcmdb.collectors.fleet_health import (
    build_fleet_state,
    derive_agent_status,
    resolve_host,
)
from internalcmdb.collectors.schedule_tiers import DEFAULT_AGENT_CONFIG
from internalcmdb.models.collectors import (
    CollectorAgent,
    CollectorSnapshot,
    SnapshotDiff,
)
from internalcmdb.models.discovery import EvidenceArtifact

from ..config import get_settings
from ..deps import get_db
from ..middleware.rate_limit import rate_limit
from ..middleware.rbac import require_role
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

logger = logging.getLogger(__name__)

_AGENT_NOT_FOUND_DETAIL = "Agent not found"
_DISK_HEAL_THRESHOLD_PCT = 85


@dataclass
class SnapshotData:
    """Groups snapshot payload fields to keep _insert_snapshot_safe args within PLR0913 limit."""

    snapshot_kind: str
    payload_jsonb: dict[str, Any]
    payload_hash: str
    collected_at: str
    tier_code: str


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


def verify_agent_token(
    authorization: Annotated[str | None, Header()] = None,
    x_agent_id: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """Validate HMAC bearer token sent by collector agents.

    Recomputes the expected token from the agent_id and the application
    secret, then performs a timing-safe comparison to prevent oracle attacks.
    """
    if not x_agent_id:
        raise HTTPException(status_code=401, detail="Missing X-Agent-ID header")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    settings = get_settings()

    try:
        agent_id = uuid.UUID(x_agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid agent ID") from exc

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ")
    expected = _generate_agent_token(agent_id, settings.secret_key)

    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid agent token")

    return agent_id


def _lock_agent(db: Session, agent_id: uuid.UUID) -> CollectorAgent | None:
    """Fetch and lock the agent row (SELECT FOR UPDATE).

    Serialises concurrent heartbeat / ingest requests for the same agent,
    preventing both deadlocks and snapshot-version collisions.
    """
    return db.execute(
        select(CollectorAgent).where(CollectorAgent.agent_id == agent_id).with_for_update()
    ).scalar_one_or_none()


def _next_snapshot_version(db: Session, agent_id: uuid.UUID) -> int:
    """Return the next monotonic snapshot version for a given agent.

    MUST be called while the agent row is locked (see _lock_agent).
    """
    current_max = db.scalar(
        select(func.max(CollectorSnapshot.snapshot_version)).where(
            CollectorSnapshot.agent_id == agent_id
        )
    )
    return (current_max or 0) + 1


def _insert_snapshot_safe(
    db: Session,
    agent_id: uuid.UUID,
    data: SnapshotData,
    *,
    max_retries: int = 3,
) -> CollectorSnapshot | None:
    """Insert a snapshot with retry on version conflict.

    Uses SAVEPOINTs so a conflict does not abort the outer transaction.
    """
    for _ in range(max_retries):
        version = _next_snapshot_version(db, agent_id)
        snapshot = CollectorSnapshot(
            snapshot_id=uuid.uuid4(),
            agent_id=agent_id,
            snapshot_version=version,
            snapshot_kind=data.snapshot_kind,
            payload_jsonb=data.payload_jsonb,
            payload_hash=data.payload_hash,
            collected_at=data.collected_at,
            tier_code=data.tier_code,
        )
        nested = db.begin_nested()
        try:
            db.add(snapshot)
            db.flush()
            return snapshot
        except IntegrityError:
            nested.rollback()
    return None


# ---------------------------------------------------------------------------
# Agent enrollment & management
# ---------------------------------------------------------------------------


@router.post("/enroll", response_model=EnrollResponse, status_code=201)
def enroll_agent(
    body: EnrollRequest,
    db: Annotated[Session, Depends(get_db)],
) -> EnrollResponse:
    """Agent self-registers and receives an ID, schedule config, and auth token."""
    host = resolve_host(db, body.host_code)
    host_id = host.host_id if host else None
    effective_host_code = host.host_code if host else body.host_code
    agent_config = {
        **DEFAULT_AGENT_CONFIG,
        "capabilities": body.capabilities,
    }

    existing_agents = db.scalars(
        select(CollectorAgent)
        .where(CollectorAgent.is_active.is_(True))
        .order_by(CollectorAgent.enrolled_at.desc())
    ).all()

    matching_agents: list[CollectorAgent] = []
    normalized_request_host = body.host_code.strip().lower()
    for existing in existing_agents:
        existing_host = existing.host_code.strip().lower()
        if host_id is not None and existing.host_id == host_id:
            matching_agents.append(existing)
            continue
        if existing_host == normalized_request_host:
            matching_agents.append(existing)
            continue
        if effective_host_code.strip().lower() == existing_host:
            matching_agents.append(existing)

    agent: CollectorAgent
    if matching_agents:
        agent = matching_agents[0]
        agent.host_id = host_id
        agent.host_code = effective_host_code
        agent.agent_version = body.agent_version
        agent.agent_config_jsonb = agent_config
        agent.is_active = True
        agent.status = "online"
        for duplicate in matching_agents[1:]:
            duplicate.is_active = False
            duplicate.status = "retired"
    else:
        agent = CollectorAgent(
            agent_id=uuid.uuid4(),
            host_id=host_id,
            host_code=effective_host_code,
            agent_version=body.agent_version,
            agent_config_jsonb=agent_config,
            status="online",
        )
        db.add(agent)

    db.commit()

    settings = get_settings()
    token = _generate_agent_token(agent.agent_id, settings.secret_key)

    tiers: dict[str, int] = DEFAULT_AGENT_CONFIG["tiers"]  # type: ignore[assignment]
    collectors: list[str] = DEFAULT_AGENT_CONFIG["enabled_collectors"]  # type: ignore[assignment]

    return EnrollResponse(
        agent_id=agent.agent_id,
        schedule_tiers=tiers,
        enabled_collectors=collectors,
        api_token=token,
    )


@router.get(
    "/agents",
    response_model=list[AgentOut],
    dependencies=[Depends(require_role("admin", "operator", "viewer"))],
)
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
    agents = db.scalars(stmt).all()
    for agent in agents:
        agent.status = derive_agent_status(agent)
    return agents  # type: ignore[return-value]


@router.get(
    "/agents/{agent_id}",
    response_model=AgentOut,
    dependencies=[Depends(require_role("admin", "operator", "viewer"))],
)
def get_agent(
    agent_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> CollectorAgent:
    agent = db.get(CollectorAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=_AGENT_NOT_FOUND_DETAIL)
    agent.status = derive_agent_status(agent)
    return agent


@router.put(
    "/agents/{agent_id}/config",
    response_model=AgentOut,
    dependencies=[Depends(require_role("admin", "operator"))],
)
def update_agent_config(
    agent_id: uuid.UUID,
    body: AgentConfigUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CollectorAgent:
    agent = db.get(CollectorAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=_AGENT_NOT_FOUND_DETAIL)

    config = dict(agent.agent_config_jsonb or {})
    if body.tiers is not None:
        config["tiers"] = body.tiers
    if body.enabled_collectors is not None:
        config["enabled_collectors"] = body.enabled_collectors
    agent.agent_config_jsonb = config
    db.commit()
    db.refresh(agent)
    return agent


@router.delete(
    "/agents/{agent_id}",
    status_code=204,
    dependencies=[Depends(require_role("admin"))],
)
def retire_agent(
    agent_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    agent = db.get(CollectorAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=_AGENT_NOT_FOUND_DETAIL)
    agent.is_active = False
    agent.status = "retired"
    db.commit()


# ---------------------------------------------------------------------------
# Cognitive reactive evaluation
# ---------------------------------------------------------------------------


def _extract_root_usage(disk_payload: dict[str, Any]) -> float:
    """Parse root filesystem usage percentage from a disk_state snapshot payload."""
    for d in cast(list[dict[str, Any]], disk_payload.get("disks") or []):
        if d.get("mountpoint") == "/":
            raw = str(d.get("used_pct", "0")).replace("%", "")
            try:
                return float(raw)
            except ValueError:
                pass
            break
    return 0.0


def _trigger_cognitive_reactions(
    background_tasks: BackgroundTasks,
    body: IngestRequest,
    agent: CollectorAgent,
) -> None:
    """Evaluate incoming snapshots for cognitive self-heal triggers.

    Called after each successful ingest commit.  When a ``disk_state``
    snapshot exceeds the threshold, a background task enqueues the
    ``self_heal_check`` ARQ job so the worker reacts in near-real-time.
    """
    for item in body.snapshots:
        if item.snapshot_kind != "disk_state":
            continue
        payload = item.payload or {}
        root_pct = _extract_root_usage(payload)
        if root_pct >= _DISK_HEAL_THRESHOLD_PCT:
            host_code = agent.host_code or str(body.agent_id)
            background_tasks.add_task(_enqueue_cognitive_self_heal, host_code, root_pct)
            break


def _enqueue_cognitive_self_heal(host_code: str, disk_pct: float) -> None:
    """Enqueue ``self_heal_check`` via ARQ when disk threshold is breached.

    Runs as a FastAPI background task (sync thread) after the ingest
    response is already sent to the agent — zero latency impact on
    the ingestion path.
    """
    import asyncio  # noqa: PLC0415

    async def _enqueue() -> None:
        from arq import create_pool as arq_create_pool  # noqa: PLC0415
        from arq.connections import RedisSettings  # noqa: PLC0415

        settings = get_settings()
        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        pool = await arq_create_pool(redis_settings)
        await pool.enqueue_job("self_heal_check")
        await pool.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_enqueue())
        logger.info(
            "Cognitive reaction: enqueued self_heal_check for %s (disk %.1f%%)",
            host_code,
            disk_pct,
        )
    except Exception:
        logger.warning(
            "Failed to enqueue cognitive self-heal for %s",
            host_code,
            exc_info=True,
        )
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# SSE vitals publish  (fire-and-forget, runs as background task)
# ---------------------------------------------------------------------------

_VITALS_CHANNEL = "infraq:cmdb:vitals"


class _VitalExtras:
    """Bundled optional payloads for SSE vital construction — avoids PLR0913."""

    __slots__ = ("disk", "docker", "gpu")

    def __init__(
        self,
        disk: dict[str, Any] | None = None,
        gpu: dict[str, Any] | None = None,
        docker: dict[str, Any] | None = None,
    ) -> None:
        self.disk = disk
        self.gpu = gpu
        self.docker = docker


def _parse_vital_disk(disk_payload: dict[str, Any] | None) -> float | None:
    """Extract root-partition used_pct from a disk_state payload dict."""
    if not disk_payload:
        return None
    disks = disk_payload.get("disks", disk_payload.get("filesystems", []))
    root_fs = next((d for d in disks if d.get("mountpoint", d.get("mount")) == "/"), None)
    if root_fs is None:
        return None
    raw = root_fs.get("used_pct", root_fs.get("use_pct"))
    if isinstance(raw, str):
        return float(raw.rstrip("%"))
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _parse_vital_gpu(gpu_payload: dict[str, Any] | None) -> float | None:
    """Extract max utilization_gpu_pct from a gpu_state payload dict."""
    if not gpu_payload:
        return None
    gpus = gpu_payload.get("gpus", [])
    pcts = [
        g["utilization_gpu_pct"]
        for g in gpus
        if isinstance(g, dict) and g.get("utilization_gpu_pct") is not None
    ]
    return round(max(pcts), 1) if pcts else None


_HEALTH_RE = re.compile(r"\(([a-z]+)\)", re.IGNORECASE)


def _container_health(c: dict[str, Any]) -> str:
    """Extract health from container — prefers 'health' field, falls back to status string."""
    if h := c.get("health"):
        return str(h).lower()
    return m.group(1).lower() if (m := _HEALTH_RE.search(str(c.get("status", "")))) else ""


def _parse_vital_docker(docker_payload: dict[str, Any] | None) -> tuple[int, int, int, int]:
    """Return (total, running, healthy, unhealthy) from a docker_state payload dict."""
    if not docker_payload:
        return 0, 0, 0, 0
    containers_list = cast(list[dict[str, Any]], docker_payload.get("containers") or [])
    total = int(docker_payload.get("total") or len(containers_list))
    running = sum(1 for c in containers_list if "Up" in str(c.get("status", "")))
    healthy = sum(1 for c in containers_list if _container_health(c) == "healthy")
    unhealthy = sum(1 for c in containers_list if _container_health(c) == "unhealthy")
    return total, running, healthy, unhealthy


def _build_vital_dict(
    agent: CollectorAgent,
    sv_payload: dict[str, Any],
    extras: _VitalExtras,
    vitals_at: str,
) -> dict[str, Any]:
    """Build a FleetVital-shaped dict from raw snapshot payloads."""
    mem = sv_payload.get("memory_kb") or {}
    mem_total = float(mem.get("MemTotal") or 0)
    mem_avail = float(mem.get("MemAvailable") or mem.get("MemFree") or 0)
    mem_pct = round((mem_total - mem_avail) / mem_total * 100, 1) if mem_total > 0 else None
    mem_total_gb = round(mem_total / (1024 * 1024), 1) if mem_total else None

    containers_total, containers_running, containers_healthy, containers_unhealthy = (
        _parse_vital_docker(extras.docker)
    )

    return {
        "agent_id": str(agent.agent_id),
        "host_code": agent.host_code,
        "status": "online",
        "last_heartbeat_at": vitals_at,
        "load_avg": sv_payload.get("load_avg", []),
        "cpu_pct": sv_payload.get("cpu_pct"),
        "memory_pct": mem_pct,
        "memory_total_gb": mem_total_gb,
        "disk_root_pct": _parse_vital_disk(extras.disk),
        "containers_running": containers_running,
        "containers_total": containers_total,
        "containers_healthy": containers_healthy,
        "containers_unhealthy": containers_unhealthy,
        "gpu_pct": _parse_vital_gpu(extras.gpu),
        "vitals_at": vitals_at,
    }


def _publish_vital_to_sse(vital: dict[str, Any]) -> None:
    """Publish a FleetVital dict to Redis pub/sub channel for SSE consumers.

    Runs as a FastAPI background task — decoupled from the HTTP response.
    Failures are silently swallowed to avoid disrupting the ingest path.
    """
    try:
        import redis as _syncredis  # noqa: PLC0415

        settings = get_settings()
        r = _syncredis.from_url(settings.redis_url, decode_responses=True)
        try:
            r.publish(_VITALS_CHANNEL, json.dumps(vital))
        finally:
            r.close()
    except Exception:
        logger.debug("SSE vitals publish failed", exc_info=True)


def _trigger_sse_vitals_publish(
    background_tasks: BackgroundTasks,
    body: IngestRequest,
    agent: CollectorAgent,
    vitals_at: str,
    db: Session,
) -> None:
    """Collect system_vitals (+ co-occurring disk/gpu/docker) and schedule
    a Redis publish so SSE consumers get sub-second delivery."""
    snapshot_map: dict[str, dict[str, Any]] = {}
    for item in body.snapshots:
        snapshot_map[item.snapshot_kind] = item.payload or {}

    sv_payload = snapshot_map.get("system_vitals")
    if sv_payload is None:
        return  # no vitals in this batch — nothing to push

    def _latest_db_payload(kind: str) -> dict[str, Any] | None:
        """Look up the latest snapshot of *kind* for this agent from the DB."""
        row = db.execute(
            select(CollectorSnapshot.payload_jsonb)
            .where(
                CollectorSnapshot.agent_id == agent.agent_id,
                CollectorSnapshot.snapshot_kind == kind,
            )
            .order_by(CollectorSnapshot.collected_at.desc())
            .limit(1)
        ).scalar()
        return row if isinstance(row, dict) else None

    vital = _build_vital_dict(
        agent=agent,
        sv_payload=sv_payload,
        extras=_VitalExtras(
            disk=snapshot_map.get("disk_state") or _latest_db_payload("disk_state"),
            gpu=snapshot_map.get("gpu_state") or _latest_db_payload("gpu_state"),
            docker=snapshot_map.get("docker_state") or _latest_db_payload("docker_state"),
        ),
        vitals_at=vitals_at,
    )
    background_tasks.add_task(_publish_vital_to_sse, vital)


# ---------------------------------------------------------------------------
# Telemetry ingestion
# ---------------------------------------------------------------------------


@router.post("/ingest", response_model=IngestResponse)
@rate_limit("60/minute")
def ingest_snapshots(
    request: Request,
    body: IngestRequest,
    db: Annotated[Session, Depends(get_db)],
    authenticated_agent_id: Annotated[uuid.UUID, Depends(verify_agent_token)],
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
) -> IngestResponse:
    """Receive a batch of snapshots from an agent."""
    if body.agent_id != authenticated_agent_id:
        raise HTTPException(
            status_code=403,
            detail="Token agent ID does not match request body agent_id",
        )

    agent = _lock_agent(db, body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=_AGENT_NOT_FOUND_DETAIL)

    accepted = 0
    deduplicated = 0
    errors: list[str] = []

    for item in body.snapshots:
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

        snapshot = _insert_snapshot_safe(
            db,
            body.agent_id,
            SnapshotData(
                snapshot_kind=item.snapshot_kind,
                payload_jsonb=item.payload,
                payload_hash=item.payload_hash,
                collected_at=item.collected_at,
                tier_code=item.tier_code,
            ),
        )
        if snapshot is None:
            errors.append(f"Failed to insert snapshot kind={item.snapshot_kind}")
            continue

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

    agent.last_heartbeat_at = str(datetime.now(UTC))
    agent.status = "online"
    db.commit()

    try:
        from internalcmdb.observability.metrics import COLLECTOR_INGEST_TOTAL  # noqa: PLC0415

        host_code = agent.host_code or str(body.agent_id)
        for item in body.snapshots:
            COLLECTOR_INGEST_TOTAL.labels(host=host_code, kind=item.snapshot_kind).inc()
    except Exception:
        logger.debug("Ingest metrics counter unavailable", exc_info=True)

    _trigger_cognitive_reactions(background_tasks, body, agent)
    _trigger_sse_vitals_publish(background_tasks, body, agent, str(datetime.now(UTC)), db)

    return IngestResponse(accepted=accepted, deduplicated=deduplicated, errors=errors)


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(
    body: HeartbeatRequest,
    db: Annotated[Session, Depends(get_db)],
    authenticated_agent_id: Annotated[uuid.UUID, Depends(verify_agent_token)],
) -> HeartbeatResponse:
    """Lightweight keep-alive from an agent."""
    if body.agent_id != authenticated_agent_id:
        raise HTTPException(
            status_code=403,
            detail="Token agent ID does not match request body agent_id",
        )

    agent = _lock_agent(db, body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=_AGENT_NOT_FOUND_DETAIL)

    agent.last_heartbeat_at = str(datetime.now(UTC))
    agent.agent_version = body.agent_version
    agent.status = "online"

    payload = {
        "uptime_seconds": body.uptime_seconds,
        "load_avg": body.load_avg,
        "memory_pct": body.memory_pct,
    }
    payload_bytes = str(sorted(payload.items())).encode()
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()

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
        _insert_snapshot_safe(
            db,
            body.agent_id,
            SnapshotData(
                snapshot_kind="heartbeat",
                payload_jsonb=payload,
                payload_hash=payload_hash,
                collected_at=str(datetime.now(UTC)),
                tier_code="5s",
            ),
        )

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
    """Aggregate live health across all agents (registry + orphan)."""
    fleet_state = build_fleet_state(db)
    counts: dict[str, int] = {"online": 0, "degraded": 0, "offline": 0, "retired": 0}

    for host in fleet_state.hosts:
        agent = fleet_state.agents_by_host_id.get(host.host_id)
        status_name = derive_agent_status(agent) if agent else "offline"
        counts[status_name] = counts.get(status_name, 0) + 1

    for agent in fleet_state.unassigned_agents:
        status_name = derive_agent_status(agent)
        counts[status_name] = counts.get(status_name, 0) + 1

    total_entities = len(fleet_state.hosts) + len(fleet_state.unassigned_agents)
    total_agents = len(fleet_state.agents_by_host_id) + len(fleet_state.unassigned_agents)

    return FleetHealthSummary(
        online=counts.get("online", 0),
        degraded=counts.get("degraded", 0),
        offline=counts.get("offline", 0),
        retired=counts.get("retired", 0),
        total=total_entities,
        registered_agents=total_agents,
        expected_hosts=len(fleet_state.hosts),
        unassigned_agents=len(fleet_state.unassigned_agents),
    )


@router.get("/health/{host_code}", response_model=HostHealth)
def host_health(
    host_code: str,
    db: Annotated[Session, Depends(get_db)],
) -> HostHealth:
    """Per-host live health from the latest heartbeat snapshot."""
    host = resolve_host(db, host_code)
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")

    fleet_state = build_fleet_state(db)
    agent = fleet_state.agents_by_host_id.get(host.host_id)
    if agent is None:
        return HostHealth(
            agent_id=None,
            host_code=host.host_code,
            status="offline",
            agent_version=None,
            last_heartbeat_at=None,
            uptime_seconds=None,
            load_avg=[],
            memory_pct=None,
        )

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
        host_code=host.host_code,
        status=derive_agent_status(agent),
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


@router.post(
    "/reports/generate",
    response_model=ReportOut,
    status_code=201,
    dependencies=[Depends(require_role("admin", "operator"))],
)
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
