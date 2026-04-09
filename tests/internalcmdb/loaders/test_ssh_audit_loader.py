"""Tests for internalcmdb.loaders.ssh_audit_loader — pure helpers and mocked load."""

from __future__ import annotations

import sys
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.loaders.ssh_audit_loader import (
    _create_collection_run,
    _ensure_discovery_source,
    _exit_if_empty_term_map,
    _insert_hardware_snapshot,
    _int_or_none,
    _load_term_map,
    _node_docker_running_count,
    _os_family_term_code,
    _primary_host_role_term_code,
    _process_audit_node,
    _ssh_ok_hosts_from_check,
    _term,
    _upsert_gpu_devices,
    _upsert_host,
    load,
)

# ---------------------------------------------------------------------------
# _os_family_term_code
# ---------------------------------------------------------------------------


class TestOsFamilyTermCode:
    def test_ubuntu_returns_ubuntu(self) -> None:
        assert _os_family_term_code("Ubuntu 22.04.3 LTS") == "ubuntu"

    def test_ubuntu_lower(self) -> None:
        assert _os_family_term_code("ubuntu focal") == "ubuntu"

    def test_debian_returns_debian(self) -> None:
        assert _os_family_term_code("Debian GNU/Linux 12") == "debian"

    def test_macos_returns_macos(self) -> None:
        assert _os_family_term_code("macOS 14.2.1") == "macos"

    def test_darwin_returns_macos(self) -> None:
        assert _os_family_term_code("darwin 23.0.0") == "macos"

    def test_unknown_string_returns_unknown(self) -> None:
        assert _os_family_term_code("CentOS Stream 9") == "unknown"

    def test_empty_string_returns_unknown(self) -> None:
        assert _os_family_term_code("") == "unknown"

    def test_windows_returns_unknown(self) -> None:
        assert _os_family_term_code("Windows Server 2022") == "unknown"


# ---------------------------------------------------------------------------
# _int_or_none
# ---------------------------------------------------------------------------


class TestIntOrNone:
    def test_integer_value(self) -> None:
        assert _int_or_none(42) == 42

    def test_string_integer(self) -> None:
        assert _int_or_none("100") == 100

    def test_none_returns_none(self) -> None:
        assert _int_or_none(None) is None

    def test_float_truncates(self) -> None:
        assert _int_or_none(3.9) == 3

    def test_non_numeric_string_returns_none(self) -> None:
        assert _int_or_none("abc") is None

    def test_empty_string_returns_none(self) -> None:
        assert _int_or_none("") is None

    def test_zero(self) -> None:
        assert _int_or_none(0) == 0


# ---------------------------------------------------------------------------
# _term helper (same logic as runtime_posture_loader)
# ---------------------------------------------------------------------------


class TestTermHelper:
    def test_returns_matching_uuid(self) -> None:
        uid = uuid.uuid4()
        term_map = {("entity_kind", "host"): uid}
        assert _term(term_map, "entity_kind", "host") == uid

    def test_raises_key_error_when_missing(self) -> None:
        with pytest.raises(KeyError):
            _term({}, "entity_kind", "nonexistent")

    def test_uses_fallback_when_primary_missing(self) -> None:
        fallback_uid = uuid.uuid4()
        term_map = {("entity_kind", "server"): fallback_uid}
        result = _term(term_map, "entity_kind", "host", fallback="server")
        assert result == fallback_uid

    def test_raises_without_fallback(self) -> None:
        with pytest.raises(KeyError):
            _term({}, "entity_kind", "x", fallback="y")


# ---------------------------------------------------------------------------
# load() with mocked connection
# ---------------------------------------------------------------------------


def _make_term_map_ssh() -> dict[tuple[str, str], uuid.UUID]:
    return {
        ("entity_kind", "host"): uuid.uuid4(),
        ("discovery_source_kind", "ssh_full_audit"): uuid.uuid4(),
        ("collection_run_status", "succeeded"): uuid.uuid4(),
        ("collection_run_status", "failed"): uuid.uuid4(),
        ("environment", "production"): uuid.uuid4(),
        ("lifecycle_status", "active"): uuid.uuid4(),
        ("lifecycle_status", "unknown"): uuid.uuid4(),
        ("os_family", "ubuntu"): uuid.uuid4(),
        ("os_family", "unknown"): uuid.uuid4(),
        ("host_role", "monitored_host"): uuid.uuid4(),
        ("host_role", "gpu_inference_node"): uuid.uuid4(),
        ("host_role", "application_runtime_host"): uuid.uuid4(),
        ("host_role", "automation_host"): uuid.uuid4(),
        ("host_role", "database_host"): uuid.uuid4(),
    }


