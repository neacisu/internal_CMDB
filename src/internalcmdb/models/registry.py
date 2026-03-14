"""Schema: registry — hosts, clusters, services, network, storage."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import CIDR, INET, JSONB, MACADDR, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Cluster(Base):
    __tablename__ = "cluster"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    cluster_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cluster_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    environment_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    lifecycle_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    canonical_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "docs.document.document_id",
            use_alter=True,
            name="fk_cluster_canonical_document",
        ),
        nullable=True,
    )
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class Host(Base):
    __tablename__ = "host"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    host_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("registry.cluster.cluster_id"), nullable=True
    )
    host_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    hostname: Mapped[str] = mapped_column(Text, nullable=False)
    ssh_alias: Mapped[str | None] = mapped_column(Text)
    fqdn: Mapped[str | None] = mapped_column(Text)
    entity_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    primary_host_role_term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=True
    )
    environment_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    lifecycle_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    os_family_term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=True
    )
    os_version_text: Mapped[str | None] = mapped_column(Text)
    kernel_version_text: Mapped[str | None] = mapped_column(Text)
    architecture_text: Mapped[str | None] = mapped_column(Text)
    is_gpu_capable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_docker_host: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_hypervisor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primary_public_ipv4: Mapped[str | None] = mapped_column(INET)
    primary_private_ipv4: Mapped[str | None] = mapped_column(INET)
    observed_hostname: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class HostRoleAssignment(Base):
    __tablename__ = "host_role_assignment"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    host_role_assignment_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry.host.host_id"), nullable=False)
    host_role_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assignment_source_text: Mapped[str | None] = mapped_column(Text)
    collection_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=True
    )
    observed_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class ClusterMembership(Base):
    __tablename__ = "cluster_membership"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    cluster_membership_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registry.cluster.cluster_id"), nullable=False
    )
    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry.host.host_id"), nullable=False)
    membership_role_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    member_node_name_text: Mapped[str | None] = mapped_column(Text)
    member_node_id_text: Mapped[str | None] = mapped_column(Text)
    membership_source_text: Mapped[str | None] = mapped_column(Text)
    is_quorate_member: Mapped[bool | None] = mapped_column(Boolean)
    collection_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=True
    )
    observed_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class HostHardwareSnapshot(Base):
    __tablename__ = "host_hardware_snapshot"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    host_hardware_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry.host.host_id"), nullable=False)
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=False
    )
    cpu_model: Mapped[str | None] = mapped_column(Text)
    cpu_socket_count: Mapped[int | None] = mapped_column(Integer)
    cpu_core_count: Mapped[int | None] = mapped_column(Integer)
    ram_total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    ram_used_bytes: Mapped[int | None] = mapped_column(BigInteger)
    ram_free_bytes: Mapped[int | None] = mapped_column(BigInteger)
    swap_total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    swap_used_bytes: Mapped[int | None] = mapped_column(BigInteger)
    gpu_count: Mapped[int | None] = mapped_column(Integer)
    hardware_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    observed_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class GpuDevice(Base):
    __tablename__ = "gpu_device"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    gpu_device_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry.host.host_id"), nullable=False)
    gpu_index: Mapped[int] = mapped_column(Integer, nullable=False)
    vendor_name: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    uuid_text: Mapped[str | None] = mapped_column(Text)
    driver_version_text: Mapped[str | None] = mapped_column(Text)
    memory_total_mb: Mapped[int | None] = mapped_column(Integer)
    memory_used_mb: Mapped[int | None] = mapped_column(Integer)
    memory_free_mb: Mapped[int | None] = mapped_column(Integer)
    utilization_gpu_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    utilization_memory_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    temperature_celsius: Mapped[float | None] = mapped_column(Numeric(5, 2))
    power_draw_watts: Mapped[float | None] = mapped_column(Numeric(8, 2))
    power_limit_watts: Mapped[float | None] = mapped_column(Numeric(8, 2))
    fan_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    compute_capability: Mapped[str | None] = mapped_column(Text)
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=False
    )
    observed_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class NetworkSegment(Base):
    __tablename__ = "network_segment"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    network_segment_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    segment_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    segment_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    environment_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    cidr: Mapped[str | None] = mapped_column(CIDR)
    vlan_id_text: Mapped[str | None] = mapped_column(Text)
    mtu: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    source_of_truth: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class NetworkInterface(Base):
    __tablename__ = "network_interface"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    network_interface_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry.host.host_id"), nullable=False)
    network_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("registry.network_segment.network_segment_id"), nullable=True
    )
    interface_name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_interface_name: Mapped[str | None] = mapped_column(Text)
    interface_kind_term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=True
    )
    state_text: Mapped[str | None] = mapped_column(Text)
    mac_address: Mapped[str | None] = mapped_column(MACADDR)
    mtu: Mapped[int | None] = mapped_column(Integer)
    is_virtual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class IpAddressAssignment(Base):
    __tablename__ = "ip_address_assignment"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    ip_address_assignment_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    network_interface_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registry.network_interface.network_interface_id"), nullable=False
    )
    network_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("registry.network_segment.network_segment_id"), nullable=True
    )
    address: Mapped[str] = mapped_column(INET, nullable=False)
    prefix_length: Mapped[int | None] = mapped_column(Integer)
    address_scope_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    observed_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=False
    )


class RouteEntry(Base):
    __tablename__ = "route_entry"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    route_entry_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry.host.host_id"), nullable=False)
    network_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("registry.network_segment.network_segment_id"), nullable=True
    )
    destination_cidr: Mapped[str | None] = mapped_column(CIDR)
    gateway_ip: Mapped[str | None] = mapped_column(INET)
    device_name: Mapped[str | None] = mapped_column(Text)
    route_type_text: Mapped[str | None] = mapped_column(Text)
    is_default_route: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_route_text: Mapped[str | None] = mapped_column(Text)
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=False
    )
    observed_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class DnsResolverState(Base):
    __tablename__ = "dns_resolver_state"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    dns_resolver_state_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry.host.host_id"), nullable=False)
    resolver_list_text: Mapped[str | None] = mapped_column(Text)
    resolver_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=False
    )
    observed_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class StorageAsset(Base):
    __tablename__ = "storage_asset"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    storage_asset_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry.host.host_id"), nullable=False)
    storage_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    device_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_text: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    is_rotational: Mapped[bool | None] = mapped_column(Boolean)
    filesystem_type_text: Mapped[str | None] = mapped_column(Text)
    mountpoint_text: Mapped[str | None] = mapped_column(Text)
    backing_device_text: Mapped[str | None] = mapped_column(Text)
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=False
    )
    observed_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class SharedService(Base):
    __tablename__ = "shared_service"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    shared_service_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    service_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    service_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    environment_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    lifecycle_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text)
    canonical_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "docs.document.document_id",
            use_alter=True,
            name="fk_shared_service_canonical_document",
        ),
        nullable=True,
    )
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class ServiceInstance(Base):
    __tablename__ = "service_instance"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    service_instance_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    shared_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registry.shared_service.shared_service_id"), nullable=False
    )
    host_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("registry.host.host_id"), nullable=True
    )
    runtime_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    instance_name: Mapped[str] = mapped_column(Text, nullable=False)
    container_name: Mapped[str | None] = mapped_column(Text)
    systemd_unit_name: Mapped[str | None] = mapped_column(Text)
    compose_project_name: Mapped[str | None] = mapped_column(Text)
    image_reference: Mapped[str | None] = mapped_column(Text)
    version_text: Mapped[str | None] = mapped_column(Text)
    status_text: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    collection_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=True
    )
    observed_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))


class ServiceExposure(Base):
    __tablename__ = "service_exposure"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    service_exposure_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    service_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registry.service_instance.service_instance_id"), nullable=False
    )
    exposure_method_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    design_source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "docs.document.document_id",
            use_alter=True,
            name="fk_service_exposure_design_doc",
        ),
        nullable=True,
    )
    hostname: Mapped[str | None] = mapped_column(Text)
    host_ip: Mapped[str | None] = mapped_column(INET)
    listen_port: Mapped[int | None] = mapped_column(Integer)
    backend_host: Mapped[str | None] = mapped_column(Text)
    backend_port: Mapped[int | None] = mapped_column(Integer)
    protocol_text: Mapped[str | None] = mapped_column(Text)
    sni_hostname: Mapped[str | None] = mapped_column(Text)
    path_prefix: Mapped[str | None] = mapped_column(Text)
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_declared_in_design: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_tls_terminated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_live_probe_success: Mapped[bool | None] = mapped_column(Boolean)
    observed_health_term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=True
    )
    probe_confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    last_probe_result_text: Mapped[str | None] = mapped_column(Text)
    last_probe_checked_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    metadata_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    collection_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=True
    )
    observed_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))


class ServiceDependency(Base):
    __tablename__ = "service_dependency"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    service_dependency_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_service_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registry.service_instance.service_instance_id"), nullable=False
    )
    target_service_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("registry.service_instance.service_instance_id"), nullable=True
    )
    target_shared_service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("registry.shared_service.shared_service_id"), nullable=True
    )
    relationship_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    dependency_role_text: Mapped[str | None] = mapped_column(Text)
    is_hard_dependency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    collection_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery.collection_run.collection_run_id"), nullable=True
    )
    observed_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))


class OwnershipAssignment(Base):
    __tablename__ = "ownership_assignment"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "registry"}

    ownership_assignment_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_kind_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    owner_type_term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"), nullable=False
    )
    owner_code: Mapped[str] = mapped_column(Text, nullable=False)
    responsibility_text: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_from: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    valid_to: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
