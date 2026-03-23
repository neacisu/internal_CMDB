"""Knowledge graph — ci_relationship table for entity-to-entity links.

Revision ID: 0009
Revises: 0008
Created: 2026-03-22

This migration creates:
  registry.ci_relationship — generic relationship table between any CMDB entities,
  enabling the knowledge graph to discover and track inter-entity links beyond
  the existing service_dependency table.
"""

# pylint: disable=invalid-name,no-member
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REGISTRY = "registry"


def upgrade() -> None:
    op.execute(
        sa.text(f"""
            CREATE TABLE {_REGISTRY}.ci_relationship (
                relationship_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_entity_kind  TEXT NOT NULL,
                source_entity_id    UUID NOT NULL,
                target_entity_kind  TEXT NOT NULL,
                target_entity_id    UUID NOT NULL,
                relationship_type   TEXT NOT NULL,
                confidence          DOUBLE PRECISION DEFAULT 1.0,
                discovered_by       TEXT,
                metadata_jsonb      JSONB,
                discovered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_verified_at    TIMESTAMPTZ,
                is_active           BOOLEAN NOT NULL DEFAULT true
            )
        """)
    )

    op.execute(
        sa.text(
            f"CREATE INDEX idx_ci_rel_source "
            f"ON {_REGISTRY}.ci_relationship (source_entity_id)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX idx_ci_rel_target "
            f"ON {_REGISTRY}.ci_relationship (target_entity_id)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX idx_ci_rel_type "
            f"ON {_REGISTRY}.ci_relationship (relationship_type)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX idx_ci_rel_active "
            f"ON {_REGISTRY}.ci_relationship (is_active) WHERE is_active = true"
        )
    )

    # Prevent duplicate relationships between the same entities
    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS ux_ci_rel_dedup "
            f"ON {_REGISTRY}.ci_relationship "
            f"(source_entity_id, target_entity_id, relationship_type) "
            f"WHERE is_active = true"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_REGISTRY}.ci_relationship CASCADE"))
