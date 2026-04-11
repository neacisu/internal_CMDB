"""Runtime posture audit → internalCMDB loader.

Reads ``subprojects/runtime-posture-audit/results/runtime_posture/current.json``
and upserts the discovered container / service state into the CMDB.

What gets written per run
--------------------------
- ``discovery.discovery_source``     — registered once (upsert by source_code)
- ``discovery.collection_run``       — one new row per loader invocation
- ``discovery.observed_fact``        — one row per running container per host
- ``registry.service_instance``      — upserted by (host_id, instance_name)
- ``registry.shared_service``        — upserted by service_code (canonical name)

Usage (from repo root after PostgreSQL is up and migrations applied):

    export $(grep -v '^#' .env | xargs)
    PYTHONPATH=src .venv/bin/python -m internalcmdb.loaders.runtime_posture_loader

    # Or point at a specific posture file:
    PYTHONPATH=src .venv/bin/python -m internalcmdb.loaders.runtime_posture_loader \\
        --posture-file /tmp/runtime-posture.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import sqlalchemy as sa
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_POSTURE_FILE = (
    _REPO_ROOT
    / "subprojects"
    / "runtime-posture-audit"
    / "results"
    / "runtime_posture"
    / "current.json"
)

# ---------------------------------------------------------------------------
# Container name → canonical service_kind term_code mapping
# ---------------------------------------------------------------------------

_CONTAINER_NAME_TO_SERVICE_KIND: dict[str, str] = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "pgbouncer": "pgbouncer",
    "redis": "redis",
    "traefik": "traefik",
    "openbao": "openbao",
    "vault": "openbao",
    "zitadel": "zitadel",
    "grafana": "grafana",
    "prometheus": "prometheus",
    "loki": "loki",
    "tempo": "tempo",
    "otel": "otel_collector",
    "otelcol": "otel_collector",
    "cadvisor": "cadvisor",
    "node-exporter": "node_exporter",
    "node_exporter": "node_exporter",
    "pve-exporter": "pve_exporter",
    "pve_exporter": "pve_exporter",
    "postgres-exporter": "postgres_exporter",
    "postgres_exporter": "postgres_exporter",
    "oauth2-proxy": "oauth2_proxy",
    "oauth2_proxy": "oauth2_proxy",
    "vllm": "vllm",
    "ollama": "ollama",
    "open-webui": "open_webui",
    "openwebui": "open_webui",
    "n8n": "n8n",
    "activepieces": "activepieces",
    "cloudbeaver": "cloudbeaver",
    "watchtower": "watchtower",
    "kafka": "kafka",
    "neo4j": "neo4j",
    "temporal": "temporal",
    "roundcube": "roundcube",
    "stalwart": "stalwart",
    "llm-guard": "llm_guard",
    "llm_guard": "llm_guard",
}


def _infer_service_kind(container_name: str) -> str:
    """Map a Docker container name to a service_kind term_code."""
    name_lower = container_name.lower()
    # Strip compose project prefix (project-service-N)
    for fragment, kind in _CONTAINER_NAME_TO_SERVICE_KIND.items():
        if fragment in name_lower:
            return kind
    return "application_worker"


def _container_is_running(status: str) -> bool:
    return status.lower().startswith("up")


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


def _get_host_id_by_code(conn: sa.engine.Connection, host_code: str) -> uuid.UUID | None:
    row = conn.execute(
        sa.text("SELECT host_id FROM registry.host WHERE host_code = :code"),
        {"code": host_code},
    ).fetchone()
    return cast(uuid.UUID, row[0]) if row else None


# ---------------------------------------------------------------------------
# Loader context (bundles connection + taxonomy + run identity)
# ---------------------------------------------------------------------------


@dataclass
class _LoadCtx:
    conn: sa.engine.Connection
    term_map: dict[tuple[str, str], uuid.UUID]
    run_id: uuid.UUID


# ---------------------------------------------------------------------------
# DiscoverySource
# ---------------------------------------------------------------------------

_SOURCE_CODE = "runtime_posture_audit_cluster"


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
            "kind": _term(term_map, "discovery_source_kind", "runtime_posture_audit"),
            "code": _SOURCE_CODE,
            "name": "Cluster Runtime Posture Audit",
            "tool": "subprojects/runtime-posture-audit/audit_runtime_posture.py",
            "desc": (
                "Read-only runtime posture: Docker containers, systemd units, "
                "backup/HA indicators, AI runtime services."
            ),
        },
    )
    return source_id


# ---------------------------------------------------------------------------
# SharedService upsert
# ---------------------------------------------------------------------------


def _upsert_shared_service(ctx: _LoadCtx, service_kind_code: str) -> uuid.UUID:
    service_code = service_kind_code
    row = ctx.conn.execute(
        sa.text("SELECT shared_service_id FROM registry.shared_service WHERE service_code = :code"),
        {"code": service_code},
    ).fetchone()
    if row:
        return cast(uuid.UUID, row[0])

    svc_id = uuid.uuid4()
    ctx.conn.execute(
        sa.text(
            """
            INSERT INTO registry.shared_service
              (shared_service_id, service_code, name,
               service_kind_term_id, environment_term_id, lifecycle_term_id)
            VALUES
              (:id, :code, :name, :kind, :env, :lifecycle)
            ON CONFLICT (service_code) DO NOTHING
            """
        ),
        {
            "id": svc_id,
            "code": service_code,
            "name": service_kind_code.replace("_", " ").title(),
            "kind": _term(
                ctx.term_map, "service_kind", service_kind_code, fallback="application_worker"
            ),
            "env": _term(ctx.term_map, "environment", "production", fallback="production"),
            "lifecycle": _term(ctx.term_map, "lifecycle_status", "active"),
        },
    )
    # Re-fetch in case of ON CONFLICT
    row2 = ctx.conn.execute(
        sa.text("SELECT shared_service_id FROM registry.shared_service WHERE service_code = :code"),
        {"code": service_code},
    ).fetchone()
    return cast(uuid.UUID, row2[0]) if row2 else svc_id


# ---------------------------------------------------------------------------
# ServiceInstance upsert
# ---------------------------------------------------------------------------


def _upsert_service_instance(
    ctx: _LoadCtx,
    host_id: uuid.UUID,
    shared_service_id: uuid.UUID,
    container: dict[str, Any],
) -> None:
    instance_name: str = container.get("name") or "unknown"
    image: str = container.get("image") or ""
    status: str = container.get("status") or ""

    existing = ctx.conn.execute(
        sa.text(
            """
            SELECT service_instance_id FROM registry.service_instance
            WHERE  host_id = :host AND instance_name = :name
            """
        ),
        {"host": host_id, "name": instance_name},
    ).fetchone()

    if existing:
        ctx.conn.execute(
            sa.text(
                """
                UPDATE registry.service_instance SET
                  image_reference   = :image,
                  status_text       = :status,
                  collection_run_id = :run_id,
                  observed_at       = now()
                WHERE service_instance_id = :id
                """
            ),
            {
                "id": existing[0],
                "image": image,
                "status": status or "unknown",
                "run_id": ctx.run_id,
            },
        )
    else:
        ctx.conn.execute(
            sa.text(
                """
                INSERT INTO registry.service_instance
                  (service_instance_id, shared_service_id, host_id,
                   runtime_kind_term_id, instance_name, container_name,
                   image_reference, status_text,
                   collection_run_id, observed_at)
                VALUES
                  (:id, :svc, :host,
                   :runtime, :name, :cname,
                   :image, :status,
                   :run_id, now())
                """
            ),
            {
                "id": uuid.uuid4(),
                "svc": shared_service_id,
                "host": host_id,
                "runtime": _term(ctx.term_map, "runtime_kind", "docker_container"),
                "name": instance_name,
                "cname": instance_name,
                "image": image,
                "status": status or "unknown",
                "run_id": ctx.run_id,
            },
        )


# ---------------------------------------------------------------------------
# ObservedFact per host runtime snapshot
# ---------------------------------------------------------------------------


def _insert_observed_fact(
    ctx: _LoadCtx,
    host_id: uuid.UUID,
    data: dict[str, Any],
) -> None:
    from internalcmdb.governance.redaction_scanner import RedactionScanner  # noqa: PLC0415

    fact_payload: dict[str, Any] = {
        "docker_present": data.get("docker_present"),
        "docker_server": data.get("docker_server"),
        "container_count": len(data.get("containers") or []),
        "containers_all_count": len(data.get("containers_all") or []),
        "indicators_count": len(data.get("indicators") or []),
        "paths": data.get("paths"),
    }

    scanner = RedactionScanner()
    scan_result = scanner.scan_fact_payload(fact_payload)
    if not scan_result.safe:
        print(
            f"  REDACT: runtime_posture fact rejected for host {host_id} "
            f"— matched {scan_result.matched_patterns}"
        )
        return

    ctx.conn.execute(
        sa.text(
            """
            INSERT INTO discovery.observed_fact
              (observed_fact_id, collection_run_id,
               entity_kind_term_id, entity_id,
               fact_namespace, fact_key, fact_value_jsonb,
               observation_status_term_id, observed_at)
            VALUES
              (:id, :run,
               :entity, :eid,
               :ns, :key, CAST(:val AS jsonb),
               :obs_status, now())
            """
        ),
        {
            "id": uuid.uuid4(),
            "run": ctx.run_id,
            "entity": _term(ctx.term_map, "entity_kind", "host"),
            "eid": host_id,
            "ns": "runtime_posture",
            "key": "runtime_posture_snapshot",
            "val": json.dumps(fact_payload),
            "obs_status": _term(ctx.term_map, "observation_status", "observed"),
        },
    )


# ---------------------------------------------------------------------------
# Per-node loader
# ---------------------------------------------------------------------------


def _running_names_from_posture(data: dict[str, Any]) -> set[str]:
    """Names of containers reported as running in the posture payload."""
    running_containers: list[Any] = cast(list[Any], data.get("containers") or [])
    return {
        str(c_inner["name"])
        for c_inner in (cast(dict[str, Any], c) for c in running_containers if isinstance(c, dict))
        if c_inner.get("name")
    }


def _upsert_container_row(
    ctx: _LoadCtx,
    host_id: uuid.UUID,
    c_raw: Any,
    running_names: set[str],
) -> None:
    """Normalise one container dict from ``containers_all`` and upsert CMDB rows."""
    if not isinstance(c_raw, dict):
        return

    container: dict[str, Any] = cast(dict[str, Any], c_raw)
    name: str = str(container.get("name") or "")
    if not name:
        return

    # If not in running_containers list, mark status as stopped
    if name not in running_names:
        container = dict(container)
        container["status"] = container.get("status") or "Exited"

    service_kind_code = _infer_service_kind(name)
    svc_id = _upsert_shared_service(ctx, service_kind_code)
    _upsert_service_instance(ctx, host_id, svc_id, container)


def _load_node(ctx: _LoadCtx, node: dict[str, Any]) -> bool:
    alias: str = node.get("alias") or ""
    if not alias or not node.get("ok"):
        return False

    host_id = _get_host_id_by_code(ctx.conn, alias)
    if host_id is None:
        print(f"  SKIP {alias}: host not in registry — run ssh_audit_loader first")
        return False

    data: dict[str, Any] = cast(dict[str, Any], node.get("data") or {})

    _insert_observed_fact(ctx, host_id, data)

    running_names = _running_names_from_posture(data)
    all_containers: list[Any] = cast(list[Any], data.get("containers_all") or [])
    for c_raw in all_containers:
        _upsert_container_row(ctx, host_id, c_raw, running_names)

    return True


# ---------------------------------------------------------------------------
# Main load
# ---------------------------------------------------------------------------


def load(conn: sa.engine.Connection, posture_data: dict[str, Any]) -> None:
    term_map = _load_term_map(conn)
    if not term_map:
        print(
            "ERROR: taxonomy term map empty — run taxonomy_seed.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    results_raw: Any = posture_data.get("results") or []
    results: list[dict[str, Any]] = (
        cast(list[dict[str, Any]], results_raw) if isinstance(results_raw, list) else []
    )
    audit_ts: str = posture_data.get("audit_ts") or datetime.now(UTC).isoformat()

    source_id = _ensure_discovery_source(conn, term_map)

    run_id = uuid.uuid4()
    ctx = _LoadCtx(conn=conn, term_map=term_map, run_id=run_id)
    run_code = f"runtime_posture_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{run_id.hex[:8]}"
    node_aliases = [n_item.get("alias", "") for n_item in results]
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
            "executor": "runtime_posture_loader/local",
            "summary": json.dumps({"node_count": len(results)}),
        },
    )

    loaded = 0
    skipped = 0
    for n_raw in results:
        alias = n_raw.get("alias", "<unknown>")
        try:
            ok = _load_node(ctx, n_raw)
            if ok:
                loaded += 1
                print(f"  OK   {alias}")
            else:
                skipped += 1
        except Exception as exc:
            print(f"  ERR  {alias}: {exc}", file=sys.stderr)

    conn.commit()
    print(f"\nDone: {loaded} nodes loaded, {skipped} skipped. collection_run_id={run_id}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load runtime posture audit into internalCMDB")
    parser.add_argument(
        "--posture-file",
        type=Path,
        default=_DEFAULT_POSTURE_FILE,
        help="Path to runtime_posture current.json",
    )
    args = parser.parse_args(argv)

    posture_path: Path = args.posture_file
    if not posture_path.exists():
        print(f"ERROR: posture file not found: {posture_path}", file=sys.stderr)
        sys.exit(1)

    envelope = json.loads(posture_path.read_text(encoding="utf-8"))
    posture_data: dict[str, Any] = cast(
        dict[str, Any],
        envelope.get("payload") or envelope,
    )

    engine = sa.create_engine(_build_url())
    with engine.connect() as conn:
        load(conn, posture_data)
    engine.dispose()


if __name__ == "__main__":
    main()