class TestLoadSshFunction:
    def test_load_empty_nodes_completes(self) -> None:
        term_map = _make_term_map_ssh()
        conn = MagicMock()
        audit_data: dict[str, Any] = {"nodes": [], "audit_ts": "2026-01-01T00:00:00Z"}

        with (
            patch(
                "internalcmdb.loaders.ssh_audit_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._create_collection_run",
                return_value=uuid.uuid4(),
            ),
        ):
            load(conn, audit_data)

    def test_load_empty_term_map_exits(self) -> None:
        conn = MagicMock()
        audit_data: dict[str, Any] = {"nodes": []}

        with (
            patch(
                "internalcmdb.loaders.ssh_audit_loader._load_term_map",
                return_value={},
            ),
            pytest.raises(SystemExit),
        ):
            load(conn, audit_data)

    def test_load_with_node_error_skipped(self) -> None:
        term_map = _make_term_map_ssh()
        conn = MagicMock()
        audit_data: dict[str, Any] = {
            "nodes": [{"alias": "bad-node", "error": "connection refused", "system": {}}],
        }

        with (
            patch(
                "internalcmdb.loaders.ssh_audit_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._create_collection_run",
                return_value=uuid.uuid4(),
            ),
        ):
            load(conn, audit_data)  # No raise — node skipped

    def test_load_with_ssh_check_data(self) -> None:
        term_map = _make_term_map_ssh()
        conn = MagicMock()
        audit_data: dict[str, Any] = {"nodes": []}
        ssh_check_data: dict[str, Any] = {
            "payload": {
                "results": [
                    {"host": "prod-node-1", "ok": True},
                    {"host": "prod-node-2", "ok": False},
                ]
            }
        }

        with (
            patch(
                "internalcmdb.loaders.ssh_audit_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._create_collection_run",
                return_value=uuid.uuid4(),
            ),
        ):
            load(conn, audit_data, ssh_check_data=ssh_check_data)

    def test_load_node_processed_successfully(self) -> None:
        term_map = _make_term_map_ssh()
        conn = MagicMock()
        host_id = uuid.uuid4()
        audit_data: dict[str, Any] = {
            "nodes": [
                {
                    "alias": "prod-node-1",
                    "system": {
                        "os": "Ubuntu 22.04",
                        "hostname": "prod-node-1",
                        "kernel": "6.1",
                        "arch": "x86_64",
                    },
                    "gpu": [],
                    "docker": None,
                }
            ],
        }

        with (
            patch(
                "internalcmdb.loaders.ssh_audit_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._create_collection_run",
                return_value=uuid.uuid4(),
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._upsert_host",
                return_value=host_id,
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._insert_hardware_snapshot",
            ),
            patch(
                "internalcmdb.loaders.ssh_audit_loader._upsert_gpu_devices",
            ),
        ):
            load(conn, audit_data)
            conn.commit.assert_called_once()


