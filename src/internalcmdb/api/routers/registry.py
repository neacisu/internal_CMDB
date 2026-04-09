"""Router: registry — hosts, clusters, services, GPU devices, network interfaces."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from internalcmdb.models.registry import (
    Cluster,
    GpuDevice,
    Host,
    HostHardwareSnapshot,
    NetworkInterface,
    ServiceInstance,
    SharedService,
    StorageAsset,
)

from ..deps import get_db
from ..schemas.common import Page, PageMeta, paginate
from ..schemas.registry import (
    ClusterOut,
    GpuDeviceOut,
    HardwareSnapshotOut,
    HostDetailOut,
    HostOut,
    NetworkInterfaceOut,
    ServiceInstanceOut,
    SharedServiceOut,
    StorageAssetOut,
)

router = APIRouter(prefix="/registry", tags=["registry"])


@dataclass
class HostFilterParams:
    """Query-parameter filter group for host listing."""

    cluster_id: uuid.UUID | None = None
    gpu_capable: bool | None = None
    docker_host: bool | None = None


@router.get("/clusters", response_model=list[ClusterOut])
def list_clusters(db: Annotated[Session, Depends(get_db)]) -> list[Cluster]:
    return db.scalars(select(Cluster).order_by(Cluster.name)).all()  # type: ignore[return-value]


@router.get("/hosts", response_model=Page[HostOut])
def list_hosts(
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[HostFilterParams, Depends()],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[HostOut]:
    q = db.query(Host)
    if filters.cluster_id is not None:
        q = q.filter(Host.cluster_id == filters.cluster_id)
    if filters.gpu_capable is not None:
        q = q.filter(Host.is_gpu_capable == filters.gpu_capable)
    if filters.docker_host is not None:
        q = q.filter(Host.is_docker_host == filters.docker_host)
    q = q.order_by(Host.hostname)
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


@router.get("/hosts/{host_id}", response_model=HostDetailOut)
def get_host(host_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> HostDetailOut:
    host = db.get(Host, host_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")

    latest_snapshot = db.scalars(
        select(HostHardwareSnapshot)
        .where(HostHardwareSnapshot.host_id == host_id)
        .order_by(HostHardwareSnapshot.observed_at.desc())
        .limit(1)
    ).first()

    gpu_devices = db.scalars(
        select(GpuDevice).where(GpuDevice.host_id == host_id).order_by(GpuDevice.gpu_index)
    ).all()

    network_interfaces = db.scalars(
        select(NetworkInterface)
        .where(NetworkInterface.host_id == host_id)
        .order_by(NetworkInterface.interface_name)
    ).all()

    return HostDetailOut(
        **HostOut.model_validate(host).model_dump(),
        latest_snapshot=(
            HardwareSnapshotOut.model_validate(latest_snapshot) if latest_snapshot else None
        ),
        gpu_devices=[GpuDeviceOut.model_validate(g) for g in gpu_devices],
        network_interfaces=[NetworkInterfaceOut.model_validate(n) for n in network_interfaces],
    )


@router.get("/gpu-devices", response_model=Page[GpuDeviceOut])
def list_gpu_devices(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    host_id: uuid.UUID | None = None,
) -> Page[GpuDeviceOut]:
    q = db.query(GpuDevice)
    if host_id is not None:
        q = q.filter(GpuDevice.host_id == host_id)
    q = q.order_by(GpuDevice.observed_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


@router.get("/network/interfaces", response_model=Page[NetworkInterfaceOut])
def list_network_interfaces(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    host_id: uuid.UUID | None = None,
) -> Page[NetworkInterfaceOut]:
    q = db.query(NetworkInterface)
    if host_id is not None:
        q = q.filter(NetworkInterface.host_id == host_id)
    q = q.order_by(NetworkInterface.interface_name)
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


@router.get("/services", response_model=list[SharedServiceOut])
def list_services(db: Annotated[Session, Depends(get_db)]) -> list[SharedService]:
    return (
        db.scalars(select(SharedService).order_by(SharedService.name)).all()  # type: ignore[return-value]
    )


@router.get("/services/{service_id}/instances", response_model=list[ServiceInstanceOut])
def list_service_instances(
    service_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[ServiceInstance]:
    return db.scalars(  # type: ignore[return-value]
        select(ServiceInstance).where(ServiceInstance.shared_service_id == service_id)
    ).all()


@router.get("/storage", response_model=Page[StorageAssetOut])
def list_storage(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    host_id: uuid.UUID | None = None,
) -> Page[StorageAssetOut]:
    q = db.query(StorageAsset)
    if host_id is not None:
        q = q.filter(StorageAsset.host_id == host_id)
    q = q.order_by(StorageAsset.host_id, StorageAsset.device_name)
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))
