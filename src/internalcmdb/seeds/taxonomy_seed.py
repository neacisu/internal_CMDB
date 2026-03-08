"""Taxonomy seed — idempotent upsert of all 22 Wave-1 vocabulary domains and their terms.

Usage (from repo root, after PostgreSQL is up and schemas are migrated):

    export $(grep -v '^#' .env | xargs)
    PYTHONPATH=src .venv/bin/python -m internalcmdb.seeds.taxonomy_seed

The script is fully idempotent: re-running it is safe and will not create
duplicates. It uses INSERT … ON CONFLICT DO NOTHING for both domains and terms.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert as pg_insert

# ---------------------------------------------------------------------------
# Domain + term catalogue
# ---------------------------------------------------------------------------

# Each entry: (domain_code, name, description, [(term_code, display_name), ...])
_CATALOGUE: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    (
        "entity_kind",
        "Entity Kind",
        "Canonical classification of every traceable entity in the registry.",
        [
            ("cluster", "Cluster"),
            ("proxmox_cluster", "Proxmox Cluster"),
            ("host", "Host"),
            ("host_role_assignment", "Host Role Assignment"),
            ("cluster_membership", "Cluster Membership"),
            ("host_hardware_snapshot", "Host Hardware Snapshot"),
            ("gpu_device", "GPU Device"),
            ("shared_service", "Shared Service"),
            ("service_instance", "Service Instance"),
            ("service_exposure", "Service Exposure"),
            ("service_dependency", "Service Dependency"),
            ("network_segment", "Network Segment"),
            ("network_interface", "Network Interface"),
            ("ip_address_assignment", "IP Address Assignment"),
            ("route_entry", "Route Entry"),
            ("dns_resolver_state", "DNS Resolver State"),
            ("storage_asset", "Storage Asset"),
            ("ownership_assignment", "Ownership Assignment"),
            ("document", "Document"),
            ("document_version", "Document Version"),
            ("document_entity_binding", "Document Entity Binding"),
            ("document_chunk", "Document Chunk"),
            ("chunk_embedding", "Chunk Embedding"),
            ("evidence_pack", "Evidence Pack"),
            ("evidence_pack_item", "Evidence Pack Item"),
            ("discovery_source", "Discovery Source"),
            ("collection_run", "Collection Run"),
            ("observed_fact", "Observed Fact"),
            ("evidence_artifact", "Evidence Artifact"),
            ("reconciliation_result", "Reconciliation Result"),
            ("prompt_template_registry", "Prompt Template Registry"),
            ("agent_run", "Agent Run"),
            ("agent_evidence", "Agent Evidence"),
            ("action_request", "Action Request"),
            ("policy_record", "Policy Record"),
            ("approval_record", "Approval Record"),
            ("change_log", "Change Log"),
        ],
    ),
    (
        "host_role",
        "Host Role",
        "Functional role a host fulfils within the platform.",
        [
            ("physical_cluster_node", "Physical Cluster Node"),
            ("proxmox_hypervisor", "Proxmox Hypervisor"),
            ("proxmox_cluster_member", "Proxmox Cluster Member"),
            ("standalone_proxmox_host", "Standalone Proxmox Host"),
            ("gpu_inference_node", "GPU Inference Node"),
            ("application_runtime_host", "Application Runtime Host"),
            ("shared_service_host", "Shared Service Host"),
            ("edge_gateway_host", "Edge Gateway Host"),
            ("database_host", "Database Host"),
            ("monitored_host", "Monitored Host"),
            ("observability_host", "Observability Host"),
            ("mail_collaboration_host", "Mail / Collaboration Host"),
            ("automation_host", "Automation Host"),
            ("development_runtime_host", "Development Runtime Host"),
        ],
    ),
    (
        "environment",
        "Environment",
        "Deployment environment / promotion tier.",
        [
            ("production", "Production"),
            ("shared-platform", "Shared Platform"),
            ("development", "Development"),
            ("staging", "Staging"),
            ("bootstrap", "Bootstrap"),
        ],
    ),
    (
        "service_kind",
        "Service Kind",
        "Canonical product or class of a service instance (not the instance identifier).",
        [
            ("postgresql", "PostgreSQL"),
            ("pgbouncer", "PgBouncer"),
            ("redis", "Redis"),
            ("traefik", "Traefik"),
            ("openbao", "OpenBao"),
            ("zitadel", "Zitadel"),
            ("grafana", "Grafana"),
            ("prometheus", "Prometheus"),
            ("loki", "Loki"),
            ("tempo", "Tempo"),
            ("otel_collector", "OpenTelemetry Collector"),
            ("cadvisor", "cAdvisor"),
            ("node_exporter", "Node Exporter"),
            ("pve_exporter", "PVE Exporter"),
            ("postgres_exporter", "Postgres Exporter"),
            ("oauth2_proxy", "OAuth2 Proxy"),
            ("vllm", "vLLM"),
            ("ollama", "Ollama"),
            ("open_webui", "Open WebUI"),
            ("n8n", "n8n"),
            ("activepieces", "Activepieces"),
            ("cloudbeaver", "CloudBeaver"),
            ("watchtower", "Watchtower"),
            ("kafka", "Kafka"),
            ("neo4j", "Neo4j"),
            ("temporal", "Temporal"),
            ("roundcube", "Roundcube"),
            ("stalwart", "Stalwart"),
            ("llm_guard", "LLM Guard"),
            ("mail_gateway", "Mail Gateway"),
            ("api_gateway", "API Gateway"),
            ("application_api", "Application API"),
            ("application_worker", "Application Worker"),
            ("web_frontend", "Web Frontend"),
            ("job_scheduler", "Job Scheduler"),
        ],
    ),
    (
        "runtime_kind",
        "Runtime Kind",
        "How the service or host is executed / virtualised.",
        [
            ("systemd_service", "Systemd Service"),
            ("docker_container", "Docker Container"),
            ("docker_compose_stack", "Docker Compose Stack"),
            ("bare_metal_host", "Bare-Metal Host"),
            ("proxmox_host", "Proxmox Host"),
            ("lxc_guest", "LXC Guest"),
            ("virtual_machine", "Virtual Machine"),
        ],
    ),
    (
        "network_segment_kind",
        "Network Segment Kind",
        "Layer-2 / overlay topology classification for a network segment.",
        [
            ("public_underlay", "Public Underlay"),
            ("private_vswitch", "Private vSwitch"),
            ("docker_bridge", "Docker Bridge"),
            ("docker_overlay", "Docker Overlay"),
            ("loopback", "Loopback"),
            ("service_bind_network", "Service Bind Network"),
            ("management_network", "Management Network"),
        ],
    ),
    (
        "address_scope",
        "Address Scope",
        "Reachability scope for an IP address assignment.",
        [
            ("public_ipv4", "Public IPv4"),
            ("public_ipv6", "Public IPv6"),
            ("private_ipv4", "Private IPv4"),
            ("loopback", "Loopback"),
            ("link_local", "Link-Local"),
            ("bridge_local", "Bridge-Local"),
        ],
    ),
    (
        "exposure_method",
        "Exposure Method",
        "How a service endpoint is made reachable.",
        [
            ("traefik_http", "Traefik HTTP"),
            ("traefik_https", "Traefik HTTPS"),
            ("traefik_tcp_sni", "Traefik TCP SNI"),
            ("direct_host_port", "Direct Host Port"),
            ("loopback_only", "Loopback Only"),
            ("private_vlan_only", "Private VLAN Only"),
            ("internal_docker_network", "Internal Docker Network"),
            ("not_exposed", "Not Exposed"),
        ],
    ),
    (
        "storage_kind",
        "Storage Kind",
        "Physical or logical classification of a storage asset.",
        [
            ("local_disk", "Local Disk"),
            ("mdraid", "MD RAID"),
            ("nvme", "NVMe"),
            ("network_storage", "Network Storage"),
            ("docker_volume", "Docker Volume"),
            ("bind_mount", "Bind Mount"),
            ("backup_target", "Backup Target"),
        ],
    ),
    (
        "document_kind",
        "Document Kind",
        "Structural / purpose classification for a canonical document.",
        [
            ("adr", "Architecture Decision Record"),
            ("cluster_overview", "Cluster Overview"),
            ("node_record", "Node Record"),
            ("hypervisor_record", "Hypervisor Record"),
            ("vm_lxc_record", "VM / LXC Record"),
            ("network_segment_record", "Network Segment Record"),
            ("storage_record", "Storage Record"),
            ("backup_restore_record", "Backup & Restore Record"),
            ("external_access_record", "External Access Record"),
            ("shared_service_dossier", "Shared Service Dossier"),
            ("service_consumption_contract", "Service Consumption Contract"),
            ("service_contract_pack", "Service Contract Pack"),
            ("runbook", "Runbook"),
            ("observability_onboarding_record", "Observability Onboarding Record"),
            ("incident_recovery_runbook", "Incident Recovery Runbook"),
            ("security_control_record", "Security Control Record"),
            ("deployment_policy_record", "Deployment Policy Record"),
            ("policy_pack", "Policy Pack"),
            ("change_template", "Change Template"),
            ("approval_pattern", "Approval Pattern"),
            ("ownership_matrix", "Ownership Matrix"),
            ("product_intent_record", "Product Intent Record"),
            ("context_boundary_record", "Context Boundary Record"),
            ("canonical_domain_model", "Canonical Domain Model"),
            ("architecture_view_pack", "Architecture View Pack"),
            ("service_contracts", "Service Contracts"),
            ("application_definition_pack", "Application Definition Pack"),
            ("engineering_policy_pack", "Engineering Policy Pack"),
        ],
    ),
    (
        "os_family",
        "OS Family",
        "Operating-system family observed on a host.",
        [
            ("ubuntu", "Ubuntu"),
            ("debian", "Debian"),
            ("macos", "macOS"),
            ("unknown", "Unknown"),
        ],
    ),
    (
        "lifecycle_status",
        "Lifecycle Status",
        "Operational lifecycle phase of an entity.",
        [
            ("planned", "Planned"),
            ("active", "Active"),
            ("degraded", "Degraded"),
            ("inactive", "Inactive"),
            ("retired", "Retired"),
            ("unknown", "Unknown"),
        ],
    ),
    (
        "observation_status",
        "Observation Status",
        "Quality / freshness classification of an observed fact.",
        [
            ("observed", "Observed"),
            ("partially_observed", "Partially Observed"),
            ("unreachable", "Unreachable"),
            ("error", "Error"),
            ("stale", "Stale"),
        ],
    ),
    (
        "discovery_source_kind",
        "Discovery Source Kind",
        "Type of automated discovery or inspection that produced a collection run.",
        [
            ("ssh_full_audit", "SSH Full Audit"),
            ("ssh_network_audit", "SSH Network Audit"),
            ("ssh_connectivity_check", "SSH Connectivity Check"),
            ("runtime_posture_audit", "Runtime Posture Audit"),
            ("trust_surface_audit", "Trust Surface Audit"),
            ("docker_runtime_inspection", "Docker Runtime Inspection"),
            ("systemd_runtime_inspection", "Systemd Runtime Inspection"),
            ("tls_endpoint_probe", "TLS Endpoint Probe"),
            ("sshd_config_inspection", "SSHD Config Inspection"),
            ("secrets_surface_inspection", "Secrets Surface Inspection"),
            ("traefik_config_inspection", "Traefik Config Inspection"),
            ("compose_manifest_inspection", "Compose Manifest Inspection"),
            ("canonical_document_parse", "Canonical Document Parse"),
            ("manual_binding", "Manual Binding"),
        ],
    ),
    (
        "evidence_kind",
        "Evidence Kind",
        "Nature / format of a collected evidence artifact.",
        [
            ("command_stdout", "Command stdout"),
            ("parsed_config_file", "Parsed Config File"),
            ("structured_json_export", "Structured JSON Export"),
            ("document_version_binding", "Document Version Binding"),
            ("route_definition", "Route Definition"),
            ("interface_snapshot", "Interface Snapshot"),
            ("container_runtime_snapshot", "Container Runtime Snapshot"),
            ("security_setting_snapshot", "Security Setting Snapshot"),
            ("runtime_posture_snapshot", "Runtime Posture Snapshot"),
            ("trust_surface_snapshot", "Trust Surface Snapshot"),
            ("tls_probe_result", "TLS Probe Result"),
            ("sshd_config_snapshot", "SSHD Config Snapshot"),
            ("secret_material_finding", "Secret Material Finding"),
        ],
    ),
    (
        "membership_role",
        "Membership Role",
        "Role a host plays within a cluster membership.",
        [
            ("operational_cluster_member", "Operational Cluster Member"),
            ("proxmox_quorum_member", "Proxmox Quorum Member"),
            ("proxmox_non_quorate_member", "Proxmox Non-Quorate Member"),
            ("standalone_hypervisor_anchor", "Standalone Hypervisor Anchor"),
            ("external_scoped_asset", "External Scoped Asset"),
        ],
    ),
    (
        "interface_kind",
        "Interface Kind",
        "Layer-2 / logical classification of a network interface.",
        [
            ("physical_nic", "Physical NIC"),
            ("bond", "Bond"),
            ("linux_bridge", "Linux Bridge"),
            ("ovs_bridge", "OVS Bridge"),
            ("docker_bridge", "Docker Bridge"),
            ("veth", "veth"),
            ("vlan_subinterface", "VLAN Subinterface"),
            ("loopback_interface", "Loopback Interface"),
            ("tunnel_interface", "Tunnel Interface"),
        ],
    ),
    (
        "owner_type",
        "Owner Type",
        "Category of entity that can hold an ownership assignment.",
        [
            ("named_individual", "Named Individual"),
            ("team", "Team"),
            ("role_group", "Role Group"),
            ("service_account", "Service Account"),
            ("external_vendor", "External Vendor"),
            ("automated_control_plane", "Automated Control Plane"),
        ],
    ),
    (
        "collection_run_status",
        "Collection Run Status",
        "Terminal or transitional state of a discovery collection run.",
        [
            ("queued", "Queued"),
            ("running", "Running"),
            ("succeeded", "Succeeded"),
            ("partial_success", "Partial Success"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
            ("timed_out", "Timed Out"),
        ],
    ),
    (
        "reconciliation_result_status",
        "Reconciliation Result Status",
        "Outcome of a canonical vs. observed fact comparison.",
        [
            ("matched", "Matched"),
            ("drift_detected", "Drift Detected"),
            ("missing_canonical", "Missing Canonical"),
            ("missing_observed", "Missing Observed"),
            ("requires_review", "Requires Review"),
            ("approved_override", "Approved Override"),
            ("suppressed", "Suppressed"),
        ],
    ),
    (
        "exposure_health",
        "Exposure Health",
        "Last known health state of a service exposure endpoint.",
        [
            ("healthy", "Healthy"),
            ("degraded", "Degraded"),
            ("connection_refused", "Connection Refused"),
            ("timeout", "Timeout"),
            ("dns_error", "DNS Error"),
            ("tls_handshake_failed", "TLS Handshake Failed"),
            ("design_only", "Design Only"),
            ("unknown", "Unknown"),
        ],
    ),
    (
        "relationship_kind",
        "Relationship Kind",
        "Directed verb that describes how one entity relates to another.",
        [
            ("contains", "Contains"),
            ("hosts", "Hosts"),
            ("member_of", "Member Of"),
            ("runs_on", "Runs On"),
            ("depends_on", "Depends On"),
            ("exposes", "Exposes"),
            ("uses_network", "Uses Network"),
            ("uses_storage", "Uses Storage"),
            ("owned_by", "Owned By"),
            ("documented_by", "Documented By"),
            ("observed_by", "Observed By"),
            ("backed_up_by", "Backed Up By"),
            ("protected_by", "Protected By"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Seeding logic
# ---------------------------------------------------------------------------


def _build_url() -> str:
    load_dotenv()
    host = os.environ["POSTGRES_HOST"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def seed(connection: sa.engine.Connection) -> None:
    """Insert all domains and terms using ON CONFLICT DO NOTHING (idempotent)."""
    domain_table = sa.table(
        "taxonomy_domain",
        sa.column("taxonomy_domain_id"),
        sa.column("domain_code"),
        sa.column("name"),
        sa.column("description"),
        schema="taxonomy",
    )
    term_table = sa.table(
        "taxonomy_term",
        sa.column("taxonomy_term_id"),
        sa.column("taxonomy_domain_id"),
        sa.column("term_code"),
        sa.column("display_name"),
        sa.column("sort_order"),
        schema="taxonomy",
    )

    # Cache domain_id by code so terms can reference them without a round-trip
    domain_id_by_code: dict[str, uuid.UUID] = {}

    for _, (domain_code, name, description, terms) in enumerate(_CATALOGUE):
        domain_id = uuid.uuid4()
        connection.execute(
            pg_insert(domain_table)
            .values(
                taxonomy_domain_id=domain_id,
                domain_code=domain_code,
                name=name,
                description=description,
            )
            .on_conflict_do_nothing(index_elements=["domain_code"])
        )
        # Retrieve actual ID in case the row already existed
        row: Any = connection.execute(
            sa.select(domain_table.c.taxonomy_domain_id).where(
                domain_table.c.domain_code == domain_code
            )
        ).fetchone()
        domain_id_by_code[domain_code] = row[0]

        for sort_t, (term_code, display_name) in enumerate(terms):
            connection.execute(
                pg_insert(term_table)
                .values(
                    taxonomy_term_id=uuid.uuid4(),
                    taxonomy_domain_id=domain_id_by_code[domain_code],
                    term_code=term_code,
                    display_name=display_name,
                    sort_order=sort_t,
                )
                .on_conflict_do_nothing(
                    # ON CONFLICT on (taxonomy_domain_id, term_code)
                    # The constraint name is uq_term_code_per_domain
                    constraint="uq_term_code_per_domain"
                )
            )

    connection.commit()
    print(f"OK: {len(_CATALOGUE)} taxonomy domains seeded.")


def main() -> None:
    engine = sa.create_engine(_build_url())
    with engine.connect() as conn:
        seed(conn)
    engine.dispose()


if __name__ == "__main__":
    main()
