"""Alembic migration environment for internalCMDB.

Connection URL is assembled from environment variables so that no
credentials ever appear in version-controlled files.

Required env vars (loaded from .env by the caller or the shell):
    POSTGRES_HOST       - hostname or IP (default: localhost)
    POSTGRES_PORT       - TCP port     (default: 5433)
    POSTGRES_DB         - database name (default: internalCMDB)
    POSTGRES_USER       - role name    (default: internalcmdb)
    POSTGRES_PASSWORD   - password     (required, no default)
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from urllib.parse import quote_plus

import sqlalchemy as sa
from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Assemble DSN from env vars
# ---------------------------------------------------------------------------


def _build_url() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5433")
    db = os.environ.get("POSTGRES_DB", "internalCMDB")
    user = os.environ.get("POSTGRES_USER", "internalcmdb")
    pw = os.environ.get("POSTGRES_PASSWORD", "")
    sslmode = os.environ.get("POSTGRES_SSLMODE", "prefer")
    if not pw:
        raise RuntimeError(
            "POSTGRES_PASSWORD env var is not set. Load your .env file before running alembic."
        )
    return f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(pw)}@{host}:{port}/{db}?sslmode={sslmode}"


# ---------------------------------------------------------------------------
# Alembic boilerplate
# ---------------------------------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so autogenerate can detect schema drift.
from internalcmdb.models import metadata as target_metadata  # noqa: E402

_url = _build_url()
config.set_main_option("sqlalchemy.url", _url)


def run_migrations_offline() -> None:
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="governance",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Ensure all schemas exist before Alembic touches the version table.
        for schema in (
            "taxonomy",
            "docs",
            "discovery",
            "governance",
            "registry",
            "retrieval",
            "agent_control",
        ):
            connection.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="governance",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
