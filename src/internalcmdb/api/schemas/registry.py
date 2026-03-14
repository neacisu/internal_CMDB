"""Pydantic v2 schemas for registry models."""

from __future__ import annotations

import uuid
from typing import Any

from .common import DatetimeStr, OptDatetimeStr, OptIpStr, OrmBase


class ClusterOut(OrmBase):
    cluster_id: uuid.UUID
    cluster_code: str
    name: str
    description: str | None = None
    created_at: DatetimeStr
    updated_at: DatetimeStr


class GpuDeviceOut(OrmBase):
    gpu_device_id: uuid.UUID
    host_id: uuid.UUID
    gpu_index: int
    vendor_name: str | None = None
    model_name: str | None = None
    uuid_text: str | None = None
    driver_version_text: str | None = None
    memory_total_mb: int | None = None
    memory_used_mb: int | None = None
    memory_free_mb: int | None = None
    utilization_gpu_pct: float | None = None
    utilization_memory_pct: float | None = None
    temperature_celsius: float | None = None
    power_draw_watts: float | None = None
    power_limit_watts: float | None = None
    fan_pct: float | None = None
    compute_capability: str | None = None
    observed_at: DatetimeStr


class HardwareSnapshotOut(OrmBase):
    host_hardware_snapshot_id: uuid.UUID
    host_id: uuid.UUID
    collection_run_id: uuid.UUID
    cpu_model: str | None = None
    cpu_socket_count: int | None = None
    cpu_core_count: int | None = None
    ram_total_bytes: int | None = None
    ram_used_bytes: int | None = None
    ram_free_bytes: int | None = None
    swap_total_bytes: int | None = None
    swap_used_bytes: int | None = None
    gpu_count: int | None = None
    hardware_jsonb: dict[str, Any] | None = None
    observed_at: DatetimeStr


class NetworkInterfaceOut(OrmBase):
    network_interface_id: uuid.UUID
    host_id: uuid.UUID
    interface_name: str
    parent_interface_name: str | None = None
    state_text: str | None = None
    mac_address: str | None = None
    mtu: int | None = None
    is_virtual: bool = False
    metadata_jsonb: dict[str, Any] | None = None
    created_at: DatetimeStr
    updated_at: DatetimeStr


class HostOut(OrmBase):
    host_id: uuid.UUID
    cluster_id: uuid.UUID | None = None
    host_code: str
    hostname: str
    ssh_alias: str | None = None
    fqdn: str | None = None
    os_version_text: str | None = None
    kernel_version_text: str | None = None
    architecture_text: str | None = None
    is_gpu_capable: bool
    is_docker_host: bool
    is_hypervisor: bool
    primary_public_ipv4: OptIpStr = None
    primary_private_ipv4: OptIpStr = None
    observed_hostname: str | None = None
    confidence_score: float | None = None
    metadata_jsonb: dict[str, Any] | None = None
    created_at: DatetimeStr
    updated_at: DatetimeStr


class HostDetailOut(HostOut):
    latest_snapshot: HardwareSnapshotOut | None = None
    gpu_devices: list[GpuDeviceOut] = []  # noqa: RUF012
    network_interfaces: list[NetworkInterfaceOut] = []  # noqa: RUF012


class SharedServiceOut(OrmBase):
    shared_service_id: uuid.UUID
    service_code: str
    name: str
    description: str | None = None
    is_active: bool
    metadata_jsonb: dict[str, Any] | None = None
    created_at: DatetimeStr
    updated_at: DatetimeStr


class ServiceInstanceOut(OrmBase):
    service_instance_id: uuid.UUID
    shared_service_id: uuid.UUID
    host_id: uuid.UUID
    instance_name: str | None = None
    status_text: str | None = None
    observed_at: OptDatetimeStr = None


class StorageAssetOut(OrmBase):
    storage_asset_id: uuid.UUID
    host_id: uuid.UUID
    device_name: str
    model_text: str | None = None
    size_bytes: int | None = None
    is_rotational: bool | None = None
    filesystem_type_text: str | None = None
    mountpoint_text: str | None = None
    metadata_jsonb: dict[str, Any] | None = None
    observed_at: DatetimeStr
