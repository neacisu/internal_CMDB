"""Tests for internalcmdb.seeds.settings_seed — mocked DB seed function."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.seeds.settings_seed import (
    _SETTINGS,
    run_seed,
)

# ---------------------------------------------------------------------------
# _SETTINGS catalogue structure tests (no DB needed)
# ---------------------------------------------------------------------------


class TestSettingsStructure:
    def test_settings_list_is_non_empty(self) -> None:
        assert len(_SETTINGS) > 0

    def test_all_entries_have_seven_elements(self) -> None:
        for entry in _SETTINGS:
            assert len(entry) == 7, f"Entry {entry[0]} has {len(entry)} elements, expected 7"

    def test_all_setting_keys_are_non_empty_strings(self) -> None:
        for key, *_ in _SETTINGS:
            assert isinstance(key, str), f"Setting key is not a string: {key!r}"
            assert key, f"Setting key is empty: {key!r}"

    def test_all_setting_groups_are_non_empty_strings(self) -> None:
        for _, group, *_ in _SETTINGS:
            assert isinstance(group, str), f"Setting group is not a string: {group!r}"
            assert group, f"Setting group is empty: {group!r}"

    def test_all_type_hints_are_strings(self) -> None:
        for key, _, _, type_hint, *_ in _SETTINGS:
            assert isinstance(type_hint, str), (
                f"type_hint for {key!r} is not a string: {type_hint!r}"
            )

    def test_all_descriptions_are_non_empty_strings(self) -> None:
        for key, _, _, _, description, *_ in _SETTINGS:
            assert isinstance(description, str), f"Description for {key!r} is not a string"
            assert description, f"Description for {key!r} is empty"

    def test_all_is_secret_flags_are_bool(self) -> None:
        for key, _, _, _, _, is_secret, _ in _SETTINGS:
            assert isinstance(is_secret, bool), f"is_secret for {key!r} is not bool: {is_secret!r}"

    def test_all_requires_restart_flags_are_bool(self) -> None:
        for key, _, _, _, _, _, req_restart in _SETTINGS:
            assert isinstance(req_restart, bool), (
                f"requires_restart for {key!r} is not bool: {req_restart!r}"
            )

    def test_setting_keys_are_unique(self) -> None:
        keys = [entry[0] for entry in _SETTINGS]
        duplicates = [k for k in set(keys) if keys.count(k) > 1]
        assert not duplicates, f"Duplicate setting keys: {duplicates}"

    def test_at_least_ten_settings(self) -> None:
        assert len(_SETTINGS) >= 10

    def test_llm_group_settings_exist(self) -> None:
        groups = {entry[1] for entry in _SETTINGS}
        assert "llm" in groups

    def test_reasoning_url_setting_exists(self) -> None:
        keys = [entry[0] for entry in _SETTINGS]
        assert "llm.reasoning.url" in keys

    def test_fast_url_setting_exists(self) -> None:
        keys = [entry[0] for entry in _SETTINGS]
        assert "llm.fast.url" in keys

    def test_no_secret_key_has_non_bool_is_secret(self) -> None:
        """Verify secret classification is explicit boolean, not truthy value."""
        for key, _, _, _, _, is_secret, _ in _SETTINGS:
            assert is_secret is True or is_secret is False, (
                f"{key}: is_secret must be exactly True or False, got {is_secret!r}"
            )

    def test_setting_keys_use_dot_notation(self) -> None:
        """Convention: all keys must contain at least one dot (group.key pattern)."""
        for key, *_ in _SETTINGS:
            assert "." in key, f"Setting key {key!r} does not follow group.key convention"

    def test_default_values_are_json_serialisable(self) -> None:
        """All default values must be serialisable to JSON (used in run_seed)."""
        import json  # noqa: PLC0415

        for key, _, default_val, *_ in _SETTINGS:
            try:
                json.dumps(default_val)
            except (TypeError, ValueError) as exc:
                pytest.fail(f"Default value for {key!r} is not JSON-serialisable: {exc}")


# ---------------------------------------------------------------------------
# run_seed() with fully mocked SQLAlchemy infrastructure
# ---------------------------------------------------------------------------


class TestRunSeed:
    """Test run_seed() behaviour without a real database.

    Strategy: patch create_engine + sessionmaker so no network I/O occurs.
    The mock session.execute() returns a CursorResult mock with rowcount=1
    on the first call (all rows fresh) to exercise the happy path.
    """

    def _make_mock_engine_factory(
        self, *, rowcount: int = 1
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Return (mock_engine, mock_session, mock_factory)."""
        mock_result = MagicMock()
        mock_result.rowcount = rowcount

        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        mock_engine = MagicMock()

        return mock_engine, mock_session, mock_factory

    def test_returns_inserted_count_all_fresh(self) -> None:
        mock_engine, _mock_session, mock_factory = self._make_mock_engine_factory(rowcount=1)
        with (
            patch(
                "internalcmdb.seeds.settings_seed.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "internalcmdb.seeds.settings_seed.sessionmaker",
                return_value=mock_factory,
            ),
        ):
            result = run_seed("postgresql://mock/db")
        assert result == len(_SETTINGS)

    def test_returns_zero_when_all_already_seeded(self) -> None:
        mock_engine, _mock_session, mock_factory = self._make_mock_engine_factory(rowcount=0)
        with (
            patch(
                "internalcmdb.seeds.settings_seed.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "internalcmdb.seeds.settings_seed.sessionmaker",
                return_value=mock_factory,
            ),
        ):
            result = run_seed("postgresql://mock/db")
        assert result == 0

    def test_execute_called_once_per_setting(self) -> None:
        mock_engine, mock_session, mock_factory = self._make_mock_engine_factory(rowcount=1)
        with (
            patch(
                "internalcmdb.seeds.settings_seed.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "internalcmdb.seeds.settings_seed.sessionmaker",
                return_value=mock_factory,
            ),
        ):
            run_seed("postgresql://mock/db")
        assert mock_session.execute.call_count == len(_SETTINGS)

    def test_commit_called_after_all_inserts(self) -> None:
        mock_engine, mock_session, mock_factory = self._make_mock_engine_factory(rowcount=1)
        with (
            patch(
                "internalcmdb.seeds.settings_seed.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "internalcmdb.seeds.settings_seed.sessionmaker",
                return_value=mock_factory,
            ),
        ):
            run_seed("postgresql://mock/db")
        mock_session.commit.assert_called_once()

    def test_engine_dispose_called_after_seed(self) -> None:
        mock_engine, _mock_session, mock_factory = self._make_mock_engine_factory(rowcount=1)
        with (
            patch(
                "internalcmdb.seeds.settings_seed.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "internalcmdb.seeds.settings_seed.sessionmaker",
                return_value=mock_factory,
            ),
        ):
            run_seed("postgresql://mock/db")
        mock_engine.dispose.assert_called_once()

    def test_create_engine_called_with_provided_url(self) -> None:
        mock_engine, _, mock_factory = self._make_mock_engine_factory()
        with (
            patch(
                "internalcmdb.seeds.settings_seed.create_engine",
                return_value=mock_engine,
            ) as mock_create_engine,
            patch(
                "internalcmdb.seeds.settings_seed.sessionmaker",
                return_value=mock_factory,
            ),
        ):
            run_seed("postgresql://specific-host/mydb")
        mock_create_engine.assert_called_once_with(
            "postgresql://specific-host/mydb", pool_pre_ping=True
        )

    def test_execute_parameters_include_setting_key(self) -> None:
        """Verify the first _SETTINGS entry's key is passed in the params dict."""
        mock_engine, mock_session, mock_factory = self._make_mock_engine_factory(rowcount=1)
        first_key = _SETTINGS[0][0]
        with (
            patch(
                "internalcmdb.seeds.settings_seed.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "internalcmdb.seeds.settings_seed.sessionmaker",
                return_value=mock_factory,
            ),
        ):
            run_seed("postgresql://mock/db")
        first_call_args = mock_session.execute.call_args_list[0]
        params: dict[str, object] = first_call_args[0][1]
        assert params["key"] == first_key

    def test_rowcount_none_treated_as_zero(self) -> None:
        """rowcount can be None on some drivers after ON CONFLICT DO NOTHING."""
        mock_engine, mock_session, mock_factory = self._make_mock_engine_factory(rowcount=0)
        # Override rowcount to None to simulate drivers that return None
        mock_session.execute.return_value.rowcount = None
        with (
            patch(
                "internalcmdb.seeds.settings_seed.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "internalcmdb.seeds.settings_seed.sessionmaker",
                return_value=mock_factory,
            ),
        ):
            result = run_seed("postgresql://mock/db")
        # None rowcount → `rowcount or 0` → 0 per insert → total 0
        assert result == 0

    def test_logs_inserted_count(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging  # noqa: PLC0415

        mock_engine, _mock_session, mock_factory = self._make_mock_engine_factory(rowcount=1)
        with (
            caplog.at_level(logging.INFO, logger="internalcmdb.seeds.settings_seed"),
            patch(
                "internalcmdb.seeds.settings_seed.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "internalcmdb.seeds.settings_seed.sessionmaker",
                return_value=mock_factory,
            ),
        ):
            run_seed("postgresql://mock/db")
        assert any("settings_seed" in r.message for r in caplog.records)
        assert any(str(len(_SETTINGS)) in r.message for r in caplog.records)
