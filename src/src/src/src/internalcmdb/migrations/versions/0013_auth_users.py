"""Create auth schema and auth.users table.

Revision ID: 0013
Revises: 0012
Created: 2026-04-05

Introduces the standalone auth module:
  - ``auth`` PostgreSQL schema
  - ``auth.users`` table (local accounts, argon2id hashed passwords)
  - Seed admin: alex@neanelu.ro / Admin1234% (force_password_change=true)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Pre-generated argon2id hash for Admin1234% — regenerate if rotating seed.
# python3 -c "from argon2 import PasswordHasher; \
#   ph=PasswordHasher(time_cost=2,memory_cost=65536,parallelism=2,hash_len=32,salt_len=16); \
#   print(ph.hash('Admin1234%'))"
_SEED_HASH = (
    "$argon2id$v=19$m=65536,t=2,p=2"
    "$5vB39ZDRr0lhI8ltMQfwZA"
    "$ooWCb+LGeiBglM8SAju7yq6r5i8HlGCv3iaBGjyUL54"
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    # Grant the application DB user access to the auth schema.
    op.execute("GRANT USAGE ON SCHEMA auth TO internalcmdb")

    op.create_table(
        "users",
        sa.Column(
            "user_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.VARCHAR(256), nullable=False),
        sa.Column("username", sa.VARCHAR(128), nullable=False),
        sa.Column("hashed_password", sa.TEXT(), nullable=False),
        sa.Column("role", sa.TEXT(), nullable=False),
        sa.Column("is_active", sa.BOOLEAN(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "force_password_change",
            sa.BOOLEAN(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("password_changed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'operator', 'viewer', 'hitl_reviewer')",
            name="ck_users_role",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_auth_users"),
        sa.UniqueConstraint("email", name="uq_auth_users_email"),
        sa.UniqueConstraint("username", name="uq_auth_users_username"),
        schema="auth",
    )

    # Seed the initial admin account (force_password_change=true).
    op.execute(
        sa.text(
            """
            INSERT INTO auth.users
                (email, username, hashed_password, role,
                 is_active, force_password_change)
            VALUES
                (:email, :username, :hashed_password, 'admin', true, true)
            ON CONFLICT (email) DO NOTHING
            """
        ).bindparams(
            email="alex@neanelu.ro",
            username="alex",
            hashed_password=_SEED_HASH,
        )
    )


def downgrade() -> None:
    op.drop_table("users", schema="auth")
    op.execute("DROP SCHEMA IF EXISTS auth CASCADE")
