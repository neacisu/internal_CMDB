"""
Sync script: hz.118 LXC containers → internalCMDB registry.

Scopuri:
  1. Audit: afișează starea curentă a DB (hosturi, agenți, servicii)
  2. Upsert hosts: inserează / actualizează LXC 100-103 în registry.host
  3. Link agenți: leagă discovery.collector_agent.host_id la registry.host
  4. Upsert IP assignments: registry.ip_address_assignment
  5. Upsert network interfaces: registry.network_interface
  6. Raport final

Rulare:
    cd /opt/stacks/internalcmdb
    source .venv/bin/activate
    python scripts/sync_hz118_lxc.py
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from dotenv import load_dotenv

load_dotenv("/opt/stacks/internalcmdb/.env")

# ── DB connection ──────────────────────────────────────────────────────────────
_host = os.environ.get("POSTGRES_SYNC_HOST", os.environ.get("POSTGRES_HOST", "127.0.0.1"))
_port = os.environ.get("POSTGRES_SYNC_PORT", os.environ.get("POSTGRES_PORT", "5433"))
_url = (
    f"postgresql+psycopg://{os.environ['POSTGRES_USER']}"
    f":{os.environ['POSTGRES_PASSWORD']}"
    f"@{_host}:{_port}"
    f"/{os.environ['POSTGRES_DB']}"
)
engine = sa.create_engine(_url, pool_pre_ping=True)

# ── Known data / constants ────────────────────────────────────────────────────
# Proxmox hypervisor host — parent of all LXCs
HZ118_HOST_CODE = "hz.118"

# OS version strings shared across multiple LXC definitions
OS_UBUNTU_2004_LTS = "Ubuntu 20.04.6 LTS"
OS_UBUNTU_2204_LTS = "Ubuntu 22.04.3 LTS"

# Python build identifiers shared across LXCs 101-103
PYTHON_DEADSNAKES_JAMMY = "3.14.4 (deadsnakes/jammy)"

LXC_HOSTS = [
    {
        "host_code": "lxc-hz118-traktors",
        "hostname": "server",
        "ssh_alias": "hz.118.lxc.100",
        "fqdn": "server.traktors.ro",
        "os_version_text": OS_UBUNTU_2004_LTS,
        "kernel_version_text": None,
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "primary_public_ipv4": "95.216.72.100",
        "primary_private_ipv4": None,
        "ssh_port": 1321,
        "description": "Production server for traktors.ro — LXC 100 on hz.118",
        "lxc_id": 100,
        "python_version": "3.14.4 (compiled from source)",
    },
    {
        "host_code": "lxc-hz118-tecdocnode",
        "hostname": "tecdocnode",
        "ssh_alias": "hz.118.lxc.101",
        "fqdn": "tecdocnode.internal",
        "os_version_text": OS_UBUNTU_2204_LTS,
        "kernel_version_text": None,
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "primary_public_ipv4": "95.216.125.170",
        "primary_private_ipv4": None,
        "ssh_port": 22,
        "description": "TecDoc Node.js service — LXC 101 on hz.118",
        "lxc_id": 101,
        "python_version": PYTHON_DEADSNAKES_JAMMY,
    },
    {
        "host_code": "lxc-hz118-tecdocmysql",
        "hostname": "tecdocmysql",
        "ssh_alias": "hz.118.lxc.102",
        "fqdn": "tecdocmysql.internal",
        "os_version_text": OS_UBUNTU_2204_LTS,
        "kernel_version_text": None,
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "primary_public_ipv4": "95.216.125.171",
        "primary_private_ipv4": None,
        "ssh_port": 22,
        "description": "TecDoc MySQL database — LXC 102 on hz.118",
        "lxc_id": 102,
        "python_version": PYTHON_DEADSNAKES_JAMMY,
    },
    {
        "host_code": "lxc-hz118-mediserver2",
        "hostname": "mediserver2",
        "ssh_alias": "hz.118.lxc.103",
        "fqdn": "mediserver2.internal",
        "os_version_text": OS_UBUNTU_2204_LTS,
        "kernel_version_text": None,
        "architecture_text": "x86_64",
        "is_docker_host": False,
        "primary_public_ipv4": "95.216.125.172",
        "primary_private_ipv4": None,
        "ssh_port": 22,
        "description": "Media server 2 — LXC 103 on hz.118",
        "lxc_id": 103,
        "python_version": PYTHON_DEADSNAKES_JAMMY,
    },
]

NOW = datetime.now(timezone.utc)


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def get_taxonomy_terms(conn: sa.Connection) -> dict[tuple[str, str], uuid.UUID]:
    """Fetch all taxonomy terms keyed by (domain_code, term_code)."""
    rows = conn.execute(
        sa.text(
            "SELECT d.domain_code, t.term_code, t.taxonomy_term_id "
            "FROM taxonomy.taxonomy_term t "
            "JOIN taxonomy.taxonomy_domain d ON d.taxonomy_domain_id = t.taxonomy_domain_id "
            "ORDER BY d.domain_code, t.term_code"
        )
    ).fetchall()
    return {(row[0], row[1]): row[2] for row in rows}


def _audit_hosts(conn: sa.Connection) -> tuple[set[str], dict[str, uuid.UUID]]:
    """Query and print all registered hosts. Returns (existing_codes, host_id_map)."""
    section("AUDIT: hosturi curente în registry.host")
    hosts = conn.execute(
        sa.text(
            "SELECT host_code, hostname, primary_public_ipv4, primary_private_ipv4, "
            "os_version_text, is_docker_host, is_hypervisor, cluster_id "
            "FROM registry.host ORDER BY host_code"
        )
    ).fetchall()
    print(f"  Total hosturi: {len(hosts)}")
    for h in hosts:
        # S3358: extract nested conditional to independent variable
        if h[6]:
            entity_type = "hypervisor"
        elif h[5]:
            entity_type = "docker"
        else:
            entity_type = "host"
        print(
            f"  {h[0]:35s}  ip={str(h[2] or '—'):18s}  "
            f"{entity_type:10s}  {h[4] or '—'}"
        )
    existing_codes = {h[0] for h in hosts}
    id_rows = conn.execute(sa.text("SELECT host_code, host_id FROM registry.host")).fetchall()
    host_id_map: dict[str, uuid.UUID] = {r[0]: r[1] for r in id_rows}
    return existing_codes, host_id_map


def _audit_agents(conn: sa.Connection) -> list:
    """Query and print all collector agents. Returns agent rows."""
    section("AUDIT: agenți colectori activi")
    agents = conn.execute(
        sa.text(
            "SELECT host_code, agent_id, status, last_heartbeat_at, host_id "
            "FROM discovery.collector_agent ORDER BY host_code"
        )
    ).fetchall()
    print(f"  Total agenți: {len(agents)}")
    for a in agents:
        linked = "linked" if a[4] else "UNLINKED"
        hb = str(a[3])[:16] if a[3] else "never"
        print(f"  {a[0]:35s}  {a[2]:8s}  hb={hb}  [{linked}]")
    return agents


def _audit_services(conn: sa.Connection) -> None:
    """Query and print all shared services."""
    section("AUDIT: servicii shared")
    services = conn.execute(
        sa.text(
            "SELECT service_code, name, "
            "metadata_jsonb->>'category' as category "
            "FROM registry.shared_service ORDER BY service_code"
        )
    ).fetchall()
    print(f"  Total servicii: {len(services)}")
    for s in services:
        print(f"  {s[0]:40s}  cat={s[2] or '—':20s}  {s[1]}")


def _audit_taxonomy(conn: sa.Connection) -> None:
    """Query and print a summary of taxonomy terms grouped by domain."""
    section("AUDIT: taxonomy terms disponibile")
    terms_rows = conn.execute(
        sa.text(
            "SELECT d.domain_code, t.term_code, t.display_name "
            "FROM taxonomy.taxonomy_term t "
            "JOIN taxonomy.taxonomy_domain d ON d.taxonomy_domain_id = t.taxonomy_domain_id "
            "ORDER BY d.domain_code, t.term_code"
        )
    ).fetchall()
    print(f"  Total termeni: {len(terms_rows)}")
    by_domain: dict[str, list[str]] = {}
    for t in terms_rows:
        by_domain.setdefault(t[0], []).append(t[1])
    for domain, items in sorted(by_domain.items()):
        print(f"  [{domain}]: {', '.join(items)}")


def audit_current_state(conn: sa.Connection) -> dict:
    """Show current DB state and return summary dict for use by follow-on steps."""
    existing_codes, host_id_map = _audit_hosts(conn)
    agents = _audit_agents(conn)
    _audit_services(conn)
    _audit_taxonomy(conn)
    return {"existing_host_codes": existing_codes, "agents": agents, "host_id_map": host_id_map}


# ── upsert helpers ─────────────────────────────────────────────────────────────

def _resolve_upsert_terms(
    terms: dict[tuple[str, str], uuid.UUID],
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID | None] | None:
    """Resolve the four taxonomy term IDs required for host upsert.

    Returns (entity_kind_id, environment_id, lifecycle_id, os_family_id) or None
    when a required term cannot be found (caller should abort the upsert).
    """
    entity_kind_id = (
        terms.get(("entity_kind", "host"))
        or terms.get(("entity_kind", "lxc_guest"))
    )
    if not entity_kind_id:
        ek_terms = {k: v for k, v in terms.items() if k[0] == "entity_kind"}
        print(f"  WARN: no 'host' entity_kind term. Available: {list(ek_terms.keys())}")
        entity_kind_id = next(iter(ek_terms.values())) if ek_terms else None

    environment_id = (
        terms.get(("environment", "production"))
        or terms.get(("environment", "prod"))
    )
    if not environment_id:
        env_terms = {k: v for k, v in terms.items() if k[0] == "environment"}
        print(f"  WARN: no 'production' env term. Available: {list(env_terms.keys())}")
        environment_id = next(iter(env_terms.values())) if env_terms else None

    lifecycle_id = (
        terms.get(("lifecycle_status", "active"))
        or terms.get(("lifecycle", "active"))
    )
    if not lifecycle_id:
        lc_terms = {k: v for k, v in terms.items() if "lifecycle" in k[0]}
        print(f"  WARN: no 'active' lifecycle term. Available: {list(lc_terms.keys())}")
        lifecycle_id = next(iter(lc_terms.values())) if lc_terms else None

    if not entity_kind_id or not environment_id or not lifecycle_id:
        print("  ERROR: missing required taxonomy terms — cannot upsert hosts")
        print(f"    entity_kind_id = {entity_kind_id}")
        print(f"    environment_id = {environment_id}")
        print(f"    lifecycle_id   = {lifecycle_id}")
        return None

    os_family_id = terms.get(("os_family", "ubuntu")) or terms.get(("os_family", "linux"))
    return entity_kind_id, environment_id, lifecycle_id, os_family_id


def _build_lxc_meta(lxc: dict, enrolled_at: datetime) -> str:
    """Serialise the metadata JSONB dict for an LXC host record."""
    import json  # noqa: PLC0415 — local import keeps module top clean

    return json.dumps(
        {
            "lxc_id": lxc["lxc_id"],
            "parent_host": HZ118_HOST_CODE,
            "ssh_port": lxc["ssh_port"],
            "python_version": lxc["python_version"],
            "description": lxc["description"],
            "proxmox_standalone": True,
            "agent_enrolled": True,
            "agent_enrolled_at": enrolled_at.isoformat(),
        }
    )


def _exec_insert_host(
    conn: sa.Connection,
    lxc: dict,
    term_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID | None],
    meta_str: str,
) -> uuid.UUID:
    """Execute a single INSERT into registry.host and return the new host_id."""
    entity_kind_id, environment_id, lifecycle_id, os_family_id = term_ids
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
            "id": new_id,
            "code": lxc["host_code"],
            "hostname": lxc["hostname"],
            "ssh_alias": lxc["ssh_alias"],
            "fqdn": lxc["fqdn"],
            "ek": entity_kind_id,
            "env": environment_id,
            "lc": lifecycle_id,
            "os_fam": os_family_id,
            "os_ver": lxc["os_version_text"],
            "arch": lxc["architecture_text"],
            "docker": lxc["is_docker_host"],
            "hyp": False,
            "pub_ip": lxc["primary_public_ipv4"],
            "priv_ip": lxc["primary_private_ipv4"],
            "obs_hostname": lxc["hostname"],
            "conf": 0.98,
            "meta": meta_str,
        },
    )
    return new_id


def _exec_update_host(
    conn: sa.Connection,
    lxc: dict,
    meta_str: str,
) -> uuid.UUID:
    """Execute an UPDATE for an existing registry.host row and return its host_id."""
    row = conn.execute(
        sa.text("SELECT host_id FROM registry.host WHERE host_code = :c"),
        {"c": lxc["host_code"]},
    ).fetchone()
    existing_id: uuid.UUID = row[0]
    conn.execute(
        sa.text(
            "UPDATE registry.host SET "
            "hostname=:hostname, ssh_alias=:ssh_alias, fqdn=:fqdn, "
            "os_version_text=:os_ver, architecture_text=:arch, "
            "primary_public_ipv4=:pub_ip, "
            "observed_hostname=:obs_hostname, confidence_score=:conf, "
            "metadata_jsonb=CAST(:meta AS jsonb), updated_at=now() "
            "WHERE host_code=:code"
        ),
        {
            "hostname": lxc["hostname"],
            "ssh_alias": lxc["ssh_alias"],
            "fqdn": lxc["fqdn"],
            "os_ver": lxc["os_version_text"],
            "arch": lxc["architecture_text"],
            "pub_ip": lxc["primary_public_ipv4"],
            "obs_hostname": lxc["hostname"],
            "conf": 0.98,
            "meta": meta_str,
            "code": lxc["host_code"],
        },
    )
    return existing_id


def upsert_hosts(conn: sa.Connection, terms: dict, existing_codes: set) -> dict[str, uuid.UUID]:
    """Upsert all 4 LXC hosts. Returns map host_code → host_id."""
    section("UPSERT: hosturi LXC hz.118")

    term_ids = _resolve_upsert_terms(terms)
    if term_ids is None:
        return {}

    inserted: dict[str, uuid.UUID] = {}
    for lxc in LXC_HOSTS:
        code = lxc["host_code"]
        meta_str = _build_lxc_meta(lxc, NOW)
        if code not in existing_codes:
            new_id = _exec_insert_host(conn, lxc, term_ids, meta_str)
            inserted[code] = new_id
            print(f"  ✓ INSERT  {code}  ({lxc['primary_public_ipv4']})")
        else:
            existing_id = _exec_update_host(conn, lxc, meta_str)
            inserted[code] = existing_id
            print(f"  ✓ UPDATE  {code}  ({lxc['primary_public_ipv4']})")

    return inserted


def link_agents(conn: sa.Connection, host_map: dict[str, uuid.UUID]) -> None:
    """Link collector_agent.host_id to registry.host for each LXC."""
    section("LINK: agenți → registry.host")
    for lxc in LXC_HOSTS:
        code = lxc["host_code"]
        host_id = host_map.get(code)
        if not host_id:
            print(f"  SKIP  {code} — no host_id")
            continue

        agents = conn.execute(
            sa.text(
                "SELECT agent_id, host_id, status, last_heartbeat_at "
                "FROM discovery.collector_agent WHERE host_code = :c ORDER BY enrolled_at DESC"
            ),
            {"c": code},
        ).fetchall()

        if not agents:
            print(f"  WARN  {code} — no agent in DB yet (may still be enrolling)")
            continue

        for agent in agents:
            agent_id, current_host_id, status, hb = agent
            if current_host_id != host_id:
                conn.execute(
                    sa.text(
                        "UPDATE discovery.collector_agent SET host_id=:hid WHERE agent_id=:aid"
                    ),
                    {"hid": host_id, "aid": agent_id},
                )
                print(f"  ✓ LINKED  {code}  agent={agent_id}  status={status}  hb={str(hb)[:16]}")
            else:
                print(f"  ✓ OK      {code}  agent={agent_id}  status={status}  hb={str(hb)[:16]}")


def link_all_unlinked_agents(conn: sa.Connection) -> None:
    """Link all other unlinked agents that have a matching host record."""
    section("LINK: toți agenții nelinkat cu host existent")
    unlinked = conn.execute(
        sa.text(
            "SELECT ca.agent_id, ca.host_code, ca.status "
            "FROM discovery.collector_agent ca "
            "WHERE ca.host_id IS NULL AND ca.is_active = true"
        )
    ).fetchall()
    print(f"  Agenți nelinkat activi: {len(unlinked)}")
    for agent_id, host_code, status in unlinked:
        host_row = conn.execute(
            sa.text("SELECT host_id FROM registry.host WHERE host_code = :c"),
            {"c": host_code},
        ).fetchone()
        if host_row:
            conn.execute(
                sa.text(
                    "UPDATE discovery.collector_agent SET host_id=:hid WHERE agent_id=:aid"
                ),
                {"hid": host_row[0], "aid": agent_id},
            )
            print(f"  ✓ LINKED  {host_code}  agent={agent_id}  status={status}")
        else:
            print(f"  — SKIP    {host_code}  — no host record in registry")


def final_report(conn: sa.Connection) -> None:
    section("RAPORT FINAL")
    hosts = conn.execute(
        sa.text(
            "SELECT h.host_code, h.hostname, h.primary_public_ipv4, h.os_version_text, "
            "ca.status as agent_status, ca.last_heartbeat_at "
            "FROM registry.host h "
            "LEFT JOIN discovery.collector_agent ca ON ca.host_id = h.host_id "
            "  AND ca.is_active = true "
            "WHERE h.host_code LIKE 'lxc-hz118-%' "
            "ORDER BY h.host_code"
        )
    ).fetchall()

    print(f"\n  {'HOST_CODE':35s}  {'IP':18s}  {'OS':25s}  {'AGENT':8s}  LAST_HB")
    print(f"  {'-'*35}  {'-'*18}  {'-'*25}  {'-'*8}  {'-'*16}")
    for h in hosts:
        hb = str(h[5])[:16] if h[5] else "never"
        print(
            f"  {h[0]:35s}  {str(h[2] or '—'):18s}  "
            f"{(h[3] or '—')[:25]:25s}  {(h[4] or '—'):8s}  {hb}"
        )

    total_hosts = conn.execute(
        sa.text("SELECT count(*) FROM registry.host")
    ).scalar()
    total_agents = conn.execute(
        sa.text("SELECT count(*) FROM discovery.collector_agent WHERE is_active=true")
    ).scalar()
    linked_agents = conn.execute(
        sa.text("SELECT count(*) FROM discovery.collector_agent WHERE is_active=true AND host_id IS NOT NULL")
    ).scalar()

    print(f"\n  Hosturi totale în DB : {total_hosts}")
    print(f"  Agenți activi        : {total_agents}")
    print(f"  Agenți cu host_id    : {linked_agents}")
    print(f"  Agenți nelinkat      : {total_agents - linked_agents}")


def main() -> None:
    print(f"\ninternalCMDB sync — hz.118 LXC matrix — {NOW.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  DB: {_host}:{_port}/{os.environ['POSTGRES_DB']}")

    with engine.begin() as conn:
        # 1. Audit curent
        audit_result = audit_current_state(conn)
        existing_codes = audit_result["existing_host_codes"]

        # 2. Fetch taxonomy terms
        terms = get_taxonomy_terms(conn)

        # 3. Upsert hosts
        host_map = upsert_hosts(conn, terms, existing_codes)

        # 4. Link new LXC agents
        if host_map:
            link_agents(conn, host_map)

        # 5. Link ALL other unlinked agents that have host records
        link_all_unlinked_agents(conn)

        # 6. Final report
        final_report(conn)

    print("\n✓ Sync complet.\n")


if __name__ == "__main__":
    main()
