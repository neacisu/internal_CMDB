"""Tests for collectors.fleet_health."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from internalcmdb.collectors.fleet_health import (
    FleetState,
    _host_aliases,
    _normalize_host_token,
    _parse_timestamp,
    build_fleet_state,
    derive_agent_status,
    resolve_host,
)


def _make_host(
    host_id=None,
    host_code="host-001",
    hostname="host-001.local",
    ssh_alias=None,
    fqdn=None,
    observed_hostname=None,
):
    h = MagicMock()
    h.host_id = host_id or uuid.uuid4()
    h.host_code = host_code
    h.hostname = hostname
    h.ssh_alias = ssh_alias
    h.fqdn = fqdn
    h.observed_hostname = observed_hostname
    return h


def _make_agent(
    is_active=True,
    status="online",
    last_heartbeat_at=None,
    enrolled_at=None,
    host_id=None,
    host_code="host-001",
):
    a = MagicMock()
    a.is_active = is_active
    a.status = status
    a.last_heartbeat_at = last_heartbeat_at or datetime.now(UTC).isoformat()
    a.enrolled_at = enrolled_at or datetime.now(UTC).isoformat()
    a.host_id = host_id
    a.host_code = host_code
    return a


# ---------------------------------------------------------------------------
# _normalize_host_token
# ---------------------------------------------------------------------------


def test_normalize_host_token_none():
    assert _normalize_host_token(None) is None


def test_normalize_host_token_empty():
    assert _normalize_host_token("   ") is None


def test_normalize_host_token_strips_lowercases():
    assert _normalize_host_token("  HOST-001  ") == "host-001"


# ---------------------------------------------------------------------------
# _parse_timestamp
# ---------------------------------------------------------------------------


def test_parse_timestamp_none():
    result = _parse_timestamp(None)
    assert result == datetime.min.replace(tzinfo=UTC)


def test_parse_timestamp_valid_iso():
    now = datetime.now(UTC)
    result = _parse_timestamp(now.isoformat())
    assert result.tzinfo is not None


def test_parse_timestamp_naive_gets_utc():
    result = _parse_timestamp("2024-01-01T12:00:00")
    assert result.tzinfo is not None


def test_parse_timestamp_invalid():
    result = _parse_timestamp("not-a-date")
    assert result == datetime.min.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# _host_aliases
# ---------------------------------------------------------------------------


def test_host_aliases_basic():
    host = _make_host(host_code="h-001", hostname="h-001.local", ssh_alias="h-001-ssh")
    aliases = _host_aliases(host)
    assert "h-001" in aliases
    assert "h-001.local" in aliases
    assert "h-001-ssh" in aliases


def test_host_aliases_excludes_none():
    host = _make_host(host_code="h-001", hostname=None)
    aliases = _host_aliases(host)
    assert None not in aliases
    assert "h-001" in aliases


# ---------------------------------------------------------------------------
# derive_agent_status
# ---------------------------------------------------------------------------


def test_derive_agent_status_retired_by_flag():
    assert derive_agent_status(_make_agent(is_active=False)) == "retired"


def test_derive_agent_status_retired_by_status():
    assert derive_agent_status(_make_agent(is_active=True, status="retired")) == "retired"


def test_derive_agent_status_online():
    agent = _make_agent(
        is_active=True,
        status="online",
        last_heartbeat_at=datetime.now(UTC).isoformat(),
    )
    assert derive_agent_status(agent) == "online"


def test_derive_agent_status_offline_no_heartbeat():
    agent = _make_agent(is_active=True, status="online")
    agent.last_heartbeat_at = None
    assert derive_agent_status(agent) == "offline"


def test_derive_agent_status_degraded():
    from internalcmdb.collectors.fleet_health import (  # noqa: PLC0415
        BASE_INTERVAL,
        DEGRADED_MULTIPLIER,
    )

    cutoff = datetime.now(UTC) - timedelta(seconds=BASE_INTERVAL * DEGRADED_MULTIPLIER + 30)
    agent = _make_agent(is_active=True, status="online", last_heartbeat_at=cutoff.isoformat())
    assert derive_agent_status(agent) == "degraded"


def test_derive_agent_status_offline_too_old():
    from internalcmdb.collectors.fleet_health import (  # noqa: PLC0415
        BASE_INTERVAL,
        OFFLINE_MULTIPLIER,
    )

    cutoff = datetime.now(UTC) - timedelta(seconds=BASE_INTERVAL * OFFLINE_MULTIPLIER + 60)
    agent = _make_agent(is_active=True, status="online", last_heartbeat_at=cutoff.isoformat())
    assert derive_agent_status(agent) == "offline"


# ---------------------------------------------------------------------------
# resolve_host
# ---------------------------------------------------------------------------


def test_resolve_host_by_code():
    db = MagicMock()
    host = _make_host(host_code="host-001", hostname="h-001.local")
    db.scalars.return_value.all.return_value = [host]
    result = resolve_host(db, "host-001")
    assert result is host


def test_resolve_host_not_found():
    db = MagicMock()
    db.scalars.return_value.all.return_value = [_make_host(host_code="host-001")]
    assert resolve_host(db, "non-existent") is None


# ---------------------------------------------------------------------------
# build_fleet_state
# ---------------------------------------------------------------------------


def test_build_fleet_state_empty():
    db = MagicMock()
    db.scalars.return_value.all.side_effect = [[], []]
    state = build_fleet_state(db)
    assert isinstance(state, FleetState)
    assert len(state.hosts) == 0
    assert len(state.agents_by_host_id) == 0
    assert len(state.unassigned_agents) == 0


def test_build_fleet_state_matched_agent():
    db = MagicMock()
    host_id = uuid.uuid4()
    host = _make_host(host_id=host_id, host_code="host-001")
    agent = _make_agent(is_active=True, host_id=host_id, host_code="host-001")
    db.scalars.return_value.all.side_effect = [[host], [agent]]
    state = build_fleet_state(db)
    assert host_id in state.agents_by_host_id
    assert len(state.unassigned_agents) == 0


def test_build_fleet_state_unassigned_agent():
    db = MagicMock()
    host = _make_host(host_id=uuid.uuid4(), host_code="host-001")
    agent = _make_agent(is_active=True, host_id=None, host_code="unknown-host")
    db.scalars.return_value.all.side_effect = [[host], [agent]]
    state = build_fleet_state(db)
    assert len(state.unassigned_agents) == 1
