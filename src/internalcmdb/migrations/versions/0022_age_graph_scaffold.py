"""Apache AGE graph scaffold — optional extension with relational fallback (F5.2).

Revision ID: 0022
Revises: 0021
Created: 2026-07-05

Optional AGE extension install (requires superuser, run manually if desired)::

    CREATE EXTENSION IF NOT EXISTS age;
    LOAD 'age';
    SET search_path = ag_catalog, "$user", public;

When AGE is unavailable, ``registry.graph_vertex`` and ``registry.graph_edge``
provide a relational fallback for blast-radius queries via ``age_backend.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REGISTRY = "registry"
_GOVERNANCE = "governance"


def upgrade() -> None:
    # Best-effort AGE extension — skipped when not installed (non-superuser CI)
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                CREATE EXTENSION IF NOT EXISTS age;
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE NOTICE 'AGE extension skipped: insufficient privileges';
                WHEN undefined_file THEN
                    RAISE NOTICE 'AGE extension skipped: not installed on this PostgreSQL';
            END $$;
            """
        )
    )

    op.execute(
        sa.text(f"""
            CREATE TABLE IF NOT EXISTS {_REGISTRY}.graph_vertex (
                vertex_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_id       UUID NOT NULL,
                entity_kind     TEXT NOT NULL,
                label           TEXT,
                properties_jsonb JSONB,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                is_active       BOOLEAN NOT NULL DEFAULT true
            )
        """)
    )

    op.execute(
        sa.text(f"""
            CREATE TABLE IF NOT EXISTS {_REGISTRY}.graph_edge (
                edge_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_vertex_id UUID NOT NULL REFERENCES {_REGISTRY}.graph_vertex(vertex_id),
                target_vertex_id UUID NOT NULL REFERENCES {_REGISTRY}.graph_vertex(vertex_id),
                relationship_type TEXT NOT NULL,
                weight          DOUBLE PRECISION DEFAULT 1.0,
                properties_jsonb JSONB,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                is_active       BOOLEAN NOT NULL DEFAULT true
            )
        """)
    )

    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_graph_vertex_entity "
            f"ON {_REGISTRY}.graph_vertex (entity_id) WHERE is_active = true"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_graph_edge_source "
            f"ON {_REGISTRY}.graph_edge (source_vertex_id) WHERE is_active = true"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_graph_edge_target "
            f"ON {_REGISTRY}.graph_edge (target_vertex_id) WHERE is_active = true"
        )
    )

    # Governance-as-code hash-chain audit trail (F5.3)
    op.execute(
        sa.text(f"""
            CREATE TABLE IF NOT EXISTS {_GOVERNANCE}.policy_audit_chain (
                record_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                sequence_num    BIGINT NOT NULL,
                action_jsonb    JSONB NOT NULL,
                decision        TEXT NOT NULL,
                policy_codes    TEXT[] NOT NULL DEFAULT '{{}}',
                record_hash     TEXT NOT NULL,
                prev_hash       TEXT,
                signature       TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT uq_policy_audit_sequence UNIQUE (sequence_num)
            )
        """)
    )

    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_policy_audit_created "
            f"ON {_GOVERNANCE}.policy_audit_chain (created_at DESC)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_GOVERNANCE}.policy_audit_chain CASCADE"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_REGISTRY}.graph_edge CASCADE"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_REGISTRY}.graph_vertex CASCADE"))
