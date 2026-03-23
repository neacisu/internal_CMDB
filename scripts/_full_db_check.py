"""Full DB state check — all shared services with their metadata status."""

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
            "SELECT service_code, name, "
            "(SELECT count(*) FROM jsonb_object_keys(metadata_jsonb)) as key_count, "
            "metadata_jsonb->>'category' as category "
            "FROM registry.shared_service ORDER BY service_code"
        )
    ).fetchall()
    print(f"Total: {len(rows)} services\n")
    for r in rows:
        cat = r[3] or "(none)"
        print(f"  {r[0]:35s}  keys={r[2]:2d}  cat={cat:20s}  {r[1]}")

    print("\n--- AI/ML detailed ---")
    AI_CODES = (
        "'vllm-fast-14b','vllm-reasoning-32b','ollama-embed','open-webui-main'"
    )
    ai = c.execute(
        sa.text(
            "SELECT service_code, name, description, metadata_jsonb "
            "FROM registry.shared_service "
            "WHERE metadata_jsonb->>'category' = 'ai_ml' "
            f"OR service_code IN ({AI_CODES}) "
            "ORDER BY service_code"
        )
    ).fetchall()
    for r in ai:
        raw = r[3]
        if isinstance(raw, dict):
            meta: dict[str, object] = dict(raw)  # type: ignore[arg-type]
        elif raw:
            meta = json.loads(raw)
        else:
            meta = {}
        print(f"\n  [{r[0]}] {r[1]}")
        print(f"    desc: {(r[2] or 'N/A')[:150]}")
        print(f"    category: {meta.get('category', 'NONE')}")
        if "hf_repo" in meta:
            print(f"    hf_repo: {meta['hf_repo']}")
        if "vram_fraction" in meta:
            print(f"    vram_fraction: {meta['vram_fraction']}")
