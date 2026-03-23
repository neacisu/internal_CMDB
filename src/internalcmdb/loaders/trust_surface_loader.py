"""Trust surface audit → internalCMDB loader.

Reads ``subprojects/trust-surface-audit/results/trust_surface/current.json``
and upserts the SSH/TLS/secret surface findings into the CMDB.

What gets written per run
--------------------------
- ``discovery.discovery_source``   — registered once (upsert by source_code)
- ``discovery.collection_run``     — one new row per loader invocation
- ``discovery.observed_fact``      — one row per host for sshd config findings
- ``discovery.evidence_artifact``  — one row per host for raw trust surface data
- ``registry.service_exposure``    — upserted endpoint probe results (TLS endpoints)

Usage (from repo root after PostgreSQL is up and migrations applied):

    export $(grep -v '^#' .env | xargs)
    PYTHONPATH=src .venv/bin/python -m internalcmdb.loaders.trust_surface_loader

    # Or point at a specific file:
    PYTHONPATH=src .venv/bin/python -m internalcmdb.loaders.trust_surface_loader \\
        --audit-file /tmp/trust-surface.json
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
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_AUDIT_FILE = (
    _REPO_ROOT
    / "subprojects"
    / "trust-surface-audit"
    / "results"
    / "trust_surface"
    / "current.json"
)

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
# DiscoverySource
# ---------------------------------------------------------------------------

_SOURCE_CODE = "trust_surface_audit_cluster"


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
            "kind": _term(term_map, "discovery_source_kind", "trust_surface_audit"),
            "code": _SOURCE_CODE,
            "name": "Cluster Trust Surface Audit",
            "tool": "subprojects/trust-surface-audit/audit_trust_surface.py",
            "desc": (
                "Read-only trust surface audit: SSHD config, SSH dir permissions, "
                "secret path exposure, TLS endpoint probes."
            ),
        },
    )
    return source_id


# ---------------------------------------------------------------------------
# SSHD config analysers
# ---------------------------------------------------------------------------


def _sshd_directive_key_value(stripped: str) -> tuple[str, str] | None:
    """Map one normalised sshd_config line to ``(finding_key, value)`` if recognised."""
    parts = stripped.split()
    tail = parts[-1] if parts else ""
    if stripped.startswith("permitrootlogin"):
        return "permit_root_login", tail or "unknown"
    if stripped.startswith("passwordauthentication"):
        return "password_auth", tail or "unknown"
    if stripped.startswith("pubkeyauthentication"):
        return "pubkey_auth", tail or "unknown"
    if stripped.startswith("port "):
        return "port", tail or "22"
    return None


def _sshd_findings(sshd_lines: list[str]) -> dict[str, str]:
    """Parse sshd_config lines into a flat findings dict."""
    findings: dict[str, str] = {}
    for line in sshd_lines:
        stripped = line.strip().lower()
        kv = _sshd_directive_key_value(stripped)
        if kv is not None:
            findings[kv[0]] = kv[1]
    return findings


def _sshd_risk_level(findings: dict[str, str]) -> str:
    """Derive a risk level string from SSHD findings."""
    if findings.get("permit_root_login") == "yes" and findings.get("password_auth") == "yes":
        return "high"
    if findings.get("permit_root_login") == "yes":
        return "medium"
    if findings.get("password_auth") == "yes":
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Per-host loader
# ---------------------------------------------------------------------------


def _load_host(
    conn: sa.engine.Connection,
    node: dict[str, Any],
    term_map: dict[tuple[str, str], uuid.UUID],
    run_id: uuid.UUID,
) -> bool:
    alias: str = node.get("alias") or ""
    if not alias or not node.get("ok"):
        return False

    host_id = _get_host_id_by_code(conn, alias)
    if host_id is None:
        print(f"  SKIP {alias}: not in registry — run ssh_audit_loader first")
        return False

    data: dict[str, Any] = cast(dict[str, Any], node.get("data") or {})

    # ── SSHD config observed fact ─────────────────────────────────────────
    from internalcmdb.governance.redaction_scanner import RedactionScanner  # noqa: PLC0415

    sshd_raw: Any = data.get("sshd") or []
    sshd_lines: list[str] = (
        [str(line) for line in sshd_raw if isinstance(line, str)]
        if isinstance(sshd_raw, list)
        else []
    )
    sshd_findgs = _sshd_findings(sshd_lines)
    risk = _sshd_risk_level(sshd_findgs)

    fact_payload: dict[str, Any] = {
        "sshd_raw": sshd_lines,
        "findings": sshd_findgs,
        "risk_level": risk,
        "secret_paths_count": len(cast(list[Any], data.get("secret_paths") or [])),
        "ssh_dirs_count": len(cast(list[Any], data.get("ssh_dirs") or [])),
        "certs_count": len(cast(list[Any], data.get("certs") or [])),
    }

    scanner = RedactionScanner()
    scan_result = scanner.scan_fact_payload(fact_payload)
    if not scan_result.safe:
        print(
            f"  REDACT {alias}: sshd fact rejected — matched {scan_result.matched_patterns}"
        )
    else:
        conn.execute(
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
                "run": run_id,
                "entity": _term(term_map, "entity_kind", "host"),
                "eid": host_id,
                "ns": "trust_surface.sshd",
                "key": "sshd_config_snapshot",
                "val": json.dumps(fact_payload),
                "obs_status": _term(term_map, "observation_status", "observed"),
            },
        )

    # ── EvidenceArtifact: full raw trust surface snapshot ────────────────
    conn.execute(
        sa.text(
            """
            INSERT INTO discovery.evidence_artifact
              (evidence_artifact_id, collection_run_id,
               evidence_kind_term_id,
               mime_type, content_excerpt_text, metadata_jsonb)
            VALUES
              (:id, :run,
               :kind,
               :mime, :excerpt, CAST(:meta AS jsonb))
            """
        ),
        {
            "id": uuid.uuid4(),
            "run": run_id,
            "kind": _term(term_map, "evidence_kind", "trust_surface_snapshot"),
            "mime": "application/json",
            "excerpt": f"trust_surface host={host_id} risk={risk}",
            "meta": json.dumps(data),
        },
    )

    return True


# ---------------------------------------------------------------------------
# Endpoint probe loader
# ---------------------------------------------------------------------------


def _endpoint_health_code(ok: bool, error: str | None) -> str:
    """Derive taxonomy-friendly health code from probe outcome (no nested ternaries, S3358)."""
    if ok:
        return "healthy"
    err_lower = str(error).lower()
    if "refused" in err_lower:
        return "connection_refused"
    if "timeout" in err_lower:
        return "timeout"
    if "tls" in err_lower:
        return "tls_handshake_failed"
    return "unknown"


def _load_endpoints(
    conn: sa.engine.Connection,
    endpoints: list[Any],
    term_map: dict[tuple[str, str], uuid.UUID],
    run_id: uuid.UUID,
) -> int:
    """Write an observed_fact per probed endpoint."""
    count = 0
    for ep_raw in endpoints:
        if not isinstance(ep_raw, dict):
            continue
        ep: dict[str, Any] = cast(dict[str, Any], ep_raw)
        endpoint_str: str = str(ep.get("endpoint") or "")
        ok: bool = bool(ep.get("ok"))
        error: str | None = ep.get("error")

        health_code = _endpoint_health_code(ok, error)

        conn.execute(
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
                "run": run_id,
                "entity": _term(term_map, "entity_kind", "service_exposure"),
                "eid": uuid.uuid5(uuid.NAMESPACE_URL, endpoint_str),
                "ns": "trust_surface.endpoint",
                "key": "tls_probe_result",
                "val": json.dumps(
                    {
                        "endpoint": endpoint_str,
                        "ok": ok,
                        "error": error,
                        "health_code": health_code,
                    }
                ),
                "obs_status": _term(
                    term_map,
                    "observation_status",
                    "observed" if ok else "error",
                    fallback="observed",
                ),
            },
        )
        count += 1

    return count


# ---------------------------------------------------------------------------
# Main load
# ---------------------------------------------------------------------------


def _exit_if_empty_term_map(term_map: dict[tuple[str, str], uuid.UUID]) -> None:
    if term_map:
        return
    print(
        "ERROR: taxonomy term map empty — run taxonomy_seed.py first.",
        file=sys.stderr,
    )
    sys.exit(1)


def _audit_host_and_endpoint_lists(audit_data: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    """Normalise ``audit_data["results"]`` into host rows and endpoint rows."""
    results_raw: Any = audit_data.get("results") or {}
    if isinstance(results_raw, dict):
        results_dict = cast(dict[str, Any], results_raw)
        return (
            cast(list[Any], results_dict.get("hosts") or []),
            cast(list[Any], results_dict.get("endpoints") or []),
        )
    if isinstance(results_raw, list):
        return results_raw, []
    return [], []


def load(conn: sa.engine.Connection, audit_data: dict[str, Any]) -> None:
    term_map = _load_term_map(conn)
    _exit_if_empty_term_map(term_map)

    host_results, endpoint_results = _audit_host_and_endpoint_lists(audit_data)

    source_id = _ensure_discovery_source(conn, term_map)

    run_id = uuid.uuid4()
    run_code = f"trust_surface_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{run_id.hex[:8]}"
    node_aliases = [
        cast(dict[str, Any], n).get("alias", "") for n in host_results if isinstance(n, dict)
    ]
    conn.execute(
        sa.text(
            """
            INSERT INTO discovery.collection_run
              (collection_run_id, discovery_source_id, run_code,
               target_scope_jsonb, started_at, finished_at,
               status_term_id, executor_identity, summary_jsonb)
            VALUES
              (:id, :src, :code,
               CAST(:scope AS jsonb), now(), now(),
               :status, :executor, CAST(:summary AS jsonb))
            """
        ),
        {
            "id": run_id,
            "src": source_id,
            "code": run_code,
            "scope": json.dumps({"hosts": node_aliases}),
            "status": _term(term_map, "collection_run_status", "succeeded"),
            "executor": "trust_surface_loader/local",
            "summary": json.dumps(
                {
                    "host_count": len(host_results),
                    "endpoint_count": len(endpoint_results),
                }
            ),
        },
    )

    loaded = 0
    skipped = 0
    for n_raw in host_results:
        if not isinstance(n_raw, dict):
            continue
        n: dict[str, Any] = cast(dict[str, Any], n_raw)
        alias = n.get("alias", "<unknown>")
        try:
            ok = _load_host(conn, n, term_map, run_id)
            if ok:
                loaded += 1
                print(f"  OK   {alias}")
            else:
                skipped += 1
        except Exception as exc:
            print(f"  ERR  {alias}: {exc}", file=sys.stderr)

    ep_count = _load_endpoints(conn, endpoint_results, term_map, run_id)

    conn.commit()
    print(
        f"\nDone: {loaded} hosts + {ep_count} endpoints loaded, "
        f"{skipped} skipped. collection_run_id={run_id}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load trust surface audit into internalCMDB")
    parser.add_argument(
        "--audit-file",
        type=Path,
        default=_DEFAULT_AUDIT_FILE,
        help="Path to trust_surface current.json",
    )
    args = parser.parse_args(argv)

    audit_path: Path = args.audit_file
    if not audit_path.exists():
        print(f"ERROR: audit file not found: {audit_path}", file=sys.stderr)
        sys.exit(1)

    envelope = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_data: dict[str, Any] = cast(
        dict[str, Any],
        envelope.get("payload") or envelope,
    )

    engine = sa.create_engine(_build_url())
    with engine.connect() as conn:
        load(conn, audit_data)
    engine.dispose()


if __name__ == "__main__":
    main()
