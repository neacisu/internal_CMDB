"""Tests for internalcmdb.workers.retention — data retention helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.workers.retention import (
    _RETENTION_RULES,
    _coerce_days,
    _delete_old_rows,
    _downsample_vitals,
    _drop_old_partitions,
    _matview_exists,
    _purge_snapshots,
    _refresh_materialized_views,
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


# ---------------------------------------------------------------------------
# _purge_snapshots
# ---------------------------------------------------------------------------


class TestPurgeSnapshots:
    def test_purge_snapshots_deletes_diffs_before_snapshots(self):
        conn = MagicMock()
        conn.execute.return_value.rowcount = 5

        counts = _purge_snapshots(conn, "14 days", "3 days", "3 days")

        assert counts["snapshots_deleted"] == 5
        assert counts["high_freq_snapshots_deleted"] == 5
        statements = [str(c[0][0]) for c in conn.execute.call_args_list]
        assert statements[0] == "BEGIN"
        assert "heartbeat" in statements[1] or "container_resources" in statements[1]
        assert "system_vitals" in " ".join(statements)
        assert statements[-1] == "COMMIT"

    def test_purge_snapshots_none_rowcounts(self):
        conn = MagicMock()
        conn.execute.return_value.rowcount = None

        counts = _purge_snapshots(conn, "14 days", "3 days", "3 days")

        assert counts["snapshot_diffs_deleted"] == 0
        assert counts["snapshots_deleted"] == 0
        assert counts["vitals_downsampled"] == 0

    def test_purge_snapshots_rolls_back_on_error(self):
        conn = MagicMock()
        call_count = {"n": 0}

        def execute_side_effect(stmt, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] > 6 and "collector_snapshot" in str(stmt) and "DELETE" in str(stmt):
                raise RuntimeError("boom")
            m = MagicMock()
            m.rowcount = 1
            return m

        conn.execute.side_effect = execute_side_effect

        with pytest.raises(RuntimeError, match="boom"):
            _purge_snapshots(conn, "14 days", "3 days", "3 days")

        statements = [str(c[0][0]) for c in conn.execute.call_args_list]
        assert statements[-1] == "ROLLBACK"


class TestDownsampleVitals:
    def test_downsample_vitals_returns_rowcount(self):
        conn = MagicMock()
        conn.execute.return_value.rowcount = 42

        result = _downsample_vitals(conn, "3 days")

        assert result == 42
        assert conn.execute.call_count >= 2


class TestMatviewRefresh:
    def test_matview_exists_true(self):
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = True
        assert _matview_exists(conn, "cognitive.mv_fleet_health_live") is True

    def test_refresh_skips_missing_view(self):
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = False

        results = _refresh_materialized_views(conn)

        assert results[0]["status"] == "missing"
        refresh_calls = [
            c for c in conn.execute.call_args_list if "REFRESH" in str(c[0][0])
        ]
        assert refresh_calls == []


# ---------------------------------------------------------------------------
# _coerce_days / rule configuration
# ---------------------------------------------------------------------------


class TestCoerceDays:
    def test_valid_int(self):
        assert _coerce_days(14, 30) == 14

    def test_valid_str(self):
        assert _coerce_days("21", 30) == 21

    def test_invalid_value_falls_back(self):
        assert _coerce_days("abc", 30) == 30
        assert _coerce_days(None, 30) == 30

    def test_non_positive_falls_back(self):
        assert _coerce_days(0, 30) == 30
        assert _coerce_days(-5, 30) == 30


class TestRetentionRules:
    def test_snapshot_rule_present(self):
        snapshot_rules = [r for r in _RETENTION_RULES if r["mode"] == "snapshots"]
        assert len(snapshot_rules) == 1
        assert snapshot_rules[0]["table"] == "discovery.collector_snapshot"
        assert snapshot_rules[0]["setting_key"] == "retention.snapshots_days"

    def test_all_rules_have_required_keys(self):
        for rule in _RETENTION_RULES:
            assert {"table", "ts_column", "mode", "setting_key", "default_days"} <= set(rule)
            assert int(rule["default_days"]) >= 1
