#!/usr/bin/env python3
"""Export agent-host-map.csv from Postgres + deploy_agent.sh HOST_SSH."""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "rollout" / "agent-host-map.csv"

HOST_SSH = {
    "orchestrator": "orchestrator",
    "postgres-main": "postgres-main",
    "imac": "imac",
    "hz.62": "hz.62",
    "hz.113": "hz.113",
    "hz.118": "hz.118",
    "lxc-hz118-traktors": "hz.118.lxc.100",
    "lxc-hz118-tecdocnode": "hz.118.lxc.101",
    "lxc-hz118-tecdocmysql": "hz.118.lxc.102",
    "lxc-hz118-mediserver2": "hz.118.lxc.103",
    "hz.123": "hz.123",
    "hz.157": "hz.157",
    "hz.164": "hz.164",
    "hz.215": "hz.215",
    "hz.223": "hz.223",
    "hz.247": "hz.247",
    "lxc-llm-guard": "lxc-llm-guard",
    "lxc-wapp-pro-app": "wapp-pro-app",
    "lxc-postgres-main": "lxc-postgres-main",
    "lxc-ci-worker": "lxc-ci-worker",
    "lxc-neanelu-prod": "lxc-neanelu-prod",
    "lxc-neanelu-staging": "lxc-neanelu-staging",
    "lxc-prod-cerniq": "lxc-prod-cerniq",
    "lxc-staging-cerniq": "lxc-staging-cerniq",
}


def main() -> None:
    from sqlalchemy import create_engine, text

    env_path = REPO / ".env"
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    url = (
        f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:"
        f"{os.environ['POSTGRES_PASSWORD']}@"
        f"{os.environ.get('POSTGRES_SYNC_HOST', '127.0.0.1')}:"
        f"{os.environ.get('POSTGRES_SYNC_PORT', '5433')}/"
        f"{os.environ['POSTGRES_DB']}"
    )
    engine = create_engine(url)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    with engine.connect() as conn, OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "agent_uuid",
                "hostname",
                "ssh_alias",
                "host_code",
                "toml_path",
                "in_deploy_script",
                "ssh_ok",
                "token_hash",
                "status",
            ]
        )
        rows = conn.execute(
            text(
                """
                SELECT agent_id::text, host_code, token_hash IS NOT NULL AS has_token
                FROM discovery.collector_agent
                WHERE is_active
                ORDER BY host_code
                """
            )
        ).all()
        for agent_id, host_code, has_token in rows:
            alias = HOST_SSH.get(host_code, host_code)
            in_deploy = "yes" if host_code in HOST_SSH else "no"
            toml = f"deploy/configs/agents/{host_code.replace('.', '-')}.toml"
            w.writerow(
                [
                    agent_id,
                    host_code,
                    alias,
                    host_code,
                    toml,
                    in_deploy,
                    "",
                    "yes" if has_token else "no",
                    "done" if has_token else "pending",
                ]
            )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
