"""Add agent token_hash and bootstrap_tokens for zero-trust enrollment.

Revision ID: 0020
Revises: 0019
Created: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collector_agent",
        sa.Column("token_hash", sa.Text(), nullable=True),
        schema="discovery",
    )

    op.create_table(
        "bootstrap_tokens",
        sa.Column(
            "token_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("token_id", name="pk_bootstrap_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_bootstrap_tokens_hash"),
        schema="discovery",
    )

    # Seed a development bootstrap token — rotate in production.
    import hashlib  # noqa: PLC0415

    dev_hash = hashlib.sha256(b"bootstrap-dev-token-change-me").hexdigest()
    op.execute(
        sa.text(
            """
            INSERT INTO discovery.bootstrap_tokens (token_hash, label, is_active)
            VALUES (:token_hash, 'dev-bootstrap', true)
            ON CONFLICT (token_hash) DO NOTHING
            """
        ).bindparams(token_hash=dev_hash)
    )


def downgrade() -> None:
    op.drop_table("bootstrap_tokens", schema="discovery")
    op.drop_column("collector_agent", "token_hash", schema="discovery")
