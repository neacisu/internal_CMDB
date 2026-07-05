"""
Sync script: hosturi rămase fără registry.host record.

Hosturi cu agent activ dar fără înregistrare:
  - orchestrator        (77.42.76.185, Debian 13, control plane)
  - lxc-postgres-main  (10.0.1.107, Ubuntu 24.04, LXC 107 pe hz.247)
  - lxc-ci-worker      (10.0.1.108, Ubuntu 24.04, LXC 108 pe hz.223)
  - lxc-neanelu-prod   (10.0.1.111, Ubuntu 24.04, LXC 111 pe hz.215)
  - lxc-neanelu-staging(10.0.1.112, Ubuntu 24.04, LXC 112 pe hz.215)
  - lxc-prod-cerniq    (10.0.1.109, Ubuntu 24.04, LXC 109 pe hz.223)
  - lxc-staging-cerniq (10.0.1.110, Ubuntu 24.04, LXC 110 pe hz.223)

Rulare:
    cd /opt/stacks/internalcmdb
    source .venv/bin/activate
    python scripts/sync_remaining_hosts.py
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from dotenv import load_dotenv

load_dotenv("/opt/stacks/internalcmdb/.env")

# ── Constants — prevent literal duplication (Sonar S1192) ─────────────────────
OS_UBUNTU_24_04 = "Ubuntu 24.04 LTS"
PARENT_HZ215 = "hz.215"
PARENT_HZ223 = "hz.223"
PARENT_HZ247 = "hz.247"

_host = os.environ.get("POSTGRES_SYNC_HOST", "127.0.0.1")
_port = os.environ.get("POSTGRES_SYNC_PORT", "5433")
_url = (
    f"postgresql+psycopg://{os.environ['POSTGRES_USER']}"
    f":{os.environ['POSTGRES_PASSWORD']}"
    f"@{_host}:{_port}"
    f"/{os.environ['POSTGRES_DB']}"
)
engine = sa.create_engine(_url, pool_pre_ping=True)
NOW = datetime.now(timezone.utc)

# ── Host definitions ───────────────────────────────────────────────────────────
REMAINING_HOSTS: list[dict[str, Any]] = [
    {
        "host_code": "orchestrator",
        "hostname": "orchestrator.neanelu.ro",
        "ssh_alias": "orchestrator",
        "fqdn": "orchestrator.neanelu.ro",
        "os_version_text": "Debian GNU/Linux 13 (trixie)",
        "os_family": "debian",
        "architecture_text": "x86_64",
        "is_docker_host": True,
        "is_hypervisor": True,
        "primary_public_ipv4": "77.42.76.185",
        "primary_private_ipv4": "10.0.0.2",
        "environment": "shared-platform",
        "description": "Control plane node: Traefik, Prometheus, CMDB API, OpenBao, Zitadel, Stalwart, Docker host, Proxmox cluster member",
        "metadata": {
            "roles": ["control_plane", "proxy", "observability", "security", "mail"],
            "proxmox_cluster": "NewCluster",
            "proxmox_node_id": 1,
            "docker_containers": 21,
        },
    },
    {
        "host_code": "lxc-postgres-main",
        "hostname": "postgres-main",
        "ssh_alias": "lxc-postgres-main",
        "fqdn": "postgres-main.internal",
        "os_version_text": OS_UBUNTU_24_04,
        "os_family": "ubuntu",
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "is_hypervisor": False,
        "primary_public_ipv4": None,
        "primary_private_ipv4": "10.0.1.107",
        "environment": "production",
        "description": "Primary PostgreSQL 18.2 host — LXC 107 on hz.247. All production app databases.",
        "metadata": {
            "lxc_id": 107,
            "parent_host": PARENT_HZ247,
            "postgres_version": "18.2",
            "systemd_services": ["postgresql@18-main.service", "postgres-exporter.service"],
        },
    },
    {
        "host_code": "lxc-ci-worker",
        "hostname": "CI-worker",
        "ssh_alias": "lxc-ci-worker",
        "fqdn": "ci-worker.internal",
        "os_version_text": OS_UBUNTU_24_04,
        "os_family": "ubuntu",
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "is_hypervisor": False,
        "primary_public_ipv4": None,
        "primary_private_ipv4": "10.0.1.108",
        "environment": "development",
        "description": "CI/CD build worker — LXC 108 on hz.223",
        "metadata": {
            "lxc_id": 108,
            "parent_host": PARENT_HZ223,
        },
    },
    {
        "host_code": "lxc-neanelu-prod",
        "hostname": "neanelu-prod",
        "ssh_alias": "lxc-neanelu-prod",
        "fqdn": "neanelu.ro",
        "os_version_text": OS_UBUNTU_24_04,
        "os_family": "ubuntu",
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "is_hypervisor": False,
        "primary_public_ipv4": None,
        "primary_private_ipv4": "10.0.1.111",
        "environment": "production",
        "description": "Production web app for neanelu.ro — LXC 111 on hz.215",
        "metadata": {
            "lxc_id": 111,
            "parent_host": PARENT_HZ215,
        },
    },
    {
        "host_code": "lxc-neanelu-staging",
        "hostname": "neanelu-staging",
        "ssh_alias": "lxc-neanelu-staging",
        "fqdn": "staging.neanelu.ro",
        "os_version_text": OS_UBUNTU_24_04,
        "os_family": "ubuntu",
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "is_hypervisor": False,
        "primary_public_ipv4": None,
        "primary_private_ipv4": "10.0.1.112",
        "environment": "staging",
        "description": "Staging web app for neanelu.ro — LXC 112 on hz.215",
        "metadata": {
            "lxc_id": 112,
            "parent_host": PARENT_HZ215,
        },
    },
    {
        "host_code": "lxc-prod-cerniq",
        "hostname": "prod-cerniq",
        "ssh_alias": "lxc-prod-cerniq",
        "fqdn": "cerniq.ro",
        "os_version_text": OS_UBUNTU_24_04,
        "os_family": "ubuntu",
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "is_hypervisor": False,
        "primary_public_ipv4": None,
        "primary_private_ipv4": "10.0.1.109",
        "environment": "production",
        "description": "Production Cerniq application — LXC 109 on hz.223",
        "metadata": {
            "lxc_id": 109,
            "parent_host": PARENT_HZ223,
        },
    },
    {
        "host_code": "lxc-staging-cerniq",
        "hostname": "staging-cerniq",
        "ssh_alias": "lxc-staging-cerniq",
        "fqdn": "staging.cerniq.ro",
        "os_version_text": OS_UBUNTU_24_04,
        "os_family": "ubuntu",
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "is_hypervisor": False,
        "primary_public_ipv4": None,
        "primary_private_ipv4": "10.0.1.110",
        "environment": "staging",
        "description": "Staging Cerniq application — LXC 110 on hz.223",
        "metadata": {
            "lxc_id": 110,
            "parent_host": PARENT_HZ223,
        },
    },
]


def get_taxonomy_terms(conn: sa.Connection) -> dict[tuple[str, str], uuid.UUID]:
    rows = conn.execute(
        sa.text(
            "SELECT d.domain_code, t.term_code, t.taxonomy_term_id "
            "FROM taxonomy.taxonomy_term t "
            "JOIN taxonomy.taxonomy_domain d ON d.taxonomy_domain_id = t.taxonomy_domain_id"
        )
    ).fetchall()
    return {(row[0], row[1]): row[2] for row in rows}


def upsert_host(
    conn: sa.Connection,
    h: dict[str, Any],
    terms: dict[tuple[str, str], uuid.UUID],
    existing_codes: set[str],
) -> uuid.UUID | None:
    env_code = h.get("environment", "production")
    entity_kind_id = terms.get(("entity_kind", "host"))
    environment_id = terms.get(("environment", env_code)) or terms.get(("environment", "production"))
    lifecycle_id = terms.get(("lifecycle_status", "active"))
    os_family_id = terms.get(("os_family", h.get("os_family", "ubuntu")))

    if not entity_kind_id or not environment_id or not lifecycle_id:
        print(f"  ERROR: missing taxonomy terms for {h['host_code']}")
        return None

    meta_str = json.dumps({**h.get("metadata", {}), "description": h["description"], "synced_at": NOW.isoformat()})
    code = h["host_code"]
    action = "UPDATE" if code in existing_codes else "INSERT"

    if action == "INSERT":
        new_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO registry.host "
                "(host_id, host_code, hostname, ssh_alias, fqdn, "
                "entity_kind_term_id, environment_term_id, lifecycle_term_id, os_family_term_id, "
                "os_version_text, architecture_text, is_docker_host, is_hypervisor, "
                "primary_public_ipv4, primary_private_ipv4, "
                "observed_hostname, confidence_score, metadata_jsonb, "
                "created_at, updated_at) "
                "VALUES "
                "(:id, :code, :hostname, :ssh_alias, :fqdn, "
                ":ek, :env, :lc, :os_fam, "
                ":os_ver, :arch, :docker, :hyp, "
                ":pub_ip, :priv_ip, "
                ":obs_hostname, :conf, CAST(:meta AS jsonb), "
                "now(), now())"
            ),
            {
                "id": new_id, "code": code, "hostname": h["hostname"],
                "ssh_alias": h["ssh_alias"], "fqdn": h["fqdn"],
                "ek": entity_kind_id, "env": environment_id, "lc": lifecycle_id, "os_fam": os_family_id,
                "os_ver": h["os_version_text"], "arch": h["architecture_text"],
                "docker": h["is_docker_host"], "hyp": h["is_hypervisor"],
                "pub_ip": h["primary_public_ipv4"], "priv_ip": h["primary_private_ipv4"],
                "obs_hostname": h["hostname"], "conf": 0.98, "meta": meta_str,
            },
        )
        print(f"  ✓ INSERT  {code}")
        return new_id
    else:
        row = conn.execute(
            sa.text("SELECT host_id FROM registry.host WHERE host_code = :c"), {"c": code}
        ).fetchone()
        assert row is not None, f"host_code '{code}' not found after existing_codes check"
        existing_id: uuid.UUID = row[0]
        conn.execute(
            sa.text(
                "UPDATE registry.host SET "
                "hostname=:hostname, ssh_alias=:ssh_alias, fqdn=:fqdn, "
                "os_version_text=:os_ver, architecture_text=:arch, "
                "is_docker_host=:docker, is_hypervisor=:hyp, "
                "primary_public_ipv4=:pub_ip, primary_private_ipv4=:priv_ip, "
                "observed_hostname=:obs_hostname, confidence_score=:conf, "
                "metadata_jsonb=CAST(:meta AS jsonb), updated_at=now() "
                "WHERE host_code=:code"
            ),
            {
                "hostname": h["hostname"], "ssh_alias": h["ssh_alias"], "fqdn": h["fqdn"],
                "os_ver": h["os_version_text"], "arch": h["architecture_text"],
                "docker": h["is_docker_host"], "hyp": h["is_hypervisor"],
                "pub_ip": h["primary_public_ipv4"], "priv_ip": h["primary_private_ipv4"],
                "obs_hostname": h["hostname"], "conf": 0.98, "meta": meta_str, "code": code,
            },
        )
        print(f"  ✓ UPDATE  {code}")
        return existing_id


def link_all_unlinked(conn: sa.Connection) -> None:
    unlinked = conn.execute(
        sa.text(
            "SELECT ca.agent_id, ca.host_code FROM discovery.collector_agent ca "
            "WHERE ca.host_id IS NULL"
        )
    ).fetchall()
    linked_count = 0
    for agent_id, host_code in unlinked:
        row = conn.execute(
            sa.text("SELECT host_id FROM registry.host WHERE host_code = :c"), {"c": host_code}
        ).fetchone()
        if row:
            conn.execute(
                sa.text("UPDATE discovery.collector_agent SET host_id=:hid WHERE agent_id=:aid"),
                {"hid": row[0], "aid": agent_id},
            )
            print(f"  ✓ LINKED  {host_code}")
            linked_count += 1
        else:
            print(f"  — SKIP    {host_code}  (no host record)")
    print(f"\n  Linked: {linked_count}/{len(unlinked)}")


def main() -> None:
    print(f"\ninternalCMDB sync — remaining hosts — {NOW.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    with engine.begin() as conn:
        terms = get_taxonomy_terms(conn)
        existing = {r[0] for r in conn.execute(sa.text("SELECT host_code FROM registry.host")).fetchall()}

        print("\n=== UPSERT: hosturi rămase ===")
        for h in REMAINING_HOSTS:
            upsert_host(conn, h, terms, existing)

        print("\n=== LINK: toți agenții nelinkat ===")
        link_all_unlinked(conn)

        # Final counts
        total = conn.execute(sa.text("SELECT count(*) FROM registry.host")).scalar()
        linked = conn.execute(
            sa.text("SELECT count(*) FROM discovery.collector_agent WHERE host_id IS NOT NULL")
        ).scalar()
        total_agents = conn.execute(sa.text("SELECT count(*) FROM discovery.collector_agent")).scalar()
        print(f"\n  Hosturi totale: {total}")
        print(f"  Agenți linkat / total: {linked} / {total_agents}")

    print("\n✓ Sync complet.\n")


if __name__ == "__main__":
    main()
