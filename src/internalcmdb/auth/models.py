"""ORM model for auth.users table."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware).

    Used as the ``onupdate`` callable for ``updated_at`` columns so that
    SQLAlchemy injects a timezone-aware timestamp on every UPDATE — consistent
    with the project-wide ``datetime.now(UTC)`` convention.
    """
    return datetime.now(UTC)


class AuthBase(DeclarativeBase):
    """Separate declarative base scoped to the auth schema."""

    __abstract__ = True


class User(AuthBase):
    """Local user account — stored in auth.users PostgreSQL table."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','viewer','hitl_reviewer','operator')",
            name="ck_users_role",
        ),
        {"schema": "auth"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        unique=True,
        index=True,
    )
    username: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    force_password_change: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=_utcnow,
    )

    def __repr__(self) -> str:
        return f"<User id={self.user_id!s} email={self.email!r} role={self.role!r}>"
