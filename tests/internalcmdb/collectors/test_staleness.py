"""Tests for collectors.staleness — check_staleness."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
from internalcmdb.collectors.staleness import check_staleness


def _make_agent(status="online", host_code="hz-01"):
    agent = MagicMock()
    agent.agent_id = "agent-001"
    agent.host_code = host_code
    agent.status = status
    return agent


def _db(agents):
    db = MagicMock()
    db.scalars.return_value.all.return_value = agents
    db.commit = MagicMock()
    return db


def test_check_staleness_empty_agents():
    db = _db([])
    counts = check_staleness(db)
    assert counts == {"degraded": 0, "offline": 0, "recovered": 0}
    db.commit.assert_called_once()


def test_check_staleness_agent_becomes_degraded():
    agent = _make_agent(status="online")
    db = _db([agent])
    with patch("internalcmdb.collectors.staleness.derive_agent_status", return_value="degraded"):
        counts = check_staleness(db)
    assert counts["degraded"] == 1
    assert agent.status == "degraded"


def test_check_staleness_agent_becomes_offline():
    agent = _make_agent(status="online")
    db = _db([agent])
    with patch("internalcmdb.collectors.staleness.derive_agent_status", return_value="offline"):
        counts = check_staleness(db)
    assert counts["offline"] == 1


def test_check_staleness_agent_recovers():
    agent = _make_agent(status="degraded")
    db = _db([agent])
    with patch("internalcmdb.collectors.staleness.derive_agent_status", return_value="online"):
        counts = check_staleness(db)
    assert counts["recovered"] == 1


def test_check_staleness_no_status_change():
    agent = _make_agent(status="online")
    db = _db([agent])
    with patch("internalcmdb.collectors.staleness.derive_agent_status", return_value="online"):
        counts = check_staleness(db)
    assert counts == {"degraded": 0, "offline": 0, "recovered": 0}


def test_check_staleness_commits_even_no_changes():
    db = _db([])
    check_staleness(db)
    db.commit.assert_called_once()


def test_check_staleness_multiple_agents():
    a1 = _make_agent("online", "hz-01")
    a2 = _make_agent("online", "hz-02")
    a3 = _make_agent("degraded", "hz-03")
    db = _db([a1, a2, a3])

    def mock_status(agent):
        if agent.host_code == "hz-01":
            return "degraded"
        if agent.host_code == "hz-02":
            return "offline"
        if agent.host_code == "hz-03":
            return "online"
        return agent.status

    with patch("internalcmdb.collectors.staleness.derive_agent_status", side_effect=mock_status):
        counts = check_staleness(db)
    assert counts["degraded"] == 1
    assert counts["offline"] == 1
    assert counts["recovered"] == 1
