"""Tests for internalcmdb.governance.access_control (pt-057).

Covers DATA-001 Class B access enforcement:
- Class A tables: unrestricted access regardless of caller roles
- Class B tables: denied without platform_engineering role
- Class B tables: permitted with platform_engineering role
- Denied access records a ChangeLog entry and raises AccessDeniedError
- AccessDeniedError carries correct metadata
"""

from __future__ import annotations

# pylint: disable=redefined-outer-name
from typing import ClassVar
from unittest.mock import MagicMock

import pytest

from internalcmdb.governance.access_control import (  # pylint: disable=import-error
    _CLASS_B_TABLES,
    AccessDeniedError,
    CallerContext,
    DataAccessControl,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    return session


@pytest.fixture
def dac(mock_session: MagicMock) -> DataAccessControl:
    return DataAccessControl(mock_session)


def _ctx(roles: set[str] | None = None, caller_id: str = "agent-test") -> CallerContext:
    return CallerContext(caller_id=caller_id, roles=frozenset(roles or set()))


# ---------------------------------------------------------------------------
# Class A tables — unrestricted
# ---------------------------------------------------------------------------


class TestClassATables:
    _CLASS_A_EXAMPLES: ClassVar[list[str]] = [
        "registry_host",
        "registry_service",
        "registry_application",
        "taxonomy_term",
        "taxonomy_domain",
        "document",
        "host_interface",
        "observed_metric",
    ]

    @pytest.mark.parametrize("table", _CLASS_A_EXAMPLES)
    def test_class_a_always_allowed(self, dac: DataAccessControl, table: str) -> None:
        # No role, no session interaction — must not raise
        ctx = _ctx(roles=set())
        dac.assert_read_allowed(table, ctx)

    @pytest.mark.parametrize("table", _CLASS_A_EXAMPLES)
    def test_class_a_does_not_write_changelog(
        self, dac: DataAccessControl, mock_session: MagicMock, table: str
    ) -> None:
        ctx = _ctx(roles=set())
        dac.assert_read_allowed(table, ctx)
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_called()


# ---------------------------------------------------------------------------
# Class B tables — access control enforcement
# ---------------------------------------------------------------------------


class TestClassBTablesAllowed:
    @pytest.mark.parametrize("table", sorted(_CLASS_B_TABLES))
    def test_allowed_with_platform_engineering(self, dac: DataAccessControl, table: str) -> None:
        ctx = _ctx(roles={"platform_engineering"})
        # Must not raise
        dac.assert_read_allowed(table, ctx)

    @pytest.mark.parametrize("table", sorted(_CLASS_B_TABLES))
    def test_allowed_with_platform_engineering_plus_extras(
        self, dac: DataAccessControl, table: str
    ) -> None:
        ctx = _ctx(roles={"platform_engineering", "other_role", "admin"})
        dac.assert_read_allowed(table, ctx)


class TestClassBTablesDenied:
    @pytest.mark.parametrize("table", sorted(_CLASS_B_TABLES))
    def test_denied_without_any_role(self, dac: DataAccessControl, table: str) -> None:
        ctx = _ctx(roles=set())
        with pytest.raises(AccessDeniedError):
            dac.assert_read_allowed(table, ctx)

    @pytest.mark.parametrize("table", sorted(_CLASS_B_TABLES))
    def test_denied_with_wrong_role(self, dac: DataAccessControl, table: str) -> None:
        ctx = _ctx(roles={"viewer", "operator"})
        with pytest.raises(AccessDeniedError):
            dac.assert_read_allowed(table, ctx)

    @pytest.mark.parametrize("table", sorted(_CLASS_B_TABLES))
    def test_denial_writes_changelog(
        self, dac: DataAccessControl, mock_session: MagicMock, table: str
    ) -> None:
        ctx = _ctx(roles=set())
        with pytest.raises(AccessDeniedError):
            dac.assert_read_allowed(table, ctx)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_denial_on_observed_fact_has_correct_metadata(self, dac: DataAccessControl) -> None:
        ctx = _ctx(caller_id="rogue-agent", roles=set())
        with pytest.raises(AccessDeniedError) as exc_info:
            dac.assert_read_allowed("observed_fact", ctx)
        err = exc_info.value
        assert err.caller_id == "rogue-agent"
        assert err.table == "observed_fact"
        assert err.required_role == "platform_engineering"

    def test_error_message_contains_relevant_info(self, dac: DataAccessControl) -> None:
        ctx = _ctx(caller_id="bad-actor", roles=set())
        with pytest.raises(AccessDeniedError) as exc_info:
            dac.assert_read_allowed("agent_run", ctx)
        message = str(exc_info.value)
        assert "bad-actor" in message
        assert "agent_run" in message
        assert "platform_engineering" in message


# ---------------------------------------------------------------------------
# CallerContext
# ---------------------------------------------------------------------------


class TestCallerContext:
    def test_frozen_dataclass(self) -> None:
        ctx = CallerContext(caller_id="x", roles=frozenset({"r"}))
        with pytest.raises((AttributeError, TypeError)):
            ctx.caller_id = "y"  # type: ignore[misc]

    def test_default_roles_empty(self) -> None:
        ctx = CallerContext(caller_id="x")
        assert ctx.roles == frozenset()

    def test_roles_immutable(self) -> None:
        ctx = CallerContext(caller_id="x", roles=frozenset({"r"}))
        assert isinstance(ctx.roles, frozenset)


# ---------------------------------------------------------------------------
# Class B table membership
# ---------------------------------------------------------------------------


class TestClassBTableSet:
    def test_all_expected_tables_classified_b(self) -> None:
        expected = {
            "observed_fact",
            "chunk_embedding",
            "document_chunk",
            "evidence_pack",
            "evidence_pack_item",
            "agent_run",
            "action_request",
            "prompt_template_registry",
            "change_log",
            "document_version",
        }
        assert expected == _CLASS_B_TABLES

    def test_count_of_class_b_tables(self) -> None:
        assert len(_CLASS_B_TABLES) == 10
