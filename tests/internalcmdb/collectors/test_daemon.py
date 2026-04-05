"""Tests for internalcmdb.collectors.agent.daemon — AgentDaemon."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_daemon(**kwargs):
    defaults = {
        "api_url": "https://api.example.com",
        "host_code": "lxc-test-01",
    }
    defaults.update(kwargs)
    from internalcmdb.collectors.agent.daemon import AgentDaemon
    return AgentDaemon(**defaults)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestAgentDaemonInit:
    def test_agent_daemon_init(self):
        daemon = _make_daemon()

        assert daemon.api_url == "https://api.example.com"
        assert daemon.host_code == "lxc-test-01"
        assert daemon.agent_id is None
        assert daemon.api_token is None

    def test_agent_daemon_init_with_credentials(self):
        daemon = _make_daemon(
            agent_id="agent-abc-123",
            api_token="tok-secret",
            agent_version="2.0.0",
        )

        assert daemon.agent_id == "agent-abc-123"
        assert daemon.api_token == "tok-secret"
        assert daemon.agent_version == "2.0.0"

    def test_agent_daemon_default_verify_ssl(self):
        daemon = _make_daemon()
        assert daemon.verify_ssl is True

    def test_agent_daemon_default_ca_bundle(self):
        daemon = _make_daemon()
        assert daemon.ca_bundle is None

    def test_agent_daemon_default_max_buffer_size(self):
        daemon = _make_daemon()
        assert daemon.max_buffer_size == 1000


# ---------------------------------------------------------------------------
# _auth_headers
# ---------------------------------------------------------------------------


class TestAuthHeaders:
    def test_auth_headers_empty_without_token(self):
        daemon = _make_daemon()
        assert daemon._auth_headers() == {}

    def test_auth_headers_empty_without_agent_id(self):
        daemon = _make_daemon(api_token="tok-secret")
        assert daemon._auth_headers() == {}

    def test_auth_headers_with_credentials(self):
        daemon = _make_daemon(agent_id="agent-123", api_token="tok-abc")
        headers = daemon._auth_headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer tok-abc"
        assert "X-Agent-ID" in headers
        assert headers["X-Agent-ID"] == "agent-123"

    def test_auth_headers_both_required(self):
        daemon_no_id = _make_daemon(api_token="tok-abc")
        daemon_no_token = _make_daemon(agent_id="agent-123")

        assert daemon_no_id._auth_headers() == {}
        assert daemon_no_token._auth_headers() == {}


# ---------------------------------------------------------------------------
# _ssl_verify
# ---------------------------------------------------------------------------


class TestSslVerify:
    def test_ssl_verify_with_ca_bundle(self):
        daemon = _make_daemon(
            ca_bundle="/etc/ssl/certs/my-ca.crt",
            verify_ssl=True,
        )
        assert daemon._ssl_verify == "/etc/ssl/certs/my-ca.crt"

    def test_ssl_verify_default(self):
        daemon = _make_daemon()
        assert daemon._ssl_verify is True

    def test_ssl_verify_disabled(self):
        daemon = _make_daemon(verify_ssl=False)
        assert daemon._ssl_verify is False

    def test_ssl_verify_ca_bundle_with_verify_false(self):
        daemon = _make_daemon(
            ca_bundle="/etc/ssl/certs/my-ca.crt",
            verify_ssl=False,
        )
        assert daemon._ssl_verify is False


# ---------------------------------------------------------------------------
# COLLECTOR_MODULES and COLLECTOR_TO_TIER
# ---------------------------------------------------------------------------


class TestCollectorModules:
    def test_collector_modules_count(self):
        from internalcmdb.collectors.agent.daemon import COLLECTOR_MODULES
        assert len(COLLECTOR_MODULES) >= 19

    def test_collector_modules_required_keys(self):
        from internalcmdb.collectors.agent.daemon import COLLECTOR_MODULES
        required = {
            "heartbeat", "system_vitals", "docker_state", "gpu_state",
            "disk_state", "network_state", "service_health", "container_resources",
        }
        for key in required:
            assert key in COLLECTOR_MODULES, f"Missing collector: {key}"

    def test_collector_to_tier_populated(self):
        from internalcmdb.collectors.agent.daemon import COLLECTOR_TO_TIER
        assert len(COLLECTOR_TO_TIER) > 0

    def test_collector_to_tier_has_heartbeat(self):
        from internalcmdb.collectors.agent.daemon import COLLECTOR_TO_TIER
        assert "heartbeat" in COLLECTOR_TO_TIER

    def test_collector_to_tier_values_are_strings(self):
        from internalcmdb.collectors.agent.daemon import COLLECTOR_TO_TIER
        for key, val in COLLECTOR_TO_TIER.items():
            assert isinstance(val, str), f"Tier for {key} is not a string"


# ---------------------------------------------------------------------------
# PendingSnapshot
# ---------------------------------------------------------------------------


class TestPendingSnapshot:
    def test_pending_snapshot_creation(self):
        from internalcmdb.collectors.agent.daemon import PendingSnapshot
        snap = PendingSnapshot(
            snapshot_kind="heartbeat",
            tier_code="T1",
            payload={"uptime_seconds": 1234.5},
            payload_hash="abc123",
            collected_at="2024-01-01T00:00:00+00:00",
        )

        assert snap.snapshot_kind == "heartbeat"
        assert snap.tier_code == "T1"
        assert snap.payload == {"uptime_seconds": 1234.5}
        assert snap.payload_hash == "abc123"
        assert snap.collected_at == "2024-01-01T00:00:00+00:00"

    def test_pending_snapshot_is_dataclass(self):
        import dataclasses
        from internalcmdb.collectors.agent.daemon import PendingSnapshot
        assert dataclasses.is_dataclass(PendingSnapshot)

    def test_pending_snapshot_payload_is_dict(self):
        from internalcmdb.collectors.agent.daemon import PendingSnapshot
        snap = PendingSnapshot(
            snapshot_kind="disk_state",
            tier_code="T3",
            payload={"disks": [], "total": 0},
            payload_hash="deadbeef",
            collected_at="2024-01-01T00:00:00+00:00",
        )
        assert isinstance(snap.payload, dict)
