"""Deactivate dev bootstrap token; prod token inserted via scripts/rotate_bootstrap_token.sh.

Revision ID: 0024
Revises: 0023
Created: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE discovery.bootstrap_tokens
               SET is_active = false
             WHERE label = 'dev-bootstrap'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE discovery.bootstrap_tokens
               SET is_active = true
             WHERE label = 'dev-bootstrap'
            """
        )
    )
