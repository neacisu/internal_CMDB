"""Check AI/ML services in DB."""

import json
import os

import sqlalchemy as sa
from dotenv import load_dotenv

load_dotenv()

_port = os.environ.get("POSTGRES_PORT", "5432")
url = (
    f"postgresql+psycopg://{os.environ['POSTGRES_USER']}"
    f":{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{_port}"
    f"/{os.environ['POSTGRES_DB']}"
)
e = sa.create_engine(url)
with e.connect() as c:
    rows = c.execute(
        sa.text(
            "SELECT service_code, name, metadata_jsonb->>'category' as cat "
            "FROM registry.shared_service "
            "WHERE metadata_jsonb->>'category' = 'ai_ml' "
            "ORDER BY service_code"
        )
    ).fetchall()
    print(f"AI/ML services: {len(rows)}")
    for r in rows:
        print(f"  {r[0]:25s}  {r[1]}")
    print()
    # Check vllm details
    codes = [
        "vllm-reasoning-32b",
        "vllm-fast-14b",
        "ollama-embed",
        "open-webui-main",
    ]
    for code in codes:
        row = c.execute(
            sa.text(
                "SELECT service_code, name, description, metadata_jsonb "
                "FROM registry.shared_service WHERE service_code = :sc"
            ),
            {"sc": code},
        ).fetchone()
        if row:
            raw = row[3]
            if isinstance(raw, dict):
                meta: dict[str, object] = dict(raw)  # type: ignore[arg-type]
            elif raw:
                meta = json.loads(raw)
            else:
                meta = {}
            print(f"[{row[0]}] name='{row[1]}'")
            print(f"  desc: {row[2][:120] if row[2] else 'N/A'}...")
            print(f"  meta keys: {list(meta.keys())}")
            if "hf_repo" in meta:
                print(f"  hf_repo: {meta['hf_repo']}")
            if "vram_fraction" in meta:
                print(f"  vram_fraction: {meta['vram_fraction']}")
            print()
        else:
            print(f"[{code}] NOT FOUND in DB")
            print()