class TestLoadTermMapSsh:
    def test_returns_populated_dict(self) -> None:
        tid = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [("entity_kind", "host", tid)]
        result = _load_term_map(conn)
        assert result == {("entity_kind", "host"): tid}

    def test_empty_rows_returns_empty(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        assert _load_term_map(conn) == {}


class TestEnsureDiscoverySourceSsh:
    def _ssh_term_map(self) -> dict[tuple[str, str], uuid.UUID]:
        return {("discovery_source_kind", "ssh_full_audit"): uuid.uuid4()}

    def test_existing_source_returned(self) -> None:
        source_id = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (source_id,)
        result = _ensure_discovery_source(conn, self._ssh_term_map())
        assert result == source_id

    def test_new_source_inserted(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        result = _ensure_discovery_source(conn, self._ssh_term_map())
        assert conn.execute.call_count >= 2
        assert isinstance(result, uuid.UUID)


class TestCreateCollectionRunHelper:
    def test_creates_run_and_returns_id(self) -> None:
        conn = MagicMock()
        term_map: dict[tuple[str, str], uuid.UUID] = {
            ("collection_run_status", "succeeded"): uuid.uuid4(),
        }
        run_id = _create_collection_run(
            conn, uuid.uuid4(), "2026-01-01T00:00:00Z", term_map, ["n1"]
        )
        conn.execute.assert_called_once()
        assert isinstance(run_id, uuid.UUID)


class TestUpsertHostHelper:
    def _host_term_map(self) -> dict[tuple[str, str], uuid.UUID]:
        return {
            ("entity_kind", "host"): uuid.uuid4(),
            ("environment", "production"): uuid.uuid4(),
            ("lifecycle_status", "active"): uuid.uuid4(),
            ("lifecycle_status", "unknown"): uuid.uuid4(),
            ("os_family", "ubuntu"): uuid.uuid4(),
            ("os_family", "unknown"): uuid.uuid4(),
            ("host_role", "monitored_host"): uuid.uuid4(),
            ("host_role", "gpu_inference_node"): uuid.uuid4(),
            ("host_role", "application_runtime_host"): uuid.uuid4(),
            ("host_role", "automation_host"): uuid.uuid4(),
            ("host_role", "database_host"): uuid.uuid4(),
        }

    def test_existing_host_updated(self) -> None:
        host_id = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (host_id,)
        node: dict[str, Any] = {
            "alias": "prod-01",
            "system": {
                "os": "Ubuntu 22.04",
                "hostname": "prod-01",
                "kernel": "6.1",
                "arch": "x86_64",
            },
            "gpu": [],
        }
        result = _upsert_host(conn, node, self._host_term_map(), uuid.uuid4(), {"prod-01"})
        assert result == host_id

    def test_new_host_inserted(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        node: dict[str, Any] = {
            "alias": "node-new",
            "system": {
                "os": "Ubuntu 22.04",
                "hostname": "node-new",
                "kernel": "6.1",
                "arch": "x86_64",
            },
            "gpu": [],
        }
        result = _upsert_host(conn, node, self._host_term_map(), uuid.uuid4(), set())
        assert isinstance(result, uuid.UUID)

    def test_gpu_node_gets_gpu_role(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        node: dict[str, Any] = {
            "alias": "gpu-01",
            "system": {},
            "gpu": [{"gpu_uuid": "GPU-abc123"}],
        }
        result = _upsert_host(conn, node, self._host_term_map(), uuid.uuid4(), set())
        assert isinstance(result, uuid.UUID)

    def test_orchestrator_gets_automation_role(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        node: dict[str, Any] = {"alias": "orchestrator", "system": {}, "gpu": []}
        result = _upsert_host(conn, node, self._host_term_map(), uuid.uuid4(), set())
        assert isinstance(result, uuid.UUID)

    def test_postgres_main_gets_database_role(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        node: dict[str, Any] = {"alias": "postgres-main", "system": {}, "gpu": []}
        result = _upsert_host(conn, node, self._host_term_map(), uuid.uuid4(), set())
        assert isinstance(result, uuid.UUID)


class TestInsertHardwareSnapshotHelper:
    def test_inserts_snapshot_without_error(self) -> None:
        conn = MagicMock()
        node: dict[str, Any] = {
            "hardware": {
                "cpu_model": "Intel Xeon",
                "cpu_physical": 2,
                "cpu_cores": 16,
                "ram_total_kb": 65536000,
                "ram_free_kb": 32768000,
                "swap_total_kb": 8388608,
                "gpu_count": 0,
            }
        }
        _insert_hardware_snapshot(conn, uuid.uuid4(), uuid.uuid4(), node)
        conn.execute.assert_called_once()

    def test_no_hardware_key_still_inserts(self) -> None:
        conn = MagicMock()
        _insert_hardware_snapshot(conn, uuid.uuid4(), uuid.uuid4(), {})
        conn.execute.assert_called_once()


class TestUpsertGpuDevicesHelper:
    def test_skip_gpu_without_uuid(self) -> None:
        conn = MagicMock()
        gpus: list[dict[str, Any]] = [{"gpu_name": "A100", "gpu_uuid": None}]
        _upsert_gpu_devices(conn, uuid.uuid4(), gpus, uuid.uuid4())
        conn.execute.assert_not_called()

    def test_existing_gpu_updated(self) -> None:
        dev_id = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (dev_id,)
        gpus: list[dict[str, Any]] = [{"gpu_uuid": "GPU-abc", "gpu_name": "A100"}]
        _upsert_gpu_devices(conn, uuid.uuid4(), gpus, uuid.uuid4())
        assert conn.execute.call_count >= 2

    def test_new_gpu_inserted(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        gpus: list[dict[str, Any]] = [{"gpu_uuid": "GPU-abc", "gpu_name": "A100"}]
        _upsert_gpu_devices(conn, uuid.uuid4(), gpus, uuid.uuid4())
        assert conn.execute.call_count >= 2


# ---------------------------------------------------------------------------
# Refactored helpers (cognitive complexity / S3776)
# ---------------------------------------------------------------------------


class TestNodeDockerRunningCount:
    def test_missing_docker(self) -> None:
        assert _node_docker_running_count({}) == 0

    def test_counts_only_running(self) -> None:
        node = {
            "docker": {
                "containers": [
                    {"state": "running"},
                    {"state": "exited"},
                    {"state": "running"},
                ]
            }
        }
        assert _node_docker_running_count(node) == 2


class TestPrimaryHostRoleTermCode:
    def test_gpu_wins_over_container_count(self) -> None:
        assert _primary_host_role_term_code("any", True, 99) == "gpu_inference_node"

    def test_many_containers(self) -> None:
        assert _primary_host_role_term_code("worker-1", False, 6) == "application_runtime_host"

    def test_named_hosts(self) -> None:
        assert _primary_host_role_term_code("orchestrator", False, 0) == "automation_host"
        assert _primary_host_role_term_code("postgres-main", False, 0) == "database_host"

    def test_default_monitored(self) -> None:
        assert _primary_host_role_term_code("gpu-01", False, 3) == "monitored_host"


class TestSshOkHostsFromCheck:
    def test_none_payload(self) -> None:
        assert _ssh_ok_hosts_from_check(None) == set()

    def test_collects_ok_hosts(self) -> None:
        data = {
            "payload": {
                "results": [
                    {"ok": True, "host": "a"},
                    {"ok": False, "host": "b"},
                    {"ok": True, "host": 1},
                ]
            }
        }
        assert _ssh_ok_hosts_from_check(data) == {"a"}


class TestExitIfEmptyTermMap:
    def test_non_empty_no_exit(self) -> None:
        _exit_if_empty_term_map({("x", "y"): uuid.uuid4()})

    def test_empty_calls_exit(self) -> None:
        with (
            patch.object(sys, "exit", side_effect=RuntimeError("exit")) as mock_exit,
            pytest.raises(RuntimeError, match="exit"),
        ):
            _exit_if_empty_term_map({})
        mock_exit.assert_called_once_with(1)


class TestProcessAuditNode:
    def test_skip_on_node_error(self) -> None:
        conn = MagicMock()
        out = _process_audit_node(
            conn,
            {"alias": "h1", "error": "disk full"},
            {},
            uuid.uuid4(),
            set(),
        )
        assert out == ("skip", "h1", "disk full")
        conn.execute.assert_not_called()

    def test_ok_runs_pipeline(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        term_map = {
            ("entity_kind", "host"): uuid.uuid4(),
            ("environment", "production"): uuid.uuid4(),
            ("lifecycle_status", "unknown"): uuid.uuid4(),
            ("lifecycle_status", "active"): uuid.uuid4(),
            ("os_family", "unknown"): uuid.uuid4(),
            ("os_family", "ubuntu"): uuid.uuid4(),
            ("host_role", "monitored_host"): uuid.uuid4(),
        }
        node: dict[str, Any] = {"alias": "edge-1", "system": {"os": "Ubuntu 22.04"}}
        rid = uuid.uuid4()
        out = _process_audit_node(conn, node, term_map, rid, set())
        assert out[0] == "ok"
        assert out[1] == "edge-1"
        uuid.UUID(out[2])  # host_id
