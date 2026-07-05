"""Tests for scripts/sync_remaining_hosts.py.

Covers:
  - Module constants (S1192 compliance verification)
  - REMAINING_HOSTS list integrity
  - get_taxonomy_terms() parsing
  - upsert_host() INSERT and UPDATE paths
  - link_all_unlinked() linking and skip behaviour
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).parents[3] / "scripts" / "sync_remaining_hosts.py"


# Clearly-named test-only placeholder; value carries no real access rights.
_TEST_DB_PASSWORD = "test"  # NOSONAR


@pytest.fixture(scope="module")
def sync(tmp_path_factory: pytest.TempPathFactory) -> types.ModuleType:
    mock_env = {
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": _TEST_DB_PASSWORD,
        "POSTGRES_DB": "testdb",
        "POSTGRES_SYNC_HOST": "127.0.0.1",
        "POSTGRES_SYNC_PORT": "5432",
    }
    mock_engine = MagicMock()

    # Snapshot keys before deletion to avoid mutating the dict during iteration.
    stale = {k for k in sys.modules if "sync_remaining_hosts" in k}
    for key in stale:
        del sys.modules[key]

    with (
        patch.dict(os.environ, mock_env, clear=False),
        patch("dotenv.load_dotenv"),
        patch("sqlalchemy.create_engine", return_value=mock_engine),
    ):
        spec = importlib.util.spec_from_file_location("sync_remaining_hosts", _SCRIPT_PATH)
        assert spec is not None, f"Cannot locate module spec for {_SCRIPT_PATH}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod


# ---------------------------------------------------------------------------
# Constants integrity (S1192 compliance)
# ---------------------------------------------------------------------------


def test_os_ubuntu_24_04_constant_is_correct(sync: Any) -> None:
    assert sync.OS_UBUNTU_24_04 == "Ubuntu 24.04 LTS"


def test_parent_hz_constants_are_correct(sync: Any) -> None:
    assert sync.PARENT_HZ215 == "hz.215"
    assert sync.PARENT_HZ223 == "hz.223"
    assert sync.PARENT_HZ247 == "hz.247"


def test_no_literal_ubuntu_24_04_in_data(sync: Any) -> None:
    """Verify every LXC entry uses the constant, not the literal string."""
    for h in sync.REMAINING_HOSTS:
        if h["os_family"] == "ubuntu" and h["host_code"] != "orchestrator":
            assert h["os_version_text"] is sync.OS_UBUNTU_24_04, (
                f"{h['host_code']} still uses a literal instead of OS_UBUNTU_24_04"
            )


def test_no_literal_hz223_in_metadata(sync: Any) -> None:
    """Verify every hz.223 child uses the PARENT_HZ223 constant."""
    for h in sync.REMAINING_HOSTS:
        if h.get("metadata", {}).get("parent_host") == "hz.223":
            # Verify Python object identity (constant re-use), not just value equality.
            assert h["metadata"]["parent_host"] is sync.PARENT_HZ223, (
                f"{h['host_code']} metadata uses a literal instead of PARENT_HZ223"
            )


# ---------------------------------------------------------------------------
# REMAINING_HOSTS list integrity
# ---------------------------------------------------------------------------


def test_remaining_hosts_has_seven_entries(sync: Any) -> None:
    assert len(sync.REMAINING_HOSTS) == 7


def test_remaining_hosts_host_codes_unique(sync: Any) -> None:
    codes: list[str] = [h["host_code"] for h in sync.REMAINING_HOSTS]
    assert len(codes) == len(set(codes))


def test_orchestrator_is_docker_and_hypervisor(sync: Any) -> None:
    orch: dict[str, Any] = next(h for h in sync.REMAINING_HOSTS if h["host_code"] == "orchestrator")
    assert orch["is_docker_host"] is True
    assert orch["is_hypervisor"] is True
    assert orch["primary_public_ipv4"] == "77.42.76.185"


def test_lxc_hosts_have_private_ips_only(sync: Any) -> None:
    for h in sync.REMAINING_HOSTS:
        if h["host_code"] == "orchestrator":
            continue
        assert h["primary_public_ipv4"] is None
        assert h["primary_private_ipv4"] is not None
        assert str(h["primary_private_ipv4"]).startswith("10.0.1.")


def test_all_hosts_have_ssh_alias(sync: Any) -> None:
    for h in sync.REMAINING_HOSTS:
        assert h.get("ssh_alias"), f"{h['host_code']} missing ssh_alias"


# ---------------------------------------------------------------------------
# get_taxonomy_terms
# ---------------------------------------------------------------------------


def test_get_taxonomy_terms_builds_dict(sync: Any) -> None:
    conn = MagicMock()
    eid = uuid.uuid4()
    conn.execute.return_value.fetchall.return_value = [
        ("entity_kind", "host", eid),
    ]
    result: dict[tuple[str, str], uuid.UUID] = sync.get_taxonomy_terms(conn)
    assert result[("entity_kind", "host")] == eid


def test_get_taxonomy_terms_empty_result(sync: Any) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    assert sync.get_taxonomy_terms(conn) == {}


# ---------------------------------------------------------------------------
# upsert_host — INSERT path
# ---------------------------------------------------------------------------

_EK_ID = uuid.uuid4()
_ENV_ID = uuid.uuid4()
_LC_ID = uuid.uuid4()
_OS_ID = uuid.uuid4()

_TERMS: dict[tuple[str, str], uuid.UUID] = {
    ("entity_kind", "host"): _EK_ID,
    ("environment", "production"): _ENV_ID,
    ("environment", "shared-platform"): uuid.uuid4(),
    ("environment", "development"): uuid.uuid4(),
    ("environment", "staging"): uuid.uuid4(),
    ("lifecycle_status", "active"): _LC_ID,
    ("os_family", "ubuntu"): _OS_ID,
    ("os_family", "debian"): uuid.uuid4(),
}


def test_upsert_host_inserts_new_host(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    conn = MagicMock()
    host: dict[str, Any] = sync.REMAINING_HOSTS[1]  # lxc-postgres-main

    result_id: uuid.UUID | None = sync.upsert_host(conn, host, _TERMS, set())

    assert isinstance(result_id, uuid.UUID)
    # Verify execute was called (INSERT)
    assert conn.execute.call_count >= 1
    captured = capsys.readouterr()
    assert "INSERT" in captured.out


def test_upsert_host_updates_existing_host(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    existing_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (existing_id,)
    host: dict[str, Any] = sync.REMAINING_HOSTS[1]  # lxc-postgres-main

    result_id: uuid.UUID | None = sync.upsert_host(conn, host, _TERMS, {host["host_code"]})

    assert result_id == existing_id
    captured = capsys.readouterr()
    assert "UPDATE" in captured.out


def test_upsert_host_returns_none_when_required_term_missing(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    conn = MagicMock()
    host: dict[str, Any] = sync.REMAINING_HOSTS[1]

    # Only os_family term present — required terms missing
    result_id = sync.upsert_host(conn, host, {("os_family", "ubuntu"): _OS_ID}, set())
    assert result_id is None
    captured = capsys.readouterr()
    assert "ERROR" in captured.out


def test_upsert_host_orchestrator_uses_debian_os_family(sync: Any) -> None:
    """Orchestrator runs Debian, not Ubuntu — os_family must resolve correctly."""
    conn = MagicMock()
    orch: dict[str, Any] = next(h for h in sync.REMAINING_HOSTS if h["host_code"] == "orchestrator")
    debian_id = uuid.uuid4()
    terms: dict[tuple[str, str], uuid.UUID] = {**_TERMS, ("os_family", "debian"): debian_id}
    # Remove ubuntu from terms to ensure it doesn't accidentally match
    terms_no_ubuntu: dict[tuple[str, str], uuid.UUID] = {k: v for k, v in terms.items() if k != ("os_family", "ubuntu")}

    # Orchestrator os_family is "debian" in its definition
    # The script should pick ("os_family", "debian") for it
    result = sync.upsert_host(conn, orch, terms_no_ubuntu, set())
    # If the script correctly reads os_family from the host dict, it won't error
    assert result is not None


# ---------------------------------------------------------------------------
# link_all_unlinked
# ---------------------------------------------------------------------------


def test_link_all_unlinked_links_agent_with_matching_host(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    agent_id = uuid.uuid4()
    host_id = uuid.uuid4()
    conn = MagicMock()
    call_count = [0]

    def side_effect(text_obj: Any, params: dict[str, Any] | None = None) -> MagicMock:
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            mock_result.fetchall.return_value = [(agent_id, "orchestrator")]
        else:
            mock_result.fetchone.return_value = (host_id,)
        return mock_result

    conn.execute.side_effect = side_effect
    sync.link_all_unlinked(conn)

    captured = capsys.readouterr()
    assert "LINKED" in captured.out


def test_link_all_unlinked_skips_when_no_host_record(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    agent_id = uuid.uuid4()
    conn = MagicMock()
    call_count = [0]

    def side_effect(text_obj: Any, params: dict[str, Any] | None = None) -> MagicMock:
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            mock_result.fetchall.return_value = [(agent_id, "dev-local")]
        else:
            mock_result.fetchone.return_value = None
        return mock_result

    conn.execute.side_effect = side_effect
    sync.link_all_unlinked(conn)

    captured = capsys.readouterr()
    assert "SKIP" in captured.out


def test_link_all_unlinked_counts_correctly(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    sync.link_all_unlinked(conn)
    captured = capsys.readouterr()
    assert "Linked: 0/0" in captured.out
