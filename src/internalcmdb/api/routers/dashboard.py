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


@router.get("/fleet-health")
def fleet_health_dashboard(
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, object]]:
    """All agents with status, last heartbeat, staleness info."""
    fleet_state = build_fleet_state(db)
    result: list[dict[str, object]] = []
    for host in fleet_state.hosts:
        agent = fleet_state.agents_by_host_id.get(host.host_id)
        result.append(
            {
                "agent_id": str(agent.agent_id) if agent else None,
                "host_code": host.host_code,
                "hostname": host.hostname,
                "status": derive_agent_status(agent) if agent else "offline",
                "agent_version": agent.agent_version if agent else None,
                "last_heartbeat_at": agent.last_heartbeat_at if agent else None,
                "enrolled_at": agent.enrolled_at if agent else None,
                "has_agent": agent is not None,
            }
        )
    return result


@router.get("/fleet-health/summary")
def fleet_health_summary(
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    """Fleet health summary counts."""
    fleet_state = build_fleet_state(db)
    counts = {"online": 0, "degraded": 0, "offline": 0}
    for host in fleet_state.hosts:
        agent = fleet_state.agents_by_host_id.get(host.host_id)
        status_name = derive_agent_status(agent) if agent else "offline"
        counts[status_name] = counts.get(status_name, 0) + 1

    return {
        "online": counts.get("online", 0),
        "degraded": counts.get("degraded", 0),
        "offline": counts.get("offline", 0),
        "total": len(fleet_state.hosts),
    }


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
