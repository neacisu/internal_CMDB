"""Quick check: do the 4 former-orphan services now have metadata?"""

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
            "metadata_jsonb::text "
            "FROM registry.shared_service "
            "WHERE service_code IN ('activepieces','kafka','n8n','neo4j') "
            "ORDER BY service_code"
        )
    ).fetchall()
    for r in rows:
        meta = json.loads(r[3]) if r[3] else {}
        print(f"{r[0]:20s}  name={r[1]:40s}  keys={r[2]}  meta_keys={list(meta.keys())}")
