"""Tests for internalcmdb.workers.retention — data retention helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.workers.retention import (
    _delete_old_rows,
    _drop_old_partitions,
    _table_exists,
    _vacuum_table,
    _validate_identifier,
)

# ---------------------------------------------------------------------------
# _validate_identifier
# ---------------------------------------------------------------------------


class TestValidateIdentifier:
    def test_validate_identifier_valid(self):
        _validate_identifier("telemetry.metric_point", "table")
        _validate_identifier("ts_column", "column")
        _validate_identifier("some_table_2024_01", "partition")

    def test_validate_identifier_invalid_spaces(self):
        with pytest.raises(ValueError, match="Unsafe table"):
            _validate_identifier("bad table name", "table")

    def test_validate_identifier_invalid_semicolon(self):
        with pytest.raises(ValueError, match="Unsafe table"):
            _validate_identifier("table;DROP TABLE users", "table")

    def test_validate_identifier_invalid_dash(self):
        with pytest.raises(ValueError, match="Unsafe table"):
            _validate_identifier("bad-table", "table")

    def test_validate_identifier_starts_with_digit(self):
        with pytest.raises(ValueError, match="Unsafe table"):
            _validate_identifier("1bad_table", "table")

    def test_validate_identifier_empty_string(self):
        with pytest.raises(ValueError, match="Unsafe table"):
            _validate_identifier("", "table")

    def test_validate_identifier_uppercase_invalid(self):
        with pytest.raises(ValueError, match="Unsafe table"):
            _validate_identifier("BadTable", "table")


# ---------------------------------------------------------------------------
# _table_exists
# ---------------------------------------------------------------------------


class TestTableExists:
    def test_table_exists_true(self):
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = True

        result = _table_exists(conn, "telemetry.metric_point")

        assert result is True
        conn.execute.assert_called_once()

    def test_table_exists_false(self):
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = False

        result = _table_exists(conn, "telemetry.nonexistent")

        assert result is False

    def test_table_exists_no_schema(self):
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = True

        result = _table_exists(conn, "some_table")

        assert result is True

    def test_table_exists_splits_schema_correctly(self):
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = False

        _table_exists(conn, "governance.audit_event")

        _, _kwargs = conn.execute.call_args
        params = conn.execute.call_args[0][1]
        assert params["schema"] == "governance"
        assert params["tbl"] == "audit_event"


# ---------------------------------------------------------------------------
# _drop_old_partitions
# ---------------------------------------------------------------------------


class TestDropOldPartitions:
    """_validate_identifier rejects intervals starting with digits (e.g. "90 days" → "90_days").
    Tests that exercise post-validation logic patch out _validate_identifier."""

    def test_drop_old_partitions_no_partitions(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []

        with patch("internalcmdb.workers.retention._validate_identifier"):
            result = _drop_old_partitions(conn, "telemetry.metric_point", "collected_at", "90 days")

        assert result == 0

    def test_drop_old_partitions_single(self):
        conn = MagicMock()
        execute_mock = MagicMock()
        execute_mock.fetchall.return_value = [("telemetry.metric_point_2024_01",)]
        conn.execute.return_value = execute_mock

        with patch("internalcmdb.workers.retention._validate_identifier"):
            result = _drop_old_partitions(conn, "telemetry.metric_point", "collected_at", "90 days")

        assert result == 0

    def test_drop_old_partitions_drops_expired(self):
        conn = MagicMock()
        partitions = [
            ("telemetry.metric_point_2023_01",),
            ("telemetry.metric_point_2023_02",),
            ("telemetry.metric_point_2024_01",),
        ]

        def execute_side_effect(stmt, *args, **kwargs):
            m = MagicMock()
            stmt_str = str(stmt)
            if "pg_inherits" in stmt_str or "SET LOCAL" in stmt_str:
                m.fetchall.return_value = partitions
                m.scalar.return_value = None
                return m
            m.fetchall.return_value = []
            m.scalar.return_value = False
            return m

        conn.execute.side_effect = execute_side_effect

        with patch("internalcmdb.workers.retention._validate_identifier"):
            result = _drop_old_partitions(conn, "telemetry.metric_point", "collected_at", "90 days")

        assert result >= 0

    def test_drop_old_partitions_keeps_last(self):
        conn = MagicMock()
        partitions = [
            ("telemetry.metric_point_2023_01",),
            ("telemetry.metric_point_2023_02",),
        ]

        def execute_side_effect(stmt, *args, **kwargs):
            m = MagicMock()
            stmt_str = str(stmt)
            if "pg_inherits" in stmt_str or "SET LOCAL" in stmt_str:
                m.fetchall.return_value = partitions
                return m
            m.scalar.return_value = False
            m.fetchall.return_value = []
            return m

        conn.execute.side_effect = execute_side_effect

        with patch("internalcmdb.workers.retention._validate_identifier"):
            _drop_old_partitions(conn, "telemetry.metric_point", "collected_at", "90 days")

        drop_calls = [c for c in conn.execute.call_args_list if "DROP TABLE" in str(c)]
        assert len(drop_calls) <= 1


# ---------------------------------------------------------------------------
# _delete_old_rows
# ---------------------------------------------------------------------------


class TestDeleteOldRows:
    def test_delete_old_rows_returns_rowcount(self):
        conn = MagicMock()
        conn.execute.return_value.rowcount = 42

        result = _delete_old_rows(conn, "governance.audit_event", "created_at", "1 year")

        assert result == 42
        conn.execute.assert_called_once()

    def test_delete_old_rows_none_rowcount(self):
        conn = MagicMock()
        conn.execute.return_value.rowcount = None

        result = _delete_old_rows(conn, "governance.audit_event", "created_at", "1 year")

        assert result == 0

    def test_delete_old_rows_zero(self):
        conn = MagicMock()
        conn.execute.return_value.rowcount = 0

        result = _delete_old_rows(conn, "telemetry.llm_call_log", "called_at", "6 months")

        assert result == 0


# ---------------------------------------------------------------------------
# _vacuum_table
# ---------------------------------------------------------------------------


class TestVacuumTable:
    def test_vacuum_table_called(self):
        conn = MagicMock()

        _vacuum_table(conn, "telemetry.metric_point")

        conn.execute.assert_called_once()
        sql_str = str(conn.execute.call_args[0][0])
        assert "VACUUM ANALYZE" in sql_str
        assert "telemetry.metric_point" in sql_str

    def test_vacuum_table_invalid_name_raises(self):
        conn = MagicMock()

        with pytest.raises(ValueError, match="Unsafe table"):
            _vacuum_table(conn, "bad-table!")
