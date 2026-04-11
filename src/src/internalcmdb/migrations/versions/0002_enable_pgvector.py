"""Enable pgvector extension and convert embedding_vector column to vector(1536).

Revision ID: 0002
Revises: 0001
Created: companion migration to 0001_wave1_initial_schema

This migration:
  1. Creates the pgvector extension (requires superuser or CREATE EXTENSION privilege).
  2. ALTERs retrieval.chunk_embedding.embedding_vector from TEXT to vector(1536).

Prerequisites:
  - Migration 0001 must already be applied.
  - The PostgreSQL server must have the pgvector extension available
    (``shared_preload_libraries`` or ``pg_extensions`` installed).
  - The executing role must have CREATE EXTENSION privilege on the target database,
    or the extension must already be installed at the server level.

Downgrade notes:
  - ``downgrade()`` converts vector(1536) back to TEXT (lossy — float[] → text).
  - Any pgvector indexes are dropped before the column type change.
"""

# pylint: disable=invalid-name,no-member
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VECTOR_DIM: int = 1536
_SCHEMA = "retrieval"
_TABLE = "chunk_embedding"
_COLUMN = "embedding_vector"
_INDEX_NAME = "ix_chunk_embedding_vector_hnsw"


def upgrade() -> None:
    bind = op.get_bind()

    # ── 0. Check whether pgvector is available on this PostgreSQL server ──────
    # We query pg_available_extensions to avoid attempting CREATE EXTENSION and
    # aborting the transaction when the shared library is not installed.
    result = bind.execute(
        sa.text("SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'")
    )
    pgvector_available: bool = (result.scalar() or 0) > 0

    if not pgvector_available:
        # pgvector is not installed on this server.  Emit a notice so operators
        # know vector search will be unavailable, then skip all vector DDL.
        # The migration revision is still stamped so downstream revisions (e.g.
        # 0003) can apply without being blocked on this optional capability.
        bind.execute(
            sa.text(
                "DO $$ BEGIN "
                "  RAISE NOTICE 'pgvector not available — skipping extension and "
                "  embedding_vector column conversion (revision 0002). "
                "  Install pgvector and run ''alembic downgrade 0001 && alembic upgrade 0002'' "
                "  to enable vector search.'; "
                "END $$"
            )
        )
        return

    # ── 1. Enable pgvector extension ─────────────────────────────────────────
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # ── 2. Drop any existing index on embedding_vector (TEXT has none, but be safe)
    op.execute(sa.text(f"DROP INDEX IF EXISTS {_SCHEMA}.{_INDEX_NAME}"))

    # ── 3. Cast TEXT column to vector(1536) ───────────────────────────────────
    # Rows inserted from 0001 forward have NULL in embedding_vector (TEXT default).
    # The USING clause casts NULL → NULL and a valid text array literal → vector.
    op.execute(
        sa.text(
            f"ALTER TABLE {_SCHEMA}.{_TABLE} "
            f"ALTER COLUMN {_COLUMN} "
            f"TYPE vector({_VECTOR_DIM}) "
            f"USING CASE "
            f"  WHEN {_COLUMN} IS NULL THEN NULL "
            f"  ELSE {_COLUMN}::vector({_VECTOR_DIM}) "
            f"END"
        )
    )

    # ── 4. Create HNSW index for approximate nearest-neighbour queries ────────
    # m=16, ef_construction=64 are conservative defaults; tune as data grows.
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS {_INDEX_NAME} "
            f"ON {_SCHEMA}.{_TABLE} "
            f"USING hnsw ({_COLUMN} vector_cosine_ops) "
            f"WITH (m = 16, ef_construction = 64)"
        )
    )


def downgrade() -> None:
    # ── 1. Drop the HNSW index ────────────────────────────────────────────────
    op.execute(sa.text(f"DROP INDEX IF EXISTS {_SCHEMA}.{_INDEX_NAME}"))

    # ── 2. Cast vector(1536) back to TEXT (lossy) ────────────────────────────
    op.execute(
        sa.text(
            f"ALTER TABLE {_SCHEMA}.{_TABLE} "
            f"ALTER COLUMN {_COLUMN} "
            f"TYPE TEXT "
            f"USING CASE "
            f"  WHEN {_COLUMN} IS NULL THEN NULL "
            f"  ELSE {_COLUMN}::text "
            f"END"
        )
    )

    # Note: we do NOT drop the pgvector extension on downgrade because other
    # objects or schemas might depend on it.  Uninstalling it would require
    # explicit operator action:  DROP EXTENSION vector CASCADE;
