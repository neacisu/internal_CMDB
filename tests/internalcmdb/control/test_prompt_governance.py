"""Tests for internalcmdb.control.prompt_governance (pt-018).

Covers:
- register: creates new template, success=True
- register: invalid version string (not MAJOR.MINOR.PATCH) → failure
- register: version downgrade (equal) → VERSION_DOWNGRADE error
- register: version downgrade (less than) → VERSION_DOWNGRADE error
- register: upgrade deactivates previous, warns
- get_active: raises KeyError when no active template
- get_active: returns the active row when present
- deactivate: returns True and sets is_active=False
- deactivate: returns False for unknown code
- list_versions: returns rows sorted newest first
- validate_template_text: empty → warning
- validate_template_text: too long → warning
- validate_template_text: unmatched Jinja block → warning
- validate_template_text: clean template → empty list
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from internalcmdb.control.prompt_governance import (  # pylint: disable=import-error
    PromptGovernance,
    TemplateSpec,
    _parse_version,
    validate_template_text,
)
from internalcmdb.models.agent_control import PromptTemplateRegistry  # pylint: disable=import-error
from internalcmdb.retrieval.task_types import TaskTypeCode  # pylint: disable=import-error

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_row(
    code: str = "tmpl-test",
    version: str = "1.0.0",
    is_active: bool = True,
    row_id: uuid.UUID | None = None,
) -> MagicMock:
    row = MagicMock(spec=PromptTemplateRegistry)
    row.prompt_template_registry_id = row_id or uuid.uuid4()
    row.template_code = code
    row.template_version = version
    row.is_active = is_active
    row.task_type_code = "TT-001"
    row.created_at = "2026-01-01T00:00:00+00:00"
    row.policy_record_id = None
    row.document_version_id = None
    return row


def _make_session(existing_active: MagicMock | None = None) -> MagicMock:
    """Build a mock session whose query chain returns *existing_active* (or empty list)."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()

    # Chain: session.query(...).filter(...).limit(1).all()
    query_mock = MagicMock()
    filter_mock = MagicMock()
    limit_mock = MagicMock()
    limit_mock.all.return_value = [existing_active] if existing_active is not None else []
    filter_mock.limit.return_value = limit_mock
    query_mock.filter.return_value = filter_mock
    session.query.return_value = query_mock

    return session


def _spec(
    code: str = "tmpl-test",
    version: str = "1.0.0",
    text: str = "You are a helpful assistant.",
) -> TemplateSpec:
    return TemplateSpec(
        template_code=code,
        task_type_code=TaskTypeCode.INFRASTRUCTURE_AUDIT,
        template_version=version,
        template_text=text,
    )


# ---------------------------------------------------------------------------
# register — new template (no existing)
# ---------------------------------------------------------------------------


class TestRegisterNew:
    def test_success_true_for_new_template(self) -> None:
        session = _make_session(existing_active=None)
        pg = PromptGovernance(session)
        result = pg.register(_spec())
        assert result.success is True

    def test_session_add_called(self) -> None:
        session = _make_session(existing_active=None)
        pg = PromptGovernance(session)
        pg.register(_spec())
        session.add.assert_called_once()

    def test_session_flush_called(self) -> None:
        session = _make_session(existing_active=None)
        pg = PromptGovernance(session)
        pg.register(_spec())
        session.flush.assert_called_once()

    def test_no_warnings_for_fresh_registration(self) -> None:
        session = _make_session(existing_active=None)
        pg = PromptGovernance(session)
        result = pg.register(_spec())
        assert result.warnings == []

    def test_errors_empty_on_success(self) -> None:
        session = _make_session(existing_active=None)
        pg = PromptGovernance(session)
        result = pg.register(_spec())
        assert result.errors == []


# ---------------------------------------------------------------------------
# register — invalid version string
# ---------------------------------------------------------------------------


