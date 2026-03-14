"""Check orphan service instances."""

import os

import sqlalchemy as sa
from dotenv import load_dotenv

load_dotenv()
url = (
    f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:"
    f"{os.environ['POSTGRES_PASSWORD']}@{os.environ['POSTGRES_HOST']}:"
    f"{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ['POSTGRES_DB']}"
)
e = sa.create_engine(url)
with e.connect() as c:
    rows = c.execute(
        sa.text(
            "SELECT ss.service_code, si.instance_name, si.container_name, "
            "si.image_reference, si.status_text "
            "FROM registry.shared_service ss "
            "JOIN registry.service_instance si ON si.shared_service_id = ss.shared_service_id "
            "WHERE ss.service_code IN ('activepieces','kafka','n8n','neo4j') "
            "ORDER BY ss.service_code, si.instance_name"
        )
    ).fetchall()
    for r in rows:
        print(f"{r[0]:15s} inst={r[1]!s:30s} container={r[2]!s:20s} img={r[3]!s:50s} status={r[4]}")
e.dispose()
