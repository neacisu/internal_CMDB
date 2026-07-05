"""Tests for scripts/sync_hz118_lxc.py.

Strategy:
  - Load the script as an importlib module with a mocked environment so module-level
    ``load_dotenv`` and ``create_engine`` calls don't touch the real database.
  - Test each pure-logic helper in isolation using MagicMock SQLAlchemy connections.
  - Cover INSERT path, UPDATE path, missing-term guard, link logic, and constants.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixture: load the script as a module with mocked DB/env
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).parents[3] / "scripts" / "sync_hz118_lxc.py"


# Clearly-named test-only placeholder; value carries no real access rights.
_TEST_DB_PASSWORD = "test"  # NOSONAR


@pytest.fixture(scope="module")
def sync(tmp_path_factory: pytest.TempPathFactory) -> types.ModuleType:
    """Import sync_hz118_lxc with no real DB or .env file required."""
    mock_env = {
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": _TEST_DB_PASSWORD,
        "POSTGRES_DB": "testdb",
        "POSTGRES_SYNC_HOST": "127.0.0.1",
        "POSTGRES_SYNC_PORT": "5432",
    }
    mock_engine = MagicMock()

    # Snapshot keys before deletion to avoid mutating the dict during iteration.
    stale = {k for k in sys.modules if "sync_hz118_lxc" in k}
    for key in stale:
        del sys.modules[key]

    with (
        patch.dict(os.environ, mock_env, clear=False),
        patch("dotenv.load_dotenv"),
        patch("sqlalchemy.create_engine", return_value=mock_engine),
    ):
        spec = importlib.util.spec_from_file_location("sync_hz118_lxc", _SCRIPT_PATH)
        assert spec is not None, f"Cannot locate module spec for {_SCRIPT_PATH}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod


# ---------------------------------------------------------------------------
# Constants integrity
# ---------------------------------------------------------------------------


def test_hz118_host_code_is_correct(sync: Any) -> None:
    assert sync.HZ118_HOST_CODE == "hz.118"


def test_os_constants_are_correct_version_strings(sync: Any) -> None:
    assert "20.04" in sync.OS_UBUNTU_2004_LTS
    assert "22.04" in sync.OS_UBUNTU_2204_LTS


def test_python_deadsnakes_constant_contains_version(sync: Any) -> None:
    assert "3.14" in sync.PYTHON_DEADSNAKES_JAMMY
    assert "deadsnakes" in sync.PYTHON_DEADSNAKES_JAMMY


def test_lxc_hosts_has_four_entries(sync: Any) -> None:
    assert len(sync.LXC_HOSTS) == 4


def test_lxc_hosts_host_codes_are_unique(sync: Any) -> None:
    codes: list[str] = [h["host_code"] for h in sync.LXC_HOSTS]
    assert len(codes) == len(set(codes))


def test_lxc_hosts_constant_references_used(sync: Any) -> None:
    """LXC 101-103 must reference OS_UBUNTU_2204_LTS and PYTHON_DEADSNAKES_JAMMY."""
    for h in sync.LXC_HOSTS:
        if h["lxc_id"] in (101, 102, 103):
            assert h["os_version_text"] == sync.OS_UBUNTU_2204_LTS
            assert h["python_version"] == sync.PYTHON_DEADSNAKES_JAMMY
    lxc100: dict[str, Any] = next(h for h in sync.LXC_HOSTS if h["lxc_id"] == 100)
    assert lxc100["os_version_text"] == sync.OS_UBUNTU_2004_LTS


# ---------------------------------------------------------------------------
# get_taxonomy_terms
# ---------------------------------------------------------------------------


def test_get_taxonomy_terms_returns_dict_keyed_by_domain_term(sync: Any) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        ("entity_kind", "host", uuid.UUID("00000000-0000-0000-0000-000000000001")),
        ("environment", "production", uuid.UUID("00000000-0000-0000-0000-000000000002")),
    ]
    result: dict[tuple[str, str], uuid.UUID] = sync.get_taxonomy_terms(conn)
    assert result[("entity_kind", "host")] == uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert result[("environment", "production")] == uuid.UUID("00000000-0000-0000-0000-000000000002")


def test_get_taxonomy_terms_empty_db_returns_empty_dict(sync: Any) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    assert sync.get_taxonomy_terms(conn) == {}


# ---------------------------------------------------------------------------
# _resolve_upsert_terms
# ---------------------------------------------------------------------------

_EK_ID = uuid.uuid4()
_ENV_ID = uuid.uuid4()
_LC_ID = uuid.uuid4()
_OS_ID = uuid.uuid4()

_FULL_TERMS: dict[tuple[str, str], uuid.UUID] = {
    ("entity_kind", "host"): _EK_ID,
    ("environment", "production"): _ENV_ID,
    ("lifecycle_status", "active"): _LC_ID,
    ("os_family", "ubuntu"): _OS_ID,
}


def test_resolve_upsert_terms_returns_tuple_when_all_present(sync: Any) -> None:
    result: tuple[Any, ...] | None = sync._resolve_upsert_terms(_FULL_TERMS)
    assert result is not None
    ek, env, lc, os_fam = result
    assert ek == _EK_ID
    assert env == _ENV_ID
    assert lc == _LC_ID
    assert os_fam == _OS_ID


def test_resolve_upsert_terms_returns_none_when_entity_kind_missing(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    terms = {k: v for k, v in _FULL_TERMS.items() if k[0] != "entity_kind"}
    result = sync._resolve_upsert_terms(terms)
    assert result is None
    captured = capsys.readouterr()
    assert "ERROR" in captured.out


def test_resolve_upsert_terms_returns_none_when_environment_missing(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    terms = {k: v for k, v in _FULL_TERMS.items() if k[0] != "environment"}
    result = sync._resolve_upsert_terms(terms)
    assert result is None


def test_resolve_upsert_terms_returns_none_when_lifecycle_missing(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    terms = {k: v for k, v in _FULL_TERMS.items() if k[0] != "lifecycle_status"}
    result = sync._resolve_upsert_terms(terms)
    assert result is None


def test_resolve_upsert_terms_falls_back_to_prod(sync: Any) -> None:
    """Falls back to ('environment', 'prod') when 'production' is absent."""
    prod_id = uuid.uuid4()
    terms = {**_FULL_TERMS, ("environment", "prod"): prod_id}
    del terms[("environment", "production")]  # type: ignore[arg-type]
    result = sync._resolve_upsert_terms(terms)  # type: ignore[arg-type]
    assert result is not None
    assert result[1] == prod_id


def test_resolve_upsert_terms_os_family_can_be_none(sync: Any) -> None:
    """os_family is optional — caller handles None gracefully at INSERT."""
    terms = {k: v for k, v in _FULL_TERMS.items() if k[0] != "os_family"}
    result = sync._resolve_upsert_terms(terms)
    assert result is not None
    assert result[3] is None


# ---------------------------------------------------------------------------
# _build_lxc_meta
# ---------------------------------------------------------------------------


def test_build_lxc_meta_contains_required_keys(sync: Any) -> None:
    from datetime import datetime, timezone

    lxc: dict[str, Any] = sync.LXC_HOSTS[0]
    ts = datetime(2026, 4, 13, 0, 0, 0, tzinfo=timezone.utc)
    raw: str = sync._build_lxc_meta(lxc, ts)
    meta = json.loads(raw)
    assert meta["lxc_id"] == lxc["lxc_id"]
    assert meta["parent_host"] == "hz.118"
    assert meta["proxmox_standalone"] is True
    assert meta["agent_enrolled"] is True
    assert "2026-04-13" in meta["agent_enrolled_at"]


# ---------------------------------------------------------------------------
# _exec_insert_host
# ---------------------------------------------------------------------------


def test_exec_insert_host_calls_execute_with_insert_sql(sync: Any) -> None:
    conn = MagicMock()
    conn.execute.return_value = MagicMock()
    lxc: dict[str, Any] = sync.LXC_HOSTS[0]
    term_ids = (_EK_ID, _ENV_ID, _LC_ID, _OS_ID)
    meta_str = json.dumps({"test": True})

    new_id: uuid.UUID = sync._exec_insert_host(conn, lxc, term_ids, meta_str)

    assert isinstance(new_id, uuid.UUID)
    assert conn.execute.call_count == 1
    sql_call = conn.execute.call_args
    # The second argument is the params dict
    params: dict[str, Any] = sql_call[0][1]
    assert params["code"] == lxc["host_code"]
    assert params["ek"] == _EK_ID
    assert params["env"] == _ENV_ID
    assert params["hyp"] is False


# ---------------------------------------------------------------------------
# _exec_update_host
# ---------------------------------------------------------------------------


def test_exec_update_host_returns_existing_id_and_calls_update(sync: Any) -> None:
    existing_id = uuid.uuid4()
    conn = MagicMock()
    # First call: SELECT host_id
    conn.execute.return_value.fetchone.return_value = (existing_id,)
    lxc: dict[str, Any] = sync.LXC_HOSTS[1]
    meta_str = json.dumps({"test": True})

    returned_id: uuid.UUID = sync._exec_update_host(conn, lxc, meta_str)

    assert returned_id == existing_id
    # Two execute calls: SELECT + UPDATE
    assert conn.execute.call_count == 2


# ---------------------------------------------------------------------------
# upsert_hosts — INSERT path
# ---------------------------------------------------------------------------


def test_upsert_hosts_inserts_all_four_when_no_existing(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    conn = MagicMock()
    # SELECT for _exec_update_host (not called on INSERT path)  
    conn.execute.return_value.fetchone.return_value = None
    # _resolve_upsert_terms calls no DB methods — uses terms dict

    result: dict[str, uuid.UUID] = sync.upsert_hosts(conn, _FULL_TERMS, set())

    assert len(result) == 4
    for h in sync.LXC_HOSTS:
        assert h["host_code"] in result
    captured = capsys.readouterr()
    assert "INSERT" in captured.out


def test_upsert_hosts_updates_when_code_already_exists(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    existing_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (existing_id,)

    existing: set[str] = {h["host_code"] for h in sync.LXC_HOSTS}
    result: dict[str, uuid.UUID] = sync.upsert_hosts(conn, _FULL_TERMS, existing)

    assert len(result) == 4
    for val in result.values():
        assert val == existing_id
    captured = capsys.readouterr()
    assert "UPDATE" in captured.out


def test_upsert_hosts_returns_empty_when_terms_missing(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    conn = MagicMock()
    result: dict[str, uuid.UUID] = sync.upsert_hosts(conn, {}, set())
    assert result == {}
    captured = capsys.readouterr()
    assert "ERROR" in captured.out


# ---------------------------------------------------------------------------
# link_agents
# ---------------------------------------------------------------------------


def test_link_agents_updates_host_id_for_unlinked_agent(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    host_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        (agent_id, None, "online", None)
    ]
    host_map: dict[str, uuid.UUID] = {sync.LXC_HOSTS[0]["host_code"]: host_id}

    sync.link_agents(conn, host_map)

    # The agent was unlinked (current_host_id=None ≠ host_id) → UPDATE must execute.
    # conn.execute is called at minimum twice: SELECT agents + UPDATE.
    assert conn.execute.call_count >= 2
    captured = capsys.readouterr()
    assert "LINKED" in captured.out


def test_link_agents_skips_when_no_host_id_in_map(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    conn = MagicMock()
    # Empty host_map → all LXCs skipped
    sync.link_agents(conn, {})
    captured = capsys.readouterr()
    assert "SKIP" in captured.out


def test_link_agents_skips_when_no_agents_in_db(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    host_map: dict[str, uuid.UUID] = {sync.LXC_HOSTS[0]["host_code"]: uuid.uuid4()}

    sync.link_agents(conn, host_map)
    captured = capsys.readouterr()
    assert "WARN" in captured.out


# ---------------------------------------------------------------------------
# link_all_unlinked_agents
# ---------------------------------------------------------------------------


def test_link_all_unlinked_agents_links_when_host_exists(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    agent_id = uuid.uuid4()
    host_id = uuid.uuid4()
    conn = MagicMock()
    # First execute call: fetch unlinked agents
    # Subsequent calls: fetch host_id rows or execute UPDATE
    call_count = [0]

    def side_effect(text_obj: Any, params: dict[str, Any] | None = None) -> MagicMock:
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            # Unlinked agents query
            mock_result.fetchall.return_value = [(agent_id, "lxc-hz118-traktors", "online")]
        elif call_count[0] == 2:
            # SELECT host_id query
            mock_result.fetchone.return_value = (host_id,)
        return mock_result

    conn.execute.side_effect = side_effect
    sync.link_all_unlinked_agents(conn)

    captured = capsys.readouterr()
    assert "LINKED" in captured.out


def test_link_all_unlinked_agents_skips_when_no_host_record(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    agent_id = uuid.uuid4()
    conn = MagicMock()
    call_count = [0]

    def side_effect(text_obj: Any, params: dict[str, Any] | None = None) -> MagicMock:
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            mock_result.fetchall.return_value = [(agent_id, "dev-local", "offline")]
        else:
            mock_result.fetchone.return_value = None
        return mock_result

    conn.execute.side_effect = side_effect
    sync.link_all_unlinked_agents(conn)

    captured = capsys.readouterr()
    assert "SKIP" in captured.out


# ---------------------------------------------------------------------------
# _audit_* helpers — structural / output shape
# ---------------------------------------------------------------------------


def _build_host_row(
    code: str = "hz.test",
    public_ip: str | None = "1.2.3.4",
    is_docker: bool = False,
    is_hyp: bool = False,
) -> tuple[Any, ...]:
    return (code, "hostname", public_ip, None, "Ubuntu 22.04", is_docker, is_hyp, None)


def test_audit_hosts_returns_existing_codes_and_host_id_map(sync: Any) -> None:
    host_id = uuid.uuid4()
    conn = MagicMock()
    call_count = [0]

    def side_effect(text_obj: Any, params: dict[str, Any] | None = None) -> MagicMock:
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            mock_result.fetchall.return_value = [_build_host_row("hz.test")]
        else:
            mock_result.fetchall.return_value = [("hz.test", host_id)]
        return mock_result

    conn.execute.side_effect = side_effect
    existing: set[str]
    id_map: dict[str, uuid.UUID]
    existing, id_map = sync._audit_hosts(conn)
    assert "hz.test" in existing
    assert id_map["hz.test"] == host_id


def test_audit_hosts_entity_type_hypervisor(sync: Any, capsys: pytest.CaptureFixture[str]) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        _build_host_row(is_hyp=True),
        _build_host_row(code="d1", is_docker=True),
        _build_host_row(code="h1"),
    ]
    sync._audit_hosts(conn)
    captured = capsys.readouterr()
    assert "hypervisor" in captured.out
    assert "docker" in captured.out
    assert "host" in captured.out
