"""Router: dashboard — aggregated statistics for the main dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import count

from internalcmdb.collectors.fleet_health import build_fleet_state, derive_agent_status
from internalcmdb.models.collectors import CollectorSnapshot
from internalcmdb.models.discovery import CollectionRun
from internalcmdb.models.registry import (
    Cluster,
    GpuDevice,
    Host,
    ServiceInstance,
    SharedService,
    StorageAsset,
)
from internalcmdb.models.taxonomy import TaxonomyTerm

from ..deps import get_db
from ..schemas.ops import (
    DashboardSummary,
    DiskSummaryItem,
    EnvironmentCount,
    GpuSummaryItem,
    TrendPoint,
    TrendSeries,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Annotated[Session, Depends(get_db)]) -> DashboardSummary:
    host_count = db.scalar(select(count()).select_from(Host)) or 0
    cluster_count = db.scalar(select(count()).select_from(Cluster)) or 0
    service_count = db.scalar(select(count()).select_from(SharedService)) or 0
    service_instance_count = db.scalar(select(count()).select_from(ServiceInstance)) or 0
    gpu_count = (
        db.scalar(select(count()).select_from(Host).where(Host.is_gpu_capable.is_(True))) or 0
    )
    docker_host_count = (
        db.scalar(select(count()).select_from(Host).where(Host.is_docker_host.is_(True))) or 0
    )
    gpu_capable_count = gpu_count

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    runs_24h = (
        db.scalar(
            select(count())
            .select_from(CollectionRun)
            .where(text("started_at >= :cutoff").bindparams(cutoff=cutoff))
        )
        or 0
    )

    last_run_row = db.execute(
        select(CollectionRun.started_at).order_by(CollectionRun.started_at.desc()).limit(1)
    ).first()
    last_run_ts = str(last_run_row[0]) if last_run_row else None

    # Total RAM from latest snapshot per host
    ram_bytes = (
        db.scalar(
            text("""
            SELECT COALESCE(SUM(h.ram_total_bytes), 0)
            FROM (
                SELECT DISTINCT ON (host_id) ram_total_bytes
                FROM registry.host_hardware_snapshot
                ORDER BY host_id, observed_at DESC
            ) h
        """)
        )
        or 0
    )
    total_ram_gb = round(float(ram_bytes) / (1024**3), 2)

    # Total GPU VRAM
    vram_mb = db.scalar(select(func.coalesce(func.sum(GpuDevice.memory_total_mb), 0))) or 0
    total_gpu_vram_gb = round(float(vram_mb) / 1024, 2)

    # Hosts by environment
    env_rows = db.execute(
        select(TaxonomyTerm.term_code, TaxonomyTerm.display_name, count(Host.host_id))
        .join(Host, Host.environment_term_id == TaxonomyTerm.taxonomy_term_id)
        .group_by(TaxonomyTerm.term_code, TaxonomyTerm.display_name)
        .order_by(count(Host.host_id).desc())
    ).all()
    hosts_by_env = [
        EnvironmentCount(term_code=r[0], display_name=r[1], count=r[2]) for r in env_rows
    ]

    # Hosts by lifecycle
    lc_rows = db.execute(
        select(TaxonomyTerm.term_code, TaxonomyTerm.display_name, count(Host.host_id))
        .join(Host, Host.lifecycle_term_id == TaxonomyTerm.taxonomy_term_id)
        .group_by(TaxonomyTerm.term_code, TaxonomyTerm.display_name)
        .order_by(count(Host.host_id).desc())
    ).all()
    hosts_by_lc = [EnvironmentCount(term_code=r[0], display_name=r[1], count=r[2]) for r in lc_rows]

    return DashboardSummary(
        host_count=host_count,
        cluster_count=cluster_count,
        service_count=service_count,
        gpu_count=gpu_count,
        docker_host_count=docker_host_count,
        gpu_capable_count=gpu_capable_count,
        collection_runs_24h=runs_24h,
        last_run_ts=last_run_ts,
        total_ram_gb=total_ram_gb,
        total_gpu_vram_gb=total_gpu_vram_gb,
        service_instance_count=service_instance_count,
        hosts_by_environment=hosts_by_env,
        hosts_by_lifecycle=hosts_by_lc,
    )


@router.get("/gpu-summary", response_model=list[GpuSummaryItem])
def get_gpu_summary(db: Annotated[Session, Depends(get_db)]) -> list[GpuSummaryItem]:
    rows = db.execute(
        select(
            GpuDevice.host_id,
            Host.hostname,
            GpuDevice.gpu_index,
            GpuDevice.model_name,
            GpuDevice.memory_total_mb,
            GpuDevice.memory_used_mb,
            GpuDevice.utilization_gpu_pct,
            GpuDevice.temperature_celsius,
            GpuDevice.power_draw_watts,
        )
        .join(Host, Host.host_id == GpuDevice.host_id)
        .order_by(Host.hostname, GpuDevice.gpu_index)
    ).all()
    return [
        GpuSummaryItem(
            host_id=r[0],
            hostname=r[1],
            gpu_index=r[2],
            model_name=r[3],
            memory_total_mb=r[4],
            memory_used_mb=r[5],
            utilization_gpu_pct=float(r[6]) if r[6] is not None else None,
            temperature_celsius=float(r[7]) if r[7] is not None else None,
            power_draw_watts=float(r[8]) if r[8] is not None else None,
        )
        for r in rows
    ]


@router.get("/disk-summary", response_model=list[DiskSummaryItem])
def get_disk_summary(db: Annotated[Session, Depends(get_db)]) -> list[DiskSummaryItem]:
    rows = db.execute(
        select(
            StorageAsset.host_id,
            Host.hostname,
            StorageAsset.device_name,
            StorageAsset.mountpoint_text,
            StorageAsset.size_bytes,
        )
        .join(Host, Host.host_id == StorageAsset.host_id)
        .order_by(Host.hostname, StorageAsset.device_name)
    ).all()
    result: list[DiskSummaryItem] = []
    for r in rows:
        result.append(
            DiskSummaryItem(
                host_id=r[0],
                hostname=r[1],
                device_name=r[2],
                mountpoint_text=r[3],
                size_bytes=r[4],
                used_pct=None,
            )
        )
    return result


@router.get("/trends", response_model=list[TrendSeries])
def get_trends(db: Annotated[Session, Depends(get_db)]) -> list[TrendSeries]:
    """Return time-series from collection runs: host count and fact count over time."""
    rows = db.execute(
        text("""
            SELECT
                DATE_TRUNC('day', cr.started_at) AS day,
                COUNT(DISTINCT h.host_id) AS host_count,
                COUNT(DISTINCT of_.observed_fact_id) AS fact_count
            FROM discovery.collection_run cr
            LEFT JOIN discovery.observed_fact of_ ON of_.collection_run_id = cr.collection_run_id
            LEFT JOIN registry.host h ON h.host_id = of_.entity_id
            WHERE cr.started_at >= NOW() - INTERVAL '90 days'
            GROUP BY 1
            ORDER BY 1
        """)
    ).all()

    host_points = [TrendPoint(ts=str(r[0]), value=float(r[1])) for r in rows]
    fact_points = [TrendPoint(ts=str(r[0]), value=float(r[2])) for r in rows]

    return [
        TrendSeries(series="host_count", points=host_points),
        TrendSeries(series="fact_count", points=fact_points),
    ]


# ---------------------------------------------------------------------------
# Fleet health extensions
# ---------------------------------------------------------------------------


def _agent_entry(
    agent: object | None,
    host_code: str,
    hostname: str,
) -> dict[str, object]:
    if agent is None:
        return {
            "agent_id": None,
            "host_code": host_code,
            "hostname": hostname,
            "status": "offline",
            "agent_version": None,
            "last_heartbeat_at": None,
            "enrolled_at": None,
            "has_agent": False,
        }
    return {
        "agent_id": str(agent.agent_id),  # type: ignore[union-attr]
        "host_code": host_code,
        "hostname": hostname,
        "status": derive_agent_status(agent),
        "agent_version": agent.agent_version,  # type: ignore[union-attr]
        "last_heartbeat_at": agent.last_heartbeat_at,  # type: ignore[union-attr]
        "enrolled_at": agent.enrolled_at,  # type: ignore[union-attr]
        "has_agent": True,
    }


@router.get("/fleet-health")
def fleet_health_dashboard(
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, object]]:
    """All agents with status, last heartbeat, staleness info.

    Includes both registry-linked hosts AND orphan agents (LXC, external).
    """
    fleet_state = build_fleet_state(db)
    result: list[dict[str, object]] = []
    seen_agent_ids: set[str] = set()

    for host in fleet_state.hosts:
        agent = fleet_state.agents_by_host_id.get(host.host_id)
        if agent:
            seen_agent_ids.add(str(agent.agent_id))
        result.append(_agent_entry(agent, host.host_code, host.hostname))

    for agent in fleet_state.unassigned_agents:
        aid = str(agent.agent_id)
        if aid in seen_agent_ids:
            continue
        seen_agent_ids.add(aid)
        result.append(_agent_entry(agent, agent.host_code, agent.host_code))

    return result


@router.get("/fleet-health/summary")
def fleet_health_summary(
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    """Fleet health summary counts (all agents, not just registry hosts)."""
    fleet_state = build_fleet_state(db)
    counts: dict[str, int] = {"online": 0, "degraded": 0, "offline": 0}

    for host in fleet_state.hosts:
        agent = fleet_state.agents_by_host_id.get(host.host_id)
        status_name = derive_agent_status(agent) if agent else "offline"
        counts[status_name] = counts.get(status_name, 0) + 1

    for agent in fleet_state.unassigned_agents:
        status_name = derive_agent_status(agent)
        counts[status_name] = counts.get(status_name, 0) + 1

    total = len(fleet_state.hosts) + len(fleet_state.unassigned_agents)
    return {
        "online": counts.get("online", 0),
        "degraded": counts.get("degraded", 0),
        "offline": counts.get("offline", 0),
        "total": total,
    }


def _parse_vitals_mem(sv: dict) -> tuple[float | None, float | None]:
    """Return (mem_pct, mem_total_gb) from a system_vitals payload."""
    mem = sv.get("memory_kb") or {}
    mem_total = mem.get("MemTotal", 0)
    mem_avail = mem.get("MemAvailable", 0)
    mem_pct = round((1 - mem_avail / mem_total) * 100, 1) if mem_total > 0 else None
    mem_total_gb = round(mem_total / (1024 * 1024), 1) if mem_total else None
    return mem_pct, mem_total_gb


def _parse_disk_root_pct(disk_snap: object) -> float | None:
    """Return root-partition used_pct from a disk_state payload."""
    disk_data = disk_snap or {}
    if not isinstance(disk_data, dict):
        return None
    disks = disk_data.get("disks", disk_data.get("filesystems", []))
    root_fs = next(
        (fs for fs in disks if fs.get("mountpoint", fs.get("mount")) == "/"),
        None,
    )
    if root_fs is None:
        return None
    raw = root_fs.get("used_pct", root_fs.get("use_pct"))
    if isinstance(raw, str):
        return float(raw.rstrip("%"))
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _parse_docker_counts(docker_snap: object) -> tuple[int, int]:
    """Return (total, running) container counts from a docker_state payload."""
    docker_data = docker_snap or {}
    if not isinstance(docker_data, dict):
        return 0, 0
    containers_list = docker_data.get("containers", [])
    running = sum(
        1 for c in containers_list
        if isinstance(c, dict) and "Up" in str(c.get("status", ""))
    )
    return docker_data.get("total", 0), running


def _latest_snapshot(db: Session, agent_id: object, kind: str) -> object:
    return db.execute(
        select(CollectorSnapshot.payload_jsonb)
        .where(
            CollectorSnapshot.agent_id == agent_id,
            CollectorSnapshot.snapshot_kind == kind,
        )
        .order_by(CollectorSnapshot.collected_at.desc())
        .limit(1)
    ).scalar()


@router.get("/fleet-vitals")
def fleet_vitals(
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, object]]:
    """Latest system vitals per active agent — CPU, RAM, disk, network from snapshots."""
    from internalcmdb.models.collectors import CollectorAgent

    agents = db.scalars(
        select(CollectorAgent).where(
            CollectorAgent.is_active.is_(True),
            CollectorAgent.status != "retired",
        )
    ).all()

    result: list[dict[str, object]] = []
    for agent in agents:
        vitals_snap = db.execute(
            select(CollectorSnapshot.payload_jsonb, CollectorSnapshot.collected_at)
            .where(
                CollectorSnapshot.agent_id == agent.agent_id,
                CollectorSnapshot.snapshot_kind == "system_vitals",
            )
            .order_by(CollectorSnapshot.collected_at.desc())
            .limit(1)
        ).first()

        sv = vitals_snap[0] if vitals_snap else {}
        mem_pct, mem_total_gb = _parse_vitals_mem(sv or {})
        disk_pct = _parse_disk_root_pct(_latest_snapshot(db, agent.agent_id, "disk_state"))
        container_count, running_count = _parse_docker_counts(
            _latest_snapshot(db, agent.agent_id, "docker_state"),
        )

        result.append({
            "agent_id": str(agent.agent_id),
            "host_code": agent.host_code,
            "status": derive_agent_status(agent),
            "last_heartbeat_at": agent.last_heartbeat_at,
            "load_avg": sv.get("load_avg", []) if sv else [],
            "memory_pct": mem_pct,
            "memory_total_gb": mem_total_gb,
            "disk_root_pct": disk_pct,
            "containers_running": running_count,
            "containers_total": container_count,
            "vitals_at": str(vitals_snap[1]) if vitals_snap else None,
        })

    result.sort(key=lambda x: str(x.get("host_code", "")))
    return result


@router.get("/fleet-health/{host_code}/timeline")
def fleet_health_timeline(
    host_code: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, object]]:
    """Heartbeat timeline for a specific host (for sparkline charts)."""
    fleet_state = build_fleet_state(db)
    agent = next(
        (
            fleet_state.agents_by_host_id[host.host_id]
            for host in fleet_state.hosts
            if host.host_code == host_code and host.host_id in fleet_state.agents_by_host_id
        ),
        None,
    )

    if agent is None:
        return []

    snapshots = db.scalars(
        select(CollectorSnapshot)
        .where(
            CollectorSnapshot.agent_id == agent.agent_id,
            CollectorSnapshot.snapshot_kind == "heartbeat",
        )
        .order_by(CollectorSnapshot.collected_at.desc())
        .limit(100)
    ).all()

    return [
        {
            "collected_at": snap.collected_at,
            "load_avg": snap.payload_jsonb.get("load_avg", []) if snap.payload_jsonb else [],
            "memory_pct": snap.payload_jsonb.get("memory_pct") if snap.payload_jsonb else None,
            "uptime_seconds": (
                snap.payload_jsonb.get("uptime_seconds") if snap.payload_jsonb else None
            ),
        }
        for snap in snapshots
    ]
