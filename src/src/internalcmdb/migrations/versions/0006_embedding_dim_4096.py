"""Upgrade embedding_vector column from vector(1536) to vector(4096).

Revision ID: 0006
Revises: 0005
Created: 2026-03-22

This migration:
  1. Drops the existing HNSW index on retrieval.chunk_embedding.embedding_vector.
  2. ALTERs the column type from vector(1536) to vector(4096).
  3. Truncates existing embeddings (they must be re-generated with the new model
     that produces 4096-dim vectors — Qwen3-Embedding-8B).
  4. Recreates the HNSW index with ef_construction=200 for the larger dimension.

Downgrade:
  - Reverts to vector(1536) and drops/recreates the HNSW index at the old dim.
  - Existing 4096-dim embeddings are truncated (lossy).
"""

# pylint: disable=invalid-name,no-member
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "retrieval"
_TABLE = "chunk_embedding"
_COLUMN = "embedding_vector"
_INDEX_NAME = "ix_chunk_embedding_vector_hnsw"
_OLD_DIM = 1536
_NEW_DIM = 4096


def upgrade() -> None:
    bind = op.get_bind()

    result = bind.execute(
        sa.text("SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'")
    )
    pgvector_available: bool = (result.scalar() or 0) > 0

    if not pgvector_available:
        bind.execute(
            sa.text(
                "DO $$ BEGIN "
                "  RAISE NOTICE 'pgvector not available — skipping embedding dimension "
                "  upgrade (revision 0006).'; "
                "END $$"
            )
        )
        return

    op.execute(sa.text(f"DROP INDEX IF EXISTS {_SCHEMA}.{_INDEX_NAME}"))

    op.execute(sa.text(f"UPDATE {_SCHEMA}.{_TABLE} SET {_COLUMN} = NULL"))

    op.execute(
        sa.text(
            f"ALTER TABLE {_SCHEMA}.{_TABLE} "
            f"ALTER COLUMN {_COLUMN} "
            f"TYPE vector({_NEW_DIM}) "
            f"USING NULL::vector({_NEW_DIM})"
        )
    )

    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS {_INDEX_NAME} "
            f"ON {_SCHEMA}.{_TABLE} "
            f"USING hnsw ({_COLUMN} vector_cosine_ops) "
            f"WITH (m = 16, ef_construction = 200)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {_SCHEMA}.{_INDEX_NAME}"))

    op.execute(sa.text(f"UPDATE {_SCHEMA}.{_TABLE} SET {_COLUMN} = NULL"))

    op.execute(
        sa.text(
            f"ALTER TABLE {_SCHEMA}.{_TABLE} "
            f"ALTER COLUMN {_COLUMN} "
            f"TYPE vector({_OLD_DIM}) "
            f"USING NULL::vector({_OLD_DIM})"
        )
    )

    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS {_INDEX_NAME} "
            f"ON {_SCHEMA}.{_TABLE} "
            f"USING hnsw ({_COLUMN} vector_cosine_ops) "
            f"WITH (m = 16, ef_construction = 64)"
        )
    )
