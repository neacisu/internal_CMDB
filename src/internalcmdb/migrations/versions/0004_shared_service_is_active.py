"""Add is_active to registry.shared_service.

Revision ID: 0004
Revises: 0003
Created: 2026-03-14
"""
# pylint: disable=invalid-name,no-member

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(  # pylint: disable=no-member
        "shared_service",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        schema="registry",
    )


def downgrade() -> None:
    op.drop_column("shared_service", "is_active", schema="registry")  # pylint: disable=no-member
