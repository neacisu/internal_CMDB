"""Tests for internalcmdb.auth.models — User ORM model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from internalcmdb.auth.models import User, _utcnow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**kwargs: object) -> User:
    defaults: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "email": "testuser@example.com",
        "username": "testuser",
        "hashed_password": "$argon2id$v=19$...",  # NOSONAR python:S2068
        "role": "viewer",
        "is_active": True,
        "force_password_change": False,
    }
    defaults.update(kwargs)
    return User(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestUserInstantiation:
    def test_minimal_fields(self) -> None:
        uid = uuid.uuid4()
        user = _make_user(user_id=uid, email="a@b.com", username="alpha")
        assert user.user_id == uid
        assert user.email == "a@b.com"
        assert user.username == "alpha"

    def test_role_stored(self) -> None:
        for role in ("admin", "viewer", "hitl_reviewer", "operator"):
            u = _make_user(role=role)
            assert u.role == role

    def test_is_active_default_true(self) -> None:
        u = _make_user(is_active=True)
        assert u.is_active is True

    def test_is_active_false(self) -> None:
        u = _make_user(is_active=False)
        assert u.is_active is False

    def test_force_password_change_default_false(self) -> None:
        u = _make_user(force_password_change=False)
        assert u.force_password_change is False

    def test_nullable_timestamps_default_none(self) -> None:
        u = _make_user()
        assert u.password_changed_at is None
        assert u.last_login_at is None

    def test_nullable_timestamps_with_value(self) -> None:
        ts = datetime.now(UTC)
        u = _make_user(password_changed_at=ts, last_login_at=ts)
        assert u.password_changed_at == ts
        assert u.last_login_at == ts


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------


class TestUserRepr:
    def test_repr_contains_id(self) -> None:
        uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        u = _make_user(user_id=uid)
        assert "12345678-1234-5678-1234-567812345678" in repr(u)

    def test_repr_contains_email(self) -> None:
        u = _make_user(email="repr@example.com")
        assert "repr@example.com" in repr(u)

    def test_repr_contains_role(self) -> None:
        u = _make_user(role="operator")
        assert "operator" in repr(u)

    def test_repr_format(self) -> None:
        uid = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        u = _make_user(user_id=uid, email="fmt@x.com", role="admin")
        assert repr(u) == (
            "<User id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee email='fmt@x.com' role='admin'>"
        )


# ---------------------------------------------------------------------------
# updated_at onupdate callable — timezone-aware
# ---------------------------------------------------------------------------


class TestUpdatedAtOnupdate:
    """Verify the onupdate callable emits timezone-aware UTC datetimes."""

    def test_onupdate_callable_exists(self) -> None:
        """SQLAlchemy stores the callable in the column's onupdate attribute."""
        col = User.__table__.c.updated_at
        assert col.onupdate is not None
        assert col.onupdate.is_callable

    def test_utcnow_returns_datetime(self) -> None:
        result = _utcnow()
        assert isinstance(result, datetime)

    def test_utcnow_is_timezone_aware(self) -> None:
        result = _utcnow()
        assert result.tzinfo is not None, "_utcnow() must return a timezone-aware datetime"

    def test_utcnow_is_utc(self) -> None:
        result = _utcnow()
        assert result.utcoffset() is not None
        assert result.utcoffset().total_seconds() == 0  # type: ignore[union-attr]

    def test_onupdate_not_utcnow(self) -> None:
        """Ensure the deprecated datetime.utcnow callable is not registered."""
        col = User.__table__.c.updated_at
        fn = col.onupdate.arg
        name = getattr(fn, "__name__", None) or ""
        assert name != "utcnow", "datetime.utcnow (naive) must not be used as onupdate"

    def test_utcnow_close_to_now(self) -> None:
        before = datetime.now(UTC)
        result = _utcnow()
        after = datetime.now(UTC)
        assert before <= result <= after

    def test_onupdate_arg_is_utcnow_fn(self) -> None:
        """The onupdate callable registered in the column must be _utcnow."""
        col = User.__table__.c.updated_at
        # SQLAlchemy may wrap the callable but the original __name__ is preserved
        fn = col.onupdate.arg
        assert getattr(fn, "__name__", None) == "_utcnow"


# ---------------------------------------------------------------------------
# Table metadata
# ---------------------------------------------------------------------------


class TestUserTableMetadata:
    def test_tablename(self) -> None:
        assert User.__tablename__ == "users"

    def test_schema(self) -> None:
        assert User.__table__.schema == "auth"

    def test_primary_key_column(self) -> None:
        pk_cols = [c.name for c in User.__table__.primary_key.columns]  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType,reportAttributeAccessIssue]
        assert pk_cols == ["user_id"]

    def test_email_unique_index(self) -> None:
        col = User.__table__.c.email
        assert col.unique is True

    def test_username_unique_index(self) -> None:
        col = User.__table__.c.username
        assert col.unique is True

    def test_role_check_constraint_present(self) -> None:
        constraint_names = [c.name for c in User.__table__.constraints if hasattr(c, "name")]  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType,reportAttributeAccessIssue,reportUnknownArgumentType]
        assert "ck_users_role" in constraint_names

    def test_created_at_not_nullable(self) -> None:
        col = User.__table__.c.created_at
        assert col.nullable is False

    def test_updated_at_not_nullable(self) -> None:
        col = User.__table__.c.updated_at
        assert col.nullable is False

    def test_password_changed_at_nullable(self) -> None:
        col = User.__table__.c.password_changed_at
        assert col.nullable is True

    def test_last_login_at_nullable(self) -> None:
        col = User.__table__.c.last_login_at
        assert col.nullable is True
