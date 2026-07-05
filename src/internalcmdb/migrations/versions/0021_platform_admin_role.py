"""Add platform_admin to auth.users role check constraint.

Revision ID: 0021
Revises: 0020
Created: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_users_role", "users", schema="auth", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin', 'operator', 'viewer', 'hitl_reviewer', 'platform_admin')",
        schema="auth",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", schema="auth", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin', 'operator', 'viewer', 'hitl_reviewer')",
        schema="auth",
    )