class TestRegisterInvalidVersion:
    @pytest.mark.parametrize(
        "bad_version",
        ["1.0", "v1.0.0", "1.0.0.0", "latest", "", "1.x.0", "1.0.0-alpha"],
    )
    def test_invalid_version_returns_failure(self, bad_version: str) -> None:
        session = _make_session(existing_active=None)
        pg = PromptGovernance(session)
        result = pg.register(_spec(version=bad_version))
        assert result.success is False
        assert len(result.errors) > 0

    def test_session_add_not_called_on_bad_version(self) -> None:
        session = _make_session(existing_active=None)
        pg = PromptGovernance(session)
        pg.register(_spec(version="invalid"))
        session.add.assert_not_called()


# ---------------------------------------------------------------------------
# register — version downgrade prevention
# ---------------------------------------------------------------------------


class TestRegisterVersionDowngrade:
    def test_same_version_rejected(self) -> None:
        existing = _make_registry_row(version="1.2.0")
        session = _make_session(existing_active=existing)
        pg = PromptGovernance(session)
        result = pg.register(_spec(version="1.2.0"))
        assert result.success is False
        assert any("VERSION_DOWNGRADE" in e for e in result.errors)

    def test_lower_version_rejected(self) -> None:
        existing = _make_registry_row(version="2.0.0")
        session = _make_session(existing_active=existing)
        pg = PromptGovernance(session)
        result = pg.register(_spec(version="1.9.0"))
        assert result.success is False
        assert any("VERSION_DOWNGRADE" in e for e in result.errors)

    def test_lower_patch_rejected(self) -> None:
        existing = _make_registry_row(version="1.0.5")
        session = _make_session(existing_active=existing)
        pg = PromptGovernance(session)
        result = pg.register(_spec(version="1.0.4"))
        assert result.success is False

    def test_session_add_not_called_on_downgrade(self) -> None:
        existing = _make_registry_row(version="3.0.0")
        session = _make_session(existing_active=existing)
        pg = PromptGovernance(session)
        pg.register(_spec(version="2.9.9"))
        session.add.assert_not_called()


# ---------------------------------------------------------------------------
# register — upgrade deactivates previous
# ---------------------------------------------------------------------------


