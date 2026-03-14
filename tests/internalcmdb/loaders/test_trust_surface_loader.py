"""Tests for internalcmdb.loaders.trust_surface_loader — pure helpers and mocked load."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.loaders.trust_surface_loader import (
    _ensure_discovery_source,
    _get_host_id_by_code,
    _load_endpoints,
    _load_host,
    _load_term_map,
    _sshd_findings,
    _sshd_risk_level,
    _term,
    load,
)

# ---------------------------------------------------------------------------
# _sshd_findings
# ---------------------------------------------------------------------------


class TestSshdFindings:
    def test_empty_lines_returns_empty(self) -> None:
        assert _sshd_findings([]) == {}

    def test_permit_root_login_yes(self) -> None:
        findings = _sshd_findings(["PermitRootLogin yes"])
        assert findings["permit_root_login"] == "yes"

    def test_permit_root_login_no(self) -> None:
        findings = _sshd_findings(["PermitRootLogin no"])
        assert findings["permit_root_login"] == "no"

    def test_password_authentication_yes(self) -> None:
        findings = _sshd_findings(["PasswordAuthentication yes"])
        assert findings["password_auth"] == "yes"

    def test_password_authentication_no(self) -> None:
        findings = _sshd_findings(["PasswordAuthentication no"])
        assert findings["password_auth"] == "no"

    def test_pubkey_authentication_yes(self) -> None:
        findings = _sshd_findings(["PubkeyAuthentication yes"])
        assert findings["pubkey_auth"] == "yes"

    def test_port_custom(self) -> None:
        findings = _sshd_findings(["Port 2222"])
        assert findings["port"] == "2222"

    def test_multiple_directives(self) -> None:
        lines = [
            "PermitRootLogin no",
            "PasswordAuthentication no",
            "PubkeyAuthentication yes",
            "Port 22",
        ]
        findings = _sshd_findings(lines)
        assert findings["permit_root_login"] == "no"
        assert findings["password_auth"] == "no"
        assert findings["pubkey_auth"] == "yes"
        assert findings["port"] == "22"

    def test_case_insensitive(self) -> None:
        findings = _sshd_findings(["PERMITROOTLOGIN yes"])
        assert findings["permit_root_login"] == "yes"

    def test_comment_lines_ignored(self) -> None:
        findings = _sshd_findings(["# PermitRootLogin yes"])
        assert "permit_root_login" not in findings

    def test_leading_whitespace_stripped(self) -> None:
        findings = _sshd_findings(["  PermitRootLogin no"])
        assert findings["permit_root_login"] == "no"

    def test_unknown_directives_ignored(self) -> None:
        findings = _sshd_findings(["X11Forwarding no"])
        assert "permit_root_login" not in findings


# ---------------------------------------------------------------------------
# _sshd_risk_level
# ---------------------------------------------------------------------------


class TestSshdRiskLevel:
    def test_root_login_yes_and_password_yes_is_high(self) -> None:
        findings = {"permit_root_login": "yes", "password_auth": "yes"}
        assert _sshd_risk_level(findings) == "high"

    def test_root_login_yes_password_no_is_medium(self) -> None:
        findings = {"permit_root_login": "yes", "password_auth": "no"}
        assert _sshd_risk_level(findings) == "medium"

    def test_root_login_no_password_yes_is_medium(self) -> None:
        findings = {"permit_root_login": "no", "password_auth": "yes"}
        assert _sshd_risk_level(findings) == "medium"

    def test_root_login_no_password_no_is_low(self) -> None:
        findings = {"permit_root_login": "no", "password_auth": "no"}
        assert _sshd_risk_level(findings) == "low"

    def test_empty_findings_is_low(self) -> None:
        assert _sshd_risk_level({}) == "low"

    def test_only_root_login_yes_is_medium(self) -> None:
        assert _sshd_risk_level({"permit_root_login": "yes"}) == "medium"

    def test_prohibited_root_mode(self) -> None:
        findings = {"permit_root_login": "prohibit-password"}
        assert _sshd_risk_level(findings) == "low"


# ---------------------------------------------------------------------------
# _term helper
# ---------------------------------------------------------------------------


class TestTermHelperTrust:
    def test_returns_matching_uuid(self) -> None:
        uid = uuid.uuid4()
        term_map = {("entity_kind", "host"): uid}
        assert _term(term_map, "entity_kind", "host") == uid

    def test_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            _term({}, "entity_kind", "nonexistent")

    def test_fallback_used(self) -> None:
        fallback_uid = uuid.uuid4()
        term_map = {("entity_kind", "server"): fallback_uid}
        assert _term(term_map, "entity_kind", "host", fallback="server") == fallback_uid


# ---------------------------------------------------------------------------
# load() with mocked connection
# ---------------------------------------------------------------------------


def _trust_term_map() -> dict[tuple[str, str], uuid.UUID]:
    return {
        ("entity_kind", "host"): uuid.uuid4(),
        ("discovery_source_kind", "trust_surface_audit"): uuid.uuid4(),
        ("collection_run_status", "succeeded"): uuid.uuid4(),
        ("collection_run_status", "failed"): uuid.uuid4(),
        ("observation_status", "confirmed"): uuid.uuid4(),
        ("observation_status", "unknown"): uuid.uuid4(),
        ("risk_level", "high"): uuid.uuid4(),
        ("risk_level", "medium"): uuid.uuid4(),
        ("risk_level", "low"): uuid.uuid4(),
        ("risk_level", "unknown"): uuid.uuid4(),
        ("entity_kind", "evidence_artifact"): uuid.uuid4(),
    }


class TestLoadTrustFunction:
    def test_load_empty_results_completes(self) -> None:
        term_map = _trust_term_map()
        conn = MagicMock()
        audit_data: dict[str, Any] = {"results": {"hosts": [], "endpoints": []}}

        with (
            patch(
                "internalcmdb.loaders.trust_surface_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.trust_surface_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
        ):
            load(conn, audit_data)

    def test_load_empty_term_map_exits(self) -> None:
        conn = MagicMock()
        with (
            patch(
                "internalcmdb.loaders.trust_surface_loader._load_term_map",
                return_value={},
            ),
            pytest.raises(SystemExit),
        ):
            load(conn, {"results": {}})

    def test_load_with_list_results_format(self) -> None:
        term_map = _trust_term_map()
        conn = MagicMock()
        audit_data: dict[str, Any] = {"results": []}

        with (
            patch(
                "internalcmdb.loaders.trust_surface_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.trust_surface_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
        ):
            load(conn, audit_data)

    def test_load_with_host_ok_skipped_if_not_in_registry(self) -> None:
        term_map = _trust_term_map()
        conn = MagicMock()
        audit_data: dict[str, Any] = {
            "results": {
                "hosts": [{"alias": "node1", "ok": True, "data": {}}],
                "endpoints": [],
            }
        }

        with (
            patch(
                "internalcmdb.loaders.trust_surface_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.trust_surface_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
            patch(
                "internalcmdb.loaders.trust_surface_loader._load_host",
                return_value=False,
            ),
            patch(
                "internalcmdb.loaders.trust_surface_loader._load_endpoints",
                return_value=0,
            ),
        ):
            load(conn, audit_data)
            conn.commit.assert_called_once()

    def test_load_with_non_dict_node_skipped(self) -> None:
        term_map = _trust_term_map()
        conn = MagicMock()
        audit_data: dict[str, Any] = {
            "results": {
                "hosts": ["not-a-dict"],
                "endpoints": [],
            }
        }

        with (
            patch(
                "internalcmdb.loaders.trust_surface_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.trust_surface_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
            patch(
                "internalcmdb.loaders.trust_surface_loader._load_endpoints",
                return_value=0,
            ),
        ):
            load(conn, audit_data)


class TestLoadTermMapTrust:
    def test_returns_populated_dict(self) -> None:
        tid = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [("entity_kind", "host", tid)]
        result = _load_term_map(conn)
        assert result == {("entity_kind", "host"): tid}

    def test_empty_returns_empty_dict(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        assert _load_term_map(conn) == {}


class TestGetHostIdByCodeTrust:
    def test_found_returns_uuid(self) -> None:
        hid = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (hid,)
        assert _get_host_id_by_code(conn, "prod-01") == hid

    def test_not_found_returns_none(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        assert _get_host_id_by_code(conn, "unknown") is None


class TestEnsureDiscoverySourceTrust:
    def _tm(self) -> dict[tuple[str, str], uuid.UUID]:
        return {("discovery_source_kind", "trust_surface_audit"): uuid.uuid4()}

    def test_existing_returned(self) -> None:
        source_id = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (source_id,)
        result = _ensure_discovery_source(conn, self._tm())
        assert result == source_id

    def test_new_inserted(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        result = _ensure_discovery_source(conn, self._tm())
        assert conn.execute.call_count >= 2
        assert isinstance(result, uuid.UUID)


class TestLoadHostHelper:
    def _tm(self) -> dict[tuple[str, str], uuid.UUID]:
        return {
            ("entity_kind", "host"): uuid.uuid4(),
            ("observation_status", "observed"): uuid.uuid4(),
            ("evidence_kind", "trust_surface_snapshot"): uuid.uuid4(),
        }

    def test_no_alias_returns_false(self) -> None:
        conn = MagicMock()
        result = _load_host(conn, {"ok": True, "data": {}}, self._tm(), uuid.uuid4())
        assert result is False

    def test_not_ok_returns_false(self) -> None:
        conn = MagicMock()
        result = _load_host(conn, {"alias": "prod-01", "ok": False}, self._tm(), uuid.uuid4())
        assert result is False

    def test_host_not_in_registry_returns_false(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        result = _load_host(
            conn,
            {"alias": "prod-01", "ok": True, "data": {}},
            self._tm(),
            uuid.uuid4(),
        )
        assert result is False

    def test_host_in_registry_returns_true(self) -> None:
        host_id = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (host_id,)
        node: dict[str, Any] = {
            "alias": "prod-01",
            "ok": True,
            "data": {
                "sshd": ["PermitRootLogin no", "PasswordAuthentication no"],
                "secret_paths": [],
                "ssh_dirs": [],
                "certs": [],
            },
        }
        result = _load_host(conn, node, self._tm(), uuid.uuid4())
        assert result is True


class TestLoadEndpointsHelper:
    def _tm(self) -> dict[tuple[str, str], uuid.UUID]:
        return {
            ("entity_kind", "service_exposure"): uuid.uuid4(),
            ("observation_status", "observed"): uuid.uuid4(),
            ("observation_status", "error"): uuid.uuid4(),
        }

    def test_empty_list_returns_zero(self) -> None:
        conn = MagicMock()
        result = _load_endpoints(conn, [], self._tm(), uuid.uuid4())
        assert result == 0

    def test_non_dict_skipped(self) -> None:
        conn = MagicMock()
        result = _load_endpoints(conn, ["not-a-dict"], self._tm(), uuid.uuid4())
        assert result == 0

    def test_ok_endpoint_inserts_fact(self) -> None:
        conn = MagicMock()
        endpoints: list[Any] = [{"endpoint": "https://api.example.com", "ok": True}]
        result = _load_endpoints(conn, endpoints, self._tm(), uuid.uuid4())
        assert result == 1
        conn.execute.assert_called_once()

    def test_refused_error_classified_correctly(self) -> None:
        conn = MagicMock()
        endpoints: list[Any] = [
            {"endpoint": "https://x.com", "ok": False, "error": "connection refused"},
        ]
        assert _load_endpoints(conn, endpoints, self._tm(), uuid.uuid4()) == 1

    def test_timeout_error_classified_correctly(self) -> None:
        conn = MagicMock()
        endpoints: list[Any] = [
            {"endpoint": "https://x.com", "ok": False, "error": "timeout occurred"},
        ]
        assert _load_endpoints(conn, endpoints, self._tm(), uuid.uuid4()) == 1

    def test_tls_error_classified_correctly(self) -> None:
        conn = MagicMock()
        endpoints: list[Any] = [
            {"endpoint": "https://x.com", "ok": False, "error": "tls handshake failed"},
        ]
        assert _load_endpoints(conn, endpoints, self._tm(), uuid.uuid4()) == 1

    def test_unknown_error_classified_as_unknown(self) -> None:
        conn = MagicMock()
        endpoints: list[Any] = [
            {"endpoint": "https://x.com", "ok": False, "error": "some other error"},
        ]
        assert _load_endpoints(conn, endpoints, self._tm(), uuid.uuid4()) == 1

    def test_multiple_endpoints_counted(self) -> None:
        conn = MagicMock()
        endpoints: list[Any] = [
            {"endpoint": "https://a.com", "ok": True},
            {"endpoint": "https://b.com", "ok": False, "error": "refused"},
        ]
        assert _load_endpoints(conn, endpoints, self._tm(), uuid.uuid4()) == 2
