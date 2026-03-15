"""Registry of all available worker scripts with metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent.parent  # repo root


@dataclass(frozen=True)
class ScriptDef:
    task_name: str
    display_name: str
    description: str
    category: str  # discovery | security | etl | maintenance | governance
    script_path: str  # relative to repo root
    default_args: list[str] = field(default_factory=list)
    is_destructive: bool = False


SCRIPTS: dict[str, ScriptDef] = {
    s.task_name: s
    for s in [
        ScriptDef(
            task_name="ssh_connectivity_check",
            display_name="SSH Connectivity Check",
            description=(
                "Tests SSH connectivity to all 12+ cluster hosts and outputs a JSON summary."
            ),
            category="discovery",
            script_path="subprojects/cluster-ssh-checker/test_cluster_ssh.py",
        ),
        ScriptDef(
            task_name="cluster_network_audit",
            display_name="Cluster Network Audit",
            description="Audits vSwitch/VLAN/IP network topology across all nodes via SSH.",
            category="discovery",
            script_path="subprojects/cluster-audit/audit_cluster.py",
        ),
        ScriptDef(
            task_name="full_cluster_audit",
            display_name="Full Cluster Audit",
            description=(
                "10-section audit per host: system, hardware, GPU, disk, network, "
                "Docker, services, firewall, security, processes."
            ),
            category="discovery",
            script_path="subprojects/cluster-full-audit/audit_full.py",
        ),
        ScriptDef(
            task_name="runtime_posture_audit",
            display_name="Runtime Posture Audit",
            description=(
                "Audits Docker containers, backup/HA indicators, and AI runtime across hosts."
            ),
            category="discovery",
            script_path="subprojects/runtime-posture-audit/audit_runtime_posture.py",
        ),
        ScriptDef(
            task_name="trust_surface_audit",
            display_name="Trust Surface Audit",
            description=(
                "Audits SSHD config, SSH keys, secret paths, and TLS certificates across hosts."
            ),
            category="security",
            script_path="subprojects/trust-surface-audit/audit_trust_surface.py",
        ),
        ScriptDef(
            task_name="key_mesh_verify",
            display_name="Key Mesh Verify",
            description="Verifies full-mesh SSH key distribution across all cluster nodes.",
            category="security",
            script_path="subprojects/cluster-key-mesh/mesh_keys.py",
            default_args=["--verify"],
        ),
        ScriptDef(
            task_name="load_ssh_audit",
            display_name="Load SSH Audit → DB",
            description=(
                "Parses full_cluster_audit/current.json and upserts hosts,"
                " hardware, GPUs into PostgreSQL."
            ),
            category="etl",
            script_path="src/internalcmdb/loaders/ssh_audit_loader.py",
        ),
        ScriptDef(
            task_name="load_runtime_posture",
            display_name="Load Runtime Posture → DB",
            description=(
                "Parses runtime_posture/current.json and upserts containers,"
                " services, observed facts."
            ),
            category="etl",
            script_path="src/internalcmdb/loaders/runtime_posture_loader.py",
        ),
        ScriptDef(
            task_name="load_trust_surface",
            display_name="Load Trust Surface → DB",
            description=(
                "Parses trust_surface/current.json and upserts TLS/SSH data and evidence artifacts."
            ),
            category="etl",
            script_path="src/internalcmdb/loaders/trust_surface_loader.py",
        ),
        ScriptDef(
            task_name="taxonomy_seed",
            display_name="Taxonomy Seed",
            description=(
                "Idempotent upsert of all 22 taxonomy domains and 200+ terms into PostgreSQL."
            ),
            category="maintenance",
            script_path="src/internalcmdb/seeds/taxonomy_seed.py",
        ),
        ScriptDef(
            task_name="document_validation",
            display_name="Document Validation",
            description=(
                "Validates YAML frontmatter across all docs/ markdown files"
                " against metadata-schema.md."
            ),
            category="governance",
            script_path="src/internalcmdb/governance/metadata_validator.py",
            default_args=["docs/"],
        ),
        ScriptDef(
            task_name="staleness_check",
            display_name="Agent Staleness Check",
            description=(
                "Checks all collector agents for heartbeat staleness"
                " and updates status to degraded/offline."
            ),
            category="maintenance",
            script_path="src/internalcmdb/collectors/staleness.py",
        ),
        ScriptDef(
            task_name="deploy_agent",
            display_name="Deploy Collector Agent",
            description=("Deploys the collector agent daemon to a remote host via SSH + systemd."),
            category="maintenance",
            script_path="scripts/deploy_agent.sh",
        ),
    ]
}
