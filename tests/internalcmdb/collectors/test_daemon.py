"""Tests for internalcmdb.collectors.agent.daemon — AgentDaemon."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_daemon(**kwargs):
    defaults = {
        "api_url": "https://api.example.com",
        "host_code": "lxc-test-01",
    }
    defaults.update(kwargs)
    from internalcmdb.collectors.agent.daemon import AgentDaemon  # noqa: PLC0415

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
        from internalcmdb.collectors.agent.daemon import COLLECTOR_MODULES  # noqa: PLC0415

        assert len(COLLECTOR_MODULES) >= 19

    def test_collector_modules_required_keys(self):
        from internalcmdb.collectors.agent.daemon import COLLECTOR_MODULES  # noqa: PLC0415

        required = {
            "heartbeat",
            "system_vitals",
            "docker_state",
            "gpu_state",
            "disk_state",
            "network_state",
            "service_health",
            "container_resources",
        }
        for key in required:
            assert key in COLLECTOR_MODULES, f"Missing collector: {key}"

    def test_collector_to_tier_populated(self):
        from internalcmdb.collectors.agent.daemon import COLLECTOR_TO_TIER  # noqa: PLC0415

        assert len(COLLECTOR_TO_TIER) > 0

    def test_collector_to_tier_has_heartbeat(self):
        from internalcmdb.collectors.agent.daemon import COLLECTOR_TO_TIER  # noqa: PLC0415

        assert "heartbeat" in COLLECTOR_TO_TIER

    def test_collector_to_tier_values_are_strings(self):
        from internalcmdb.collectors.agent.daemon import COLLECTOR_TO_TIER  # noqa: PLC0415

        for key, val in COLLECTOR_TO_TIER.items():
            assert isinstance(val, str), f"Tier for {key} is not a string"


# ---------------------------------------------------------------------------
# PendingSnapshot
# ---------------------------------------------------------------------------


class TestPendingSnapshot:
    def test_pending_snapshot_creation(self):
        from internalcmdb.collectors.agent.daemon import PendingSnapshot  # noqa: PLC0415

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
        import dataclasses  # noqa: PLC0415

        from internalcmdb.collectors.agent.daemon import PendingSnapshot  # noqa: PLC0415

        assert dataclasses.is_dataclass(PendingSnapshot)

    def test_pending_snapshot_payload_is_dict(self):
        from internalcmdb.collectors.agent.daemon import PendingSnapshot  # noqa: PLC0415

        snap = PendingSnapshot(
            snapshot_kind="disk_state",
            tier_code="T3",
            payload={"disks": [], "total": 0},
            payload_hash="deadbeef",
            collected_at="2024-01-01T00:00:00+00:00",
        )
        assert isinstance(snap.payload, dict)


# ---------------------------------------------------------------------------
# _run_subprocess — static method; use check=False so non-zero exit is returned
# ---------------------------------------------------------------------------


class TestRunSubprocess:
    def test_success_exit_zero(self):
        from internalcmdb.collectors.agent.daemon import AgentDaemon  # noqa: PLC0415

        result = AgentDaemon._run_subprocess("echo hello", 10)
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]
        assert result["stderr"] == ""

    def test_nonzero_exit_code_still_returns_result(self):
        """check=False means a non-zero exit must NOT raise — exit_code is captured."""
        from internalcmdb.collectors.agent.daemon import AgentDaemon  # noqa: PLC0415

        result = AgentDaemon._run_subprocess("false", 10)
        assert result["exit_code"] == 1
        assert "stdout" in result
        assert "stderr" in result
        assert "error" not in result

    def test_timeout_returns_error_dict(self):
        from internalcmdb.collectors.agent.daemon import AgentDaemon  # noqa: PLC0415

        result = AgentDaemon._run_subprocess("sleep 60", timeout=0)
        assert "error" in result
        assert "timed out" in result["error"].lower()
        assert result["exit_code"] == -1

    def test_command_not_found_returns_error_dict(self):
        from internalcmdb.collectors.agent.daemon import AgentDaemon  # noqa: PLC0415

        result = AgentDaemon._run_subprocess("__cmd_that_does_not_exist__", 5)
        assert "error" in result
        assert result["exit_code"] == -1

    def test_output_is_captured(self):
        from internalcmdb.collectors.agent.daemon import AgentDaemon  # noqa: PLC0415

        result = AgentDaemon._run_subprocess("echo stderr >&2; echo stdout", 10)
        assert result["exit_code"] == 0
        assert "stdout" in result
        assert "stderr" in result

    def test_stdout_truncated_at_64kb(self):
        """Output exceeding 64 KiB must be truncated to avoid memory exhaustion."""
        large_output = "x" * 70_000
        mock_result = MagicMock()
        mock_result.stdout = large_output
        mock_result.stderr = ""
        mock_result.returncode = 0

        from internalcmdb.collectors.agent.daemon import AgentDaemon  # noqa: PLC0415

        with patch("subprocess.run", return_value=mock_result):
            result = AgentDaemon._run_subprocess("echo x", 10)

        assert len(result["stdout"]) == 65_536
        assert result["exit_code"] == 0

    def test_uses_check_false(self):
        """subprocess.run must be called with check=False (PLW1510 compliance)."""
        from internalcmdb.collectors.agent.daemon import AgentDaemon  # noqa: PLC0415

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="ok", stderr="", returncode=0
            )
            AgentDaemon._run_subprocess("echo ok", 5)

        call_kwargs = mock_run.call_args[1] if mock_run.call_args else {}
        # check= can be positional or keyword; easiest to check the keyword dict
        assert call_kwargs.get("check") is False, (
            "subprocess.run must pass check=False to satisfy PLW1510"
        )


# ---------------------------------------------------------------------------
# _handle_command — validates HMAC, dispatches execution
# ---------------------------------------------------------------------------


def _make_valid_command(
    daemon, command_id: str, command_type: str, payload: dict
) -> str:
    """Build a valid signed command JSON string for a daemon."""
    payload_json = json.dumps(payload, sort_keys=True)
    sig = hmac.new(
        daemon.api_token.encode(),
        f"{command_id}:{payload_json}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return json.dumps({
        "command_id": command_id,
        "command_type": command_type,
        "payload": payload,
        "timeout": 30,
        "signature": sig,
    })


class TestHandleCommand:
    def test_invalid_json_is_rejected_gracefully(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        # Must not raise, must log warning and return
        asyncio.run(daemon._handle_command("not-json-at-all"))

    def test_no_api_token_rejects_command(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        daemon.agent_id = "agent-001"
        daemon.api_token = None  # no token

        cmd_json = json.dumps({
            "command_id": "cmd-001",
            "command_type": "service_status",
            "payload": {},
            "timeout": 30,
            "signature": "irrelevant",
        })

        with patch.object(daemon, "_send_command_result", new_callable=AsyncMock) as mock_send:
            asyncio.run(daemon._handle_command(cmd_json))

        mock_send.assert_called_once()
        call_result = mock_send.call_args[0][1]
        assert "error" in call_result
        assert call_result["exit_code"] == -1

    def test_missing_signature_rejects_command(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon(agent_id="agent-001", api_token="tok-secret")

        cmd_json = json.dumps({
            "command_id": "cmd-002",
            "command_type": "service_status",
            "payload": {},
            "timeout": 30,
            "signature": "",  # empty signature
        })

        with patch.object(daemon, "_send_command_result", new_callable=AsyncMock) as mock_send:
            asyncio.run(daemon._handle_command(cmd_json))

        mock_send.assert_called_once()
        result = mock_send.call_args[0][1]
        assert "HMAC" in result["error"]

    def test_wrong_signature_rejects_command(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon(agent_id="agent-001", api_token="tok-secret")

        cmd_json = json.dumps({
            "command_id": "cmd-003",
            "command_type": "service_status",
            "payload": {},
            "timeout": 30,
            "signature": "deadbeefdeadbeef" * 4,  # wrong hex value
        })

        with patch.object(daemon, "_send_command_result", new_callable=AsyncMock) as mock_send:
            asyncio.run(daemon._handle_command(cmd_json))

        mock_send.assert_called_once()
        result = mock_send.call_args[0][1]
        assert "HMAC verification failed" in result["error"]

    def test_valid_command_dispatches_and_sends_result(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon(agent_id="agent-001", api_token="tok-secret")
        raw_msg = _make_valid_command(
            daemon, "cmd-004", "docker_inspect", {"container": "myapp"}
        )

        mock_execute = AsyncMock(return_value={"stdout": '{"Id": "abc"}', "exit_code": 0})
        with (
            patch.object(daemon, "_execute_command", mock_execute),
            patch.object(daemon, "_send_command_result", new_callable=AsyncMock) as mock_send,
        ):
            asyncio.run(daemon._handle_command(raw_msg))

        mock_execute.assert_called_once_with(
            "docker_inspect",
            {"container": "myapp", "_subprocess_timeout": 30},
        )
        mock_send.assert_called_once()
        call_result = mock_send.call_args[0][1]
        assert "duration_ms" in call_result


# ---------------------------------------------------------------------------
# _execute_command — dispatch table
# ---------------------------------------------------------------------------


class TestExecuteCommand:
    def test_unknown_command_type_returns_error(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._execute_command("unknown_cmd", {}))
        assert "error" in result
        assert "unknown_cmd" in result["error"]
        assert result["exit_code"] == -1

    def test_run_diagnostic_dispatches_correctly(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        mock_diag = AsyncMock(return_value={"stdout": "ok", "exit_code": 0})
        with patch.object(daemon, "_cmd_run_diagnostic", mock_diag):
            asyncio.run(daemon._execute_command("run_diagnostic", {"command": "uptime"}))
        mock_diag.assert_called_once()

    def test_read_file_dispatches_correctly(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        mock_rf = AsyncMock(return_value={"stdout": "content", "exit_code": 0})
        with patch.object(daemon, "_cmd_read_file", mock_rf):
            asyncio.run(daemon._execute_command("read_file", {"path": "/etc/nginx/nginx.conf"}))
        mock_rf.assert_called_once()

    def test_service_status_dispatches_correctly(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        mock_ss = AsyncMock(return_value={"stdout": "active", "exit_code": 0})
        with patch.object(daemon, "_cmd_service_status", mock_ss):
            asyncio.run(daemon._execute_command("service_status", {"service": "nginx"}))
        mock_ss.assert_called_once()

    def test_docker_inspect_dispatches_correctly(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        mock_di = AsyncMock(return_value={"stdout": '{}', "exit_code": 0})
        with patch.object(daemon, "_cmd_docker_inspect", mock_di):
            asyncio.run(daemon._execute_command("docker_inspect", {"container": "app"}))
        mock_di.assert_called_once()


# ---------------------------------------------------------------------------
# _cmd_run_diagnostic — allowlist enforcement
# ---------------------------------------------------------------------------


class TestCmdRunDiagnostic:
    def test_allowlisted_command_executes(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        with (
            patch.object(
                daemon,
                "_run_subprocess",
                return_value={"stdout": "", "stderr": "", "exit_code": 0},
            ),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value={"stdout": "ok", "exit_code": 0}
            )
            result = asyncio.run(daemon._cmd_run_diagnostic({"command": "uptime"}))
        assert result["exit_code"] == 0

    def test_non_allowlisted_command_rejected(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._cmd_run_diagnostic({"command": "rm -rf /"}))
        assert "error" in result
        assert "allowlist" in result["error"]
        assert result["exit_code"] == -1

    def test_empty_command_rejected(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._cmd_run_diagnostic({"command": ""}))
        assert "error" in result
        assert result["exit_code"] == -1


# ---------------------------------------------------------------------------
# _cmd_read_file — path allowlist, traversal, file not found
# ---------------------------------------------------------------------------


class TestCmdReadFile:
    def test_allowlisted_path_reads_file(self, tmp_path):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        tmp_file = tmp_path / "sshd_config"
        tmp_file.write_text("PermitRootLogin no")

        # Override the allowlist to include our tmp path for this test
        daemon._COMMAND_ALLOWLIST["read_file"].append(str(tmp_path) + "/")
        result = asyncio.run(daemon._cmd_read_file({"path": str(tmp_file)}))
        assert result["exit_code"] == 0
        assert "PermitRootLogin" in result["stdout"]

    def test_non_allowlisted_path_rejected(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._cmd_read_file({"path": "/root/.ssh/id_rsa"}))
        assert "error" in result
        assert result["exit_code"] == -1

    def test_path_traversal_blocked(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._cmd_read_file({"path": "/etc/ssh/../shadow"}))
        assert "error" in result
        assert "traversal" in result["error"].lower() or "allowlist" in result["error"].lower()

    def test_file_not_found_returns_error(self, tmp_path):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        daemon._COMMAND_ALLOWLIST["read_file"].append(str(tmp_path) + "/")
        result = asyncio.run(
            daemon._cmd_read_file({"path": str(tmp_path / "does_not_exist.conf")})
        )
        assert "error" in result
        assert result["exit_code"] == 1


# ---------------------------------------------------------------------------
# _cmd_service_status — service name validation
# ---------------------------------------------------------------------------


class TestCmdServiceStatus:
    def test_valid_service_name_dispatches(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        mock_diag = AsyncMock(return_value={"stdout": "active", "exit_code": 0})
        with patch.object(daemon, "_cmd_run_diagnostic", mock_diag):
            asyncio.run(daemon._cmd_service_status({"service": "nginx"}))
        mock_diag.assert_called_once()

    def test_empty_service_name_rejected(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._cmd_service_status({"service": ""}))
        assert "error" in result
        assert result["exit_code"] == -1

    def test_service_name_with_slash_rejected(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._cmd_service_status({"service": "../../etc/passwd"}))
        assert "error" in result
        assert result["exit_code"] == -1

    def test_service_name_with_dotdot_rejected(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._cmd_service_status({"service": "..malicious"}))
        assert "error" in result
        assert result["exit_code"] == -1


# ---------------------------------------------------------------------------
# _cmd_docker_inspect — container name validation
# ---------------------------------------------------------------------------


class TestCmdDockerInspect:
    def test_empty_container_rejected(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._cmd_docker_inspect({"container": ""}))
        assert "error" in result
        assert result["exit_code"] == -1

    def test_container_with_slash_rejected(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        result = asyncio.run(daemon._cmd_docker_inspect({"container": "../../etc/shadow"}))
        assert "error" in result
        assert result["exit_code"] == -1

    def test_valid_container_name_accepted(self):
        import asyncio  # noqa: PLC0415

        daemon = _make_daemon()
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value={"stdout": '[{"Id":"abc"}]', "exit_code": 0}
            )
            result = asyncio.run(daemon._cmd_docker_inspect({"container": "myapp-container"}))
        assert result["exit_code"] == 0
