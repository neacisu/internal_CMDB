"""SSH full-audit → internalCMDB loader.

Reads ``subprojects/cluster-full-audit/results/full_cluster_audit/current.json``
and upserts the discovered state into the CMDB registry.

What gets written per run
--------------------------
- ``discovery.discovery_source``   — registered once (upsert by source_code)
- ``discovery.collection_run``     — one new row per loader invocation
- ``registry.host``                — upserted by host_code = SSH alias
- ``registry.host_hardware_snapshot`` — one row per (host_id, collection_run_id)
- ``registry.gpu_device``          — upserted by (host_id, gpu_uuid)

Usage (from repo root after PostgreSQL is up and migrations applied):

    export $(grep -v '^#' .env | xargs)
    PYTHONPATH=src .venv/bin/python -m internalcmdb.loaders.ssh_audit_loader

    # Or point at a specific audit file:
    PYTHONPATH=src .venv/bin/python -m internalcmdb.loaders.ssh_audit_loader \\
        --audit-file /tmp/cluster-audit.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import sqlalchemy as sa
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]  # …/ProiecteIT
_DEFAULT_AUDIT_FILE = (
    _REPO_ROOT
    / "subprojects"
    / "cluster-full-audit"
    / "results"
    / "full_cluster_audit"
    / "current.json"
)
_DEFAULT_SSH_CHECK_FILE = (
    _REPO_ROOT
    / "subprojects"
    / "cluster-ssh-checker"
    / "results"
    / "ssh_connectivity"
    / "current.json"
)

# ---------------------------------------------------------------------------
# OS string → taxonomy term_code mapping
# ---------------------------------------------------------------------------


def _os_family_term_code(os_string: str) -> str:
    os_lower = os_string.lower()
    if "ubuntu" in os_lower:
        return "ubuntu"
    if "debian" in os_lower:
        return "debian"
    if "macos" in os_lower or "darwin" in os_lower:
        return "macos"
    return "unknown"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _build_url() -> str:
    load_dotenv()
    host = os.environ["POSTGRES_HOST"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def _load_term_map(conn: sa.engine.Connection) -> dict[tuple[str, str], uuid.UUID]:
    """Return {(domain_code, term_code): taxonomy_term_id} for all active terms."""
    rows = conn.execute(
        sa.text(
            """
            SELECT d.domain_code, t.term_code, t.taxonomy_term_id
            FROM   taxonomy.taxonomy_term  t
            JOIN   taxonomy.taxonomy_domain d USING (taxonomy_domain_id)
            WHERE  t.is_active = TRUE
            """
        )
    ).fetchall()
    return {(r[0], r[1]): r[2] for r in rows}


def _term(
    term_map: dict[tuple[str, str], uuid.UUID],
    domain: str,
    code: str,
    *,
    fallback: str | None = None,
) -> uuid.UUID:
    key = (domain, code)
    if key in term_map:
        return term_map[key]
    if fallback is not None:
        fb_key = (domain, fallback)
        if fb_key in term_map:
            return term_map[fb_key]
    raise KeyError(f"Taxonomy term not found: ({domain!r}, {code!r})")


# ---------------------------------------------------------------------------
# DiscoverySource registration
# ---------------------------------------------------------------------------

_SOURCE_CODE = "ssh_full_audit_cluster"


def _ensure_discovery_source(
    conn: sa.engine.Connection,
    term_map: dict[tuple[str, str], uuid.UUID],
) -> uuid.UUID:
    row = conn.execute(
        sa.text(
            "SELECT discovery_source_id FROM discovery.discovery_source WHERE source_code = :code"
        ),
        {"code": _SOURCE_CODE},
    ).fetchone()
    if row:
        return cast(uuid.UUID, row[0])

    source_id = uuid.uuid4()
    conn.execute(
        sa.text(
            """
            INSERT INTO discovery.discovery_source
              (discovery_source_id, source_kind_term_id, source_code, name,
               tool_path, is_read_only, description)
            VALUES
              (:id, :kind, :code, :name, :tool, TRUE, :desc)
            """
        ),
        {
            "id": source_id,
            "kind": _term(term_map, "discovery_source_kind", "ssh_full_audit"),
            "code": _SOURCE_CODE,
            "name": "Cluster SSH Full Audit",
            "tool": "subprojects/cluster-full-audit/audit_full.py",
            "desc": (
                "Read-only SSH audit of all cluster nodes: system, hardware, "
                "GPU, disk, network, Docker, services, firewall, security."
            ),
        },
    )
    return source_id


# ---------------------------------------------------------------------------
# CollectionRun creation
# ---------------------------------------------------------------------------


def _create_collection_run(
    conn: sa.engine.Connection,
    source_id: uuid.UUID,
    audit_ts: str,
    term_map: dict[tuple[str, str], uuid.UUID],
    node_aliases: list[str],
) -> uuid.UUID:
    run_id = uuid.uuid4()
    run_code = f"ssh_full_audit_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{run_id.hex[:8]}"
    conn.execute(
        sa.text(
            """
            INSERT INTO discovery.collection_run
              (collection_run_id, discovery_source_id, run_code,
               target_scope_jsonb, started_at, finished_at,
               status_term_id, executor_identity, summary_jsonb)
            VALUES
              (:id, :src, :code,
               CAST(:scope AS jsonb), CAST(:started AS timestamptz), now(),
               :status, :executor, CAST(:summary AS jsonb))
            """
        ),
        {
            "id": run_id,
            "src": source_id,
            "code": run_code,
            "scope": json.dumps({"hosts": node_aliases}),
            "started": audit_ts,
            "status": _term(term_map, "collection_run_status", "succeeded"),
            "executor": "ssh_audit_loader/local",
            "summary": json.dumps({"host_count": len(node_aliases)}),
        },
    )
    return run_id


# ---------------------------------------------------------------------------
# Host upsert
# ---------------------------------------------------------------------------


def _upsert_host(
    conn: sa.engine.Connection,
    node: dict[str, Any],
    term_map: dict[tuple[str, str], uuid.UUID],
    _run_id: uuid.UUID,
    ssh_ok_set: set[str],
) -> uuid.UUID:
    alias: str = node["alias"]
    system: dict[str, Any] = cast(dict[str, Any], node.get("system") or {})
    gpu_list: list[dict[str, Any]] = cast(list[dict[str, Any]], node.get("gpu") or [])

    os_text: str = system.get("os") or "unknown"
    hostname_text: str = system.get("hostname") or alias
    kernel_text: str = system.get("kernel") or ""
    arch_text: str = system.get("arch") or ""
    pub_ip: str | None = node.get("pub_ip")

    os_family_code = _os_family_term_code(os_text)
    is_gpu: bool = bool(gpu_list) and any(bool(g.get("gpu_uuid")) for g in gpu_list)
    is_docker: bool = bool(node.get("docker"))

    entity_term = _term(term_map, "entity_kind", "host")
    env_term = _term(term_map, "environment", "production")
    lifecycle_term_code = "active" if ssh_ok_set and alias in ssh_ok_set else "unknown"
    lifecycle_term = _term(term_map, "lifecycle_status", lifecycle_term_code, fallback="unknown")
    os_term = _term(term_map, "os_family", os_family_code, fallback="unknown")

    # Determine primary host role
    docker_raw: Any = node.get("docker")
    docker_info: dict[str, Any] = (
        cast(dict[str, Any], docker_raw) if isinstance(docker_raw, dict) else {}
    )
    containers_raw: Any = docker_info.get("containers")
    docker_containers: list[dict[str, Any]] = (
        [cast(dict[str, Any], c) for c in containers_raw if isinstance(c, dict)]
        if isinstance(containers_raw, list)
        else []
    )
    n_containers = sum(1 for c in docker_containers if c.get("state") == "running")
    if is_gpu:
        role_code = "gpu_inference_node"
    elif n_containers > 5:  # noqa: PLR2004
        role_code = "application_runtime_host"
    elif alias in ("orchestrator",):
        role_code = "automation_host"
    elif alias in ("postgres-main",):
        role_code = "database_host"
    else:
        role_code = "monitored_host"

    primary_role_term = _term(term_map, "host_role", role_code, fallback="monitored_host")

    # Check if host already exists
    existing = conn.execute(
        sa.text("SELECT host_id FROM registry.host WHERE host_code = :code"),
        {"code": alias},
    ).fetchone()

    if existing:
        host_id: uuid.UUID = existing[0]
        conn.execute(
            sa.text(
                """
                UPDATE registry.host SET
                  hostname                  = :hostname,
                  ssh_alias                 = :alias,
                  entity_kind_term_id       = :entity,
                  primary_host_role_term_id = :role,
                  environment_term_id       = :env,
                  lifecycle_term_id         = :lifecycle,
                  os_family_term_id         = :os_fam,
                  os_version_text           = :os_ver,
                  kernel_version_text       = :kernel,
                  architecture_text         = :arch,
                  is_gpu_capable            = :gpu,
                  is_docker_host            = :docker,
                  primary_public_ipv4       = :pub_ip,
                  observed_hostname         = :obs_hostname,
                  confidence_score          = 0.95,
                  updated_at                = now()
                WHERE host_id = :id
                """
            ),
            {
                "id": host_id,
                "hostname": hostname_text,
                "alias": alias,
                "entity": entity_term,
                "role": primary_role_term,
                "env": env_term,
                "lifecycle": lifecycle_term,
                "os_fam": os_term,
                "os_ver": os_text,
                "kernel": kernel_text,
                "arch": arch_text,
                "gpu": is_gpu,
                "docker": is_docker,
                "pub_ip": pub_ip,
                "obs_hostname": hostname_text,
            },
        )
    else:
        host_id = uuid.uuid4()
        conn.execute(
            sa.text(
                """
                INSERT INTO registry.host
                  (host_id, host_code, hostname, ssh_alias, fqdn,
                   entity_kind_term_id, primary_host_role_term_id,
                   environment_term_id, lifecycle_term_id, os_family_term_id,
                   os_version_text, kernel_version_text, architecture_text,
                   is_gpu_capable, is_docker_host, is_hypervisor,
                   primary_public_ipv4, observed_hostname, confidence_score)
                VALUES
                  (:id, :code, :hostname, :alias, NULL,
                   :entity, :role,
                   :env, :lifecycle, :os_fam,
                   :os_ver, :kernel, :arch,
                   :gpu, :docker, FALSE,
                   :pub_ip, :obs_hostname, 0.95)
                """
            ),
            {
                "id": host_id,
                "code": alias,
                "hostname": hostname_text,
                "alias": alias,
                "entity": entity_term,
                "role": primary_role_term,
                "env": env_term,
                "lifecycle": lifecycle_term,
                "os_fam": os_term,
                "os_ver": os_text,
                "kernel": kernel_text,
                "arch": arch_text,
                "gpu": is_gpu,
                "docker": is_docker,
                "pub_ip": pub_ip,
                "obs_hostname": hostname_text,
            },
        )

    return host_id


# ---------------------------------------------------------------------------
# Hardware snapshot
# ---------------------------------------------------------------------------


def _insert_hardware_snapshot(
    conn: sa.engine.Connection,
    host_id: uuid.UUID,
    run_id: uuid.UUID,
    node: dict[str, Any],
) -> None:
    snapshot_id = uuid.uuid4()
    hw_raw: Any = node.get("hardware")
    hardware: dict[str, Any] = cast(dict[str, Any], hw_raw) if isinstance(hw_raw, dict) else {}

    def _kb_to_bytes(val: Any) -> int | None:
        n = _int_or_none(val)
        return n * 1024 if n is not None else None

    conn.execute(
        sa.text(
            """
            INSERT INTO registry.host_hardware_snapshot
              (host_hardware_snapshot_id, host_id, collection_run_id,
               cpu_model, cpu_socket_count, cpu_core_count,
               ram_total_bytes, ram_free_bytes,
               swap_total_bytes,
               gpu_count, hardware_jsonb, observed_at)
            VALUES
              (:snap_id, :host_id, :run_id,
               :cpu_model, :cpu_phys, :cpu_cores,
               :ram_total, :ram_free,
               :swap_total,
               :gpu_count, CAST(:hw_json AS jsonb), now())
            """
        ),
        {
            "snap_id": snapshot_id,
            "host_id": host_id,
            "run_id": run_id,
            "cpu_model": hardware.get("cpu_model"),
            "cpu_phys": _int_or_none(hardware.get("cpu_physical")),
            "cpu_cores": _int_or_none(hardware.get("cpu_cores")),
            "ram_total": _kb_to_bytes(hardware.get("ram_total_kb")),
            "ram_free": _kb_to_bytes(hardware.get("ram_free_kb")),
            "swap_total": _kb_to_bytes(hardware.get("swap_total_kb")),
            "gpu_count": _int_or_none(hardware.get("gpu_count")),
            "hw_json": json.dumps(hardware),
        },
    )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# GPU device upsert
# ---------------------------------------------------------------------------


def _upsert_gpu_devices(
    conn: sa.engine.Connection,
    host_id: uuid.UUID,
    gpu_list: list[dict[str, Any]],
    run_id: uuid.UUID,
) -> None:
    for idx, gpu in enumerate(gpu_list):
        gpu_uuid: str | None = gpu.get("gpu_uuid")
        if not gpu_uuid:
            continue

        existing = conn.execute(
            sa.text(
                "SELECT gpu_device_id FROM registry.gpu_device "
                "WHERE host_id = :host AND uuid_text = :uuid"
            ),
            {"host": host_id, "uuid": gpu_uuid},
        ).fetchone()

        def _dec(v: Any) -> float | None:
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        params: dict[str, Any] = {
            "model": gpu.get("gpu_name"),
            "vendor": "NVIDIA",
            "driver": gpu.get("gpu_driver"),
            "mem_total": _int_or_none(gpu.get("gpu_mem_total")),
            "mem_used": _int_or_none(gpu.get("gpu_mem_used")),
            "mem_free": _int_or_none(gpu.get("gpu_mem_free")),
            "util_gpu": _dec(gpu.get("gpu_util")),
            "util_mem": _dec(gpu.get("gpu_mem_util")),
            "temp": _dec(gpu.get("gpu_temp")),
            "pwr_draw": _dec(gpu.get("gpu_power_draw")),
            "pwr_limit": _dec(gpu.get("gpu_power_limit")),
            "fan": _dec(gpu.get("gpu_fan")),
            "compute_cap": gpu.get("gpu_compute_cap"),
        }

        if existing:
            conn.execute(
                sa.text(
                    """
                    UPDATE registry.gpu_device SET
                      model_name             = :model,
                      vendor_name            = :vendor,
                      driver_version_text    = :driver,
                      memory_total_mb        = :mem_total,
                      memory_used_mb         = :mem_used,
                      memory_free_mb         = :mem_free,
                      utilization_gpu_pct    = :util_gpu,
                      utilization_memory_pct = :util_mem,
                      temperature_celsius    = :temp,
                      power_draw_watts       = :pwr_draw,
                      power_limit_watts      = :pwr_limit,
                      fan_pct                = :fan,
                      compute_capability     = :compute_cap,
                      collection_run_id      = :run,
                      observed_at            = now()
                    WHERE gpu_device_id = :id
                    """
                ),
                {"id": existing[0], "run": run_id, **params},
            )
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO registry.gpu_device
                      (gpu_device_id, host_id, gpu_index, uuid_text,
                       model_name, vendor_name, driver_version_text,
                       memory_total_mb, memory_used_mb, memory_free_mb,
                       utilization_gpu_pct, utilization_memory_pct,
                       temperature_celsius, power_draw_watts, power_limit_watts,
                       fan_pct, compute_capability,
                       collection_run_id, observed_at)
                    VALUES
                      (:id, :host, :idx, :uuid,
                       :model, :vendor, :driver,
                       :mem_total, :mem_used, :mem_free,
                       :util_gpu, :util_mem,
                       :temp, :pwr_draw, :pwr_limit,
                       :fan, :compute_cap,
                       :run, now())
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "host": host_id,
                    "idx": idx,
                    "uuid": gpu_uuid,
                    "run": run_id,
                    **params,
                },
            )


# ---------------------------------------------------------------------------
# Main load logic
# ---------------------------------------------------------------------------


def load(
    conn: sa.engine.Connection,
    audit_data: dict[str, Any],
    ssh_check_data: dict[str, Any] | None = None,
) -> None:
    term_map = _load_term_map(conn)
    if not term_map:
        print(
            "ERROR: taxonomy term map is empty — run taxonomy_seed.py before this loader.",
            file=sys.stderr,
        )
        sys.exit(1)

    nodes: list[dict[str, Any]] = audit_data.get("nodes") or []
    audit_ts: str = audit_data.get("audit_ts") or datetime.now(UTC).isoformat()

    # Build set of hosts that answered SSH OK (from connectivity check)
    ssh_ok_set: set[str] = set()
    if ssh_check_data:
        payload_raw: Any = ssh_check_data.get("payload")
        payload_dict: dict[str, Any] = (
            cast(dict[str, Any], payload_raw) if isinstance(payload_raw, dict) else {}
        )
        for r_raw in cast(list[Any], payload_dict.get("results") or []):
            if isinstance(r_raw, dict):
                r: dict[str, Any] = cast(dict[str, Any], r_raw)
                if r.get("ok") and isinstance(r.get("host"), str):
                    ssh_ok_set.add(cast(str, r["host"]))

    source_id = _ensure_discovery_source(conn, term_map)
    node_aliases = [n["alias"] for n in nodes if "alias" in n]
    run_id = _create_collection_run(conn, source_id, audit_ts, term_map, node_aliases)

    loaded = 0
    errors = 0
    for node in nodes:
        alias = node.get("alias", "<unknown>")
        if node.get("error"):
            print(f"  SKIP {alias}: audit error — {node['error']}")
            continue
        try:
            host_id = _upsert_host(conn, node, term_map, run_id, ssh_ok_set)
            _insert_hardware_snapshot(conn, host_id, run_id, node)
            _upsert_gpu_devices(conn, host_id, node.get("gpu") or [], run_id)
            loaded += 1
            print(f"  OK   {alias} → host_id={host_id}")
        except Exception as exc:
            print(f"  ERR  {alias}: {exc}", file=sys.stderr)
            errors += 1

    conn.commit()
    print(f"\nDone: {loaded} hosts loaded, {errors} errors. collection_run_id={run_id}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load SSH full audit into internalCMDB")
    parser.add_argument(
        "--audit-file",
        type=Path,
        default=_DEFAULT_AUDIT_FILE,
        help="Path to full_cluster_audit current.json",
    )
    parser.add_argument(
        "--ssh-check-file",
        type=Path,
        default=_DEFAULT_SSH_CHECK_FILE,
        help="Path to ssh_connectivity current.json (optional)",
    )
    args = parser.parse_args(argv)

    audit_path: Path = args.audit_file
    if not audit_path.exists():
        print(f"ERROR: audit file not found: {audit_path}", file=sys.stderr)
        sys.exit(1)

    audit_envelope = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_data: dict[str, Any] = audit_envelope.get("payload") or audit_envelope

    ssh_check_data: dict[str, Any] | None = None
    ssh_check_path: Path = args.ssh_check_file
    if ssh_check_path.exists():
        ssh_check_data = json.loads(ssh_check_path.read_text(encoding="utf-8"))

    engine = sa.create_engine(_build_url())
    with engine.connect() as conn:
        load(conn, audit_data, ssh_check_data)
    engine.dispose()


if __name__ == "__main__":
    main()
