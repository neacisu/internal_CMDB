"""Full DB summary: all shared services with metadata key counts."""

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
            "(SELECT count(*) FROM jsonb_object_keys(metadata_jsonb)) as key_count "
            "FROM registry.shared_service ORDER BY service_code"
        )
    ).fetchall()
    total = len(rows)
    zero = sum(1 for r in rows if r[2] == 0)
    print(f"Total: {total} services, {zero} with 0 metadata keys\n")
    for r in rows:
        print(f"  {r[0]:30s}  {r[2]:2d} keys  {r[1]}")
