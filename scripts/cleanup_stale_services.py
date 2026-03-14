"""One-off cleanup: migrate service_instance references from stale shared_service
entries to canonical ones, then delete the stale entries.

Stale entries were created by an earlier seed run that inserted taxonomy term
codes as service_code values without metadata.  The canonical entries (from
shared_service_seed.py v1.1) have enriched metadata.

Usage:
    python scripts/cleanup_stale_services.py
"""

import os

import sqlalchemy as sa
from dotenv import load_dotenv

load_dotenv()

# Mapping: stale service_code → canonical service_code
MIGRATE_MAP = {
    "postgresql": "internalcmdb-postgres",
    "pgbouncer": "pgbouncer-main",
    "redis": "redis-shared",
    "traefik": "traefik-proxy",
    "prometheus": "prometheus-main",
    "grafana": "grafana-main",
    "loki": "loki-main",
    "tempo": "tempo-main",
    "otel_collector": "otel-collector-main",
    "node_exporter": "node-exporter-orchestrator",
    "cadvisor": "cadvisor-orchestrator",
    "openbao": "openbao-main",
    "ollama": "ollama-embed",
    "open_webui": "open-webui-main",
    "vllm": "vllm-reasoning-32b",
    "application_worker": "internalcmdb-worker",
    # Old renamed entry
    "vllm-fast-9b": "vllm-fast-14b",
}

url = (
    f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:"
    f"{os.environ['POSTGRES_PASSWORD']}@{os.environ['POSTGRES_HOST']}:"
    f"{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ['POSTGRES_DB']}"
)

engine = sa.create_engine(url)


def main() -> None:
    """Run the cleanup."""
    with engine.connect() as conn:
        # Build ID lookup: service_code → shared_service_id
        all_svcs = conn.execute(
            sa.text("SELECT service_code, shared_service_id FROM registry.shared_service")
        ).fetchall()
        code_to_id = {r[0]: r[1] for r in all_svcs}

        migrated_instances = 0
        migrated_deps = 0

        # Migrate service_instance references
        for stale_code, canonical_code in MIGRATE_MAP.items():
            stale_id = code_to_id.get(stale_code)
            canonical_id = code_to_id.get(canonical_code)
            if not stale_id:
                continue
            if not canonical_id:
                print(f"WARNING: canonical '{canonical_code}' not found, skipping '{stale_code}'")
                continue

            # Migrate service_instance rows
            r = conn.execute(
                sa.text(
                    "UPDATE registry.service_instance "
                    "SET shared_service_id = :canonical_id "
                    "WHERE shared_service_id = :stale_id"
                ),
                {"canonical_id": canonical_id, "stale_id": stale_id},
            )
            if r.rowcount and r.rowcount > 0:
                migrated_instances += r.rowcount
                print(f"  Migrated {r.rowcount} instances: {stale_code} → {canonical_code}")

            # Migrate service_dependency (target_shared_service_id)
            r2 = conn.execute(
                sa.text(
                    "UPDATE registry.service_dependency "
                    "SET target_shared_service_id = :canonical_id "
                    "WHERE target_shared_service_id = :stale_id"
                ),
                {"canonical_id": canonical_id, "stale_id": stale_id},
            )
            if r2.rowcount and r2.rowcount > 0:
                migrated_deps += r2.rowcount

        print(
            f"Migrated {migrated_instances} service_instance rows, {migrated_deps} dependency rows."
        )

        # Now delete stale entries (including unmapped ones like n8n, kafka, neo4j, activepieces)
        # First handle entries with remaining instances (for unmapped stale codes)
        stale_codes = [
            c
            for c in code_to_id
            if c
            not in [
                "internalcmdb-postgres",
                "pgbouncer-main",
                "redis-shared",
                "traefik-proxy",
                "prometheus-main",
                "grafana-main",
                "loki-main",
                "tempo-main",
                "otel-collector-main",
                "node-exporter-orchestrator",
                "cadvisor-orchestrator",
                "postgres-exporter-internalcmdb",
                "pve-exporter-main",
                "openbao-main",
                "zitadel-main",
                "oauth2-proxy-main",
                "vllm-reasoning-32b",
                "vllm-fast-14b",
                "ollama-embed",
                "open-webui-main",
                "internalcmdb-api",
                "internalcmdb-worker",
                "internalcmdb-frontend",
                "internalcmdb-scheduler",
            ]
        ]

        if stale_codes:
            # Check remaining instances
            remaining = conn.execute(
                sa.text(
                    "SELECT ss.service_code, count(si.service_instance_id) "
                    "FROM registry.shared_service ss "
                    "LEFT JOIN registry.service_instance si "
                    "  ON si.shared_service_id = ss.shared_service_id "
                    "WHERE ss.service_code = ANY(:codes) "
                    "GROUP BY ss.service_code "
                    "HAVING count(si.service_instance_id) > 0"
                ),
                {"codes": stale_codes},
            ).fetchall()

            if remaining:
                blocked = {r[0] for r in remaining}
                print(f"Cannot delete (still have instances): {list(blocked)}")
                stale_codes = [c for c in stale_codes if c not in blocked]

        if stale_codes:
            # Delete service_dependency rows referencing stale services (as source)
            stale_ids = [code_to_id[c] for c in stale_codes]
            conn.execute(
                sa.text(
                    "DELETE FROM registry.service_dependency "
                    "WHERE source_service_instance_id IN ("
                    "  SELECT service_instance_id FROM registry.service_instance "
                    "  WHERE shared_service_id = ANY(:ids)"
                    ")"
                ),
                {"ids": stale_ids},
            )

            r = conn.execute(
                sa.text("DELETE FROM registry.shared_service WHERE service_code = ANY(:codes)"),
                {"codes": stale_codes},
            )
            print(f"Deleted {r.rowcount} stale entries: {stale_codes}")
        else:
            print("No stale entries to delete.")

        conn.commit()

    engine.dispose()
    print("Done.")


if __name__ == "__main__":
    main()