class TestRegisterUpgrade:
    def test_upgrade_succeeds(self) -> None:
        existing = _make_registry_row(version="1.0.0")
        session = _make_session(existing_active=existing)
        pg = PromptGovernance(session)
        result = pg.register(_spec(version="1.1.0"))
        assert result.success is True

    def test_upgrade_deactivates_previous(self) -> None:
        existing = _make_registry_row(version="1.0.0")
        session = _make_session(existing_active=existing)
        pg = PromptGovernance(session)
        pg.register(_spec(version="2.0.0"))
        assert existing.is_active is False

    def test_upgrade_warning_mentions_previous_version(self) -> None:
        existing = _make_registry_row(version="1.0.0")
        session = _make_session(existing_active=existing)
        pg = PromptGovernance(session)
        result = pg.register(_spec(version="1.0.1"))
        assert any("1.0.0" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# get_active
# ---------------------------------------------------------------------------


class TestGetActive:
    def test_raises_key_error_when_none(self) -> None:
        session = _make_session(existing_active=None)
        pg = PromptGovernance(session)
        with pytest.raises(KeyError, match="No active prompt template"):
            pg.get_active("tmpl-missing")

    def test_returns_active_row(self) -> None:
        row = _make_registry_row(code="tmpl-x", version="2.0.0")
        session = _make_session(existing_active=row)
        pg = PromptGovernance(session)
        result = pg.get_active("tmpl-x")
        assert result is row


# ---------------------------------------------------------------------------
# deactivate
# ---------------------------------------------------------------------------


class TestDeactivate:
    def test_deactivate_known_code_returns_true(self) -> None:
        row = _make_registry_row(code="tmpl-x")
        session = _make_session(existing_active=row)
        pg = PromptGovernance(session)
        result = pg.deactivate("tmpl-x", reason="replaced by v2")
        assert result is True

    def test_deactivate_sets_is_active_false(self) -> None:
        row = _make_registry_row(code="tmpl-x")
        session = _make_session(existing_active=row)
        pg = PromptGovernance(session)
        pg.deactivate("tmpl-x", reason="reason")
        assert row.is_active is False

    def test_deactivate_unknown_code_returns_false(self) -> None:
        session = _make_session(existing_active=None)
        pg = PromptGovernance(session)
        result = pg.deactivate("tmpl-missing", reason="nothing")
        assert result is False

    def test_deactivate_calls_flush(self) -> None:
        row = _make_registry_row(code="tmpl-x")
        session = _make_session(existing_active=row)
        pg = PromptGovernance(session)
        pg.deactivate("tmpl-x", reason="done")
        session.flush.assert_called()


# ---------------------------------------------------------------------------
# list_versions
# ---------------------------------------------------------------------------


class TestListVersions:
    def test_returns_sorted_newest_first(self) -> None:
        rows = [
            _make_registry_row(version="1.0.0"),
            _make_registry_row(version="2.0.0"),
            _make_registry_row(version="1.5.0"),
        ]
        session = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        filter_mock.all.return_value = rows
        query_mock.filter.return_value = filter_mock
        session.query.return_value = query_mock

        pg = PromptGovernance(session)
        result = pg.list_versions("tmpl-x")
        versions = [r.template_version for r in result]
        assert versions == ["2.0.0", "1.5.0", "1.0.0"]

    def test_empty_list_for_unknown_code(self) -> None:
        session = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        filter_mock.all.return_value = []
        query_mock.filter.return_value = filter_mock
        session.query.return_value = query_mock

        pg = PromptGovernance(session)
        result = pg.list_versions("tmpl-none")
        assert result == []


# ---------------------------------------------------------------------------
# _parse_version
# ---------------------------------------------------------------------------


class TestParseVersion:
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("1.0.0", (1, 0, 0)),
            ("0.1.0", (0, 1, 0)),
            ("10.20.300", (10, 20, 300)),
        ],
    )
    def test_valid_versions(self, version: str, expected: tuple[int, int, int]) -> None:
        assert _parse_version(version) == expected

    @pytest.mark.parametrize("bad", ["1.0", "one.two.three", "", "v1.0.0", "1.0.0.0"])
    def test_invalid_raises_value_error(self, bad: str) -> None:
        with pytest.raises(ValueError, match="Invalid version"):
            _parse_version(bad)


# ---------------------------------------------------------------------------
# validate_template_text
# ---------------------------------------------------------------------------


class TestValidateTemplateText:
    def test_clean_template_no_warnings(self) -> None:
        assert validate_template_text("You are a helpful assistant.") == []

    def test_empty_template_warns(self) -> None:
        warnings = validate_template_text("")
        assert any("EMPTY_TEMPLATE" in w for w in warnings)

    def test_blank_only_warns(self) -> None:
        warnings = validate_template_text("   \n\t  ")
        assert any("EMPTY_TEMPLATE" in w for w in warnings)

    def test_large_template_warns(self) -> None:
        big = "x" * 33_000
        warnings = validate_template_text(big)
        assert any("LARGE_TEMPLATE" in w for w in warnings)

    def test_unmatched_jinja_block_warns(self) -> None:
        text = "Hello {% if x world"  # {%  with no matching %}
        warnings = validate_template_text(text)
        assert any("UNMATCHED_JINJA_BLOCK" in w for w in warnings)

    def test_unmatched_jinja_var_warns(self) -> None:
        text = "Hello {{ name }"  # missing closing brace
        warnings = validate_template_text(text)
        assert any("UNMATCHED_JINJA_VAR" in w for w in warnings)

    def test_valid_jinja_no_warnings(self) -> None:
        text = "Hello {% if name %}{{ name }}{% endif %}"
        warnings = validate_template_text(text)
        # Should not have unmatched jinja warnings
        assert not any("UNMATCHED_JINJA" in w for w in warnings)
