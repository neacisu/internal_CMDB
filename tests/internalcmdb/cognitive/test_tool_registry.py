"""Tests for internalcmdb.cognitive.tool_registry.

Covers:
  - RiskClass StrEnum values and behaviour
  - ToolDefinition: construction, requires_hitl, to_openai_tool()
  - ToolRegistry: register, get, list_tools (filtered), openai_tools, tool_count
  - get_registry: singleton returns same object; all three phases registered
  - _summarize_payload: dict/list/scalar/non-dict branches, nested payload
  - check_network_connectivity: URL validation (scheme, netloc, empty) and shlex safety
  - read_config_file: path allowlist validation (allowed, denied, empty)
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from internalcmdb.cognitive.tool_registry import (
    RiskClass,
    ToolDefinition,
    ToolRegistry,
    _summarize_payload,
    get_registry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _noop(params: dict[str, Any]) -> dict[str, Any]:
    await asyncio.sleep(0)  # cooperative yield — ensures function is truly async
    return {"ok": True, "params": params}


def _make_tool(
    tool_id: str = "test_tool",
    risk_class: RiskClass = RiskClass.RC1,
    tags: tuple[str, ...] = (),
) -> ToolDefinition:
    return ToolDefinition(
        tool_id=tool_id,
        name=f"Test Tool {tool_id}",
        description="A test tool.",
        risk_class=risk_class,
        parameters={"type": "object", "properties": {}, "required": []},
        execute=_noop,
        tags=tags,
    )


# ---------------------------------------------------------------------------
# RiskClass
# ---------------------------------------------------------------------------


class TestRiskClass:
    def test_values_are_strings(self) -> None:
        assert RiskClass.RC1 == "RC-1"
        assert RiskClass.RC2 == "RC-2"
        assert RiskClass.RC3 == "RC-3"

    def test_is_str(self) -> None:
        assert isinstance(RiskClass.RC1, str)

    def test_str_comparison(self) -> None:
        assert RiskClass.RC1 == "RC-1"
        assert RiskClass.RC2 != "RC-1"


# ---------------------------------------------------------------------------
# ToolDefinition
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_rc1_does_not_require_hitl(self) -> None:
        tool = _make_tool(risk_class=RiskClass.RC1)
        assert tool.requires_hitl is False

    def test_rc2_requires_hitl(self) -> None:
        tool = _make_tool(risk_class=RiskClass.RC2)
        assert tool.requires_hitl is True

    def test_rc3_requires_hitl(self) -> None:
        tool = _make_tool(risk_class=RiskClass.RC3)
        assert tool.requires_hitl is True

    def test_to_openai_tool_structure(self) -> None:
        tool = _make_tool(tool_id="my_tool")
        openai = tool.to_openai_tool()
        assert openai["type"] == "function"
        assert "function" in openai
        fn = openai["function"]
        assert fn["name"] == "my_tool"
        assert "description" in fn
        assert "parameters" in fn

    def test_cooldown_and_timeout_defaults(self) -> None:
        tool = _make_tool()
        assert tool.cooldown_s == 0
        assert tool.timeout_s == 30

    def test_custom_cooldown_and_timeout(self) -> None:
        tool = ToolDefinition(
            tool_id="t",
            name="T",
            description="d",
            risk_class=RiskClass.RC2,
            parameters={"type": "object", "properties": {}, "required": []},
            execute=_noop,
            cooldown_s=120,
            timeout_s=60,
        )
        assert tool.cooldown_s == 120
        assert tool.timeout_s == 60

    def test_tags_default_empty(self) -> None:
        tool = _make_tool()
        assert tool.tags == ()

    def test_execute_is_callable(self) -> None:
        tool = _make_tool()
        assert callable(tool.execute)

    @pytest.mark.asyncio
    async def test_execute_returns_dict(self) -> None:
        tool = _make_tool()
        result = await tool.execute({"x": 1})
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        tool = _make_tool("alpha")
        reg.register(tool)
        assert reg.get("alpha") is tool

    def test_get_missing_returns_none(self) -> None:
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_tool_count(self) -> None:
        reg = ToolRegistry()
        assert reg.tool_count == 0
        reg.register(_make_tool("a"))
        reg.register(_make_tool("b"))
        assert reg.tool_count == 2

    def test_list_tools_unfiltered(self) -> None:
        reg = ToolRegistry()
        reg.register(_make_tool("x", RiskClass.RC1))
        reg.register(_make_tool("y", RiskClass.RC2))
        tools = reg.list_tools()
        assert len(tools) == 2

    def test_list_tools_filtered_by_risk_class(self) -> None:
        reg = ToolRegistry()
        reg.register(_make_tool("x", RiskClass.RC1))
        reg.register(_make_tool("y", RiskClass.RC2))
        reg.register(_make_tool("z", RiskClass.RC3))
        rc2 = reg.list_tools(risk_class=RiskClass.RC2)
        assert len(rc2) == 1
        assert rc2[0].tool_id == "y"

    def test_list_tools_filtered_by_tags(self) -> None:
        reg = ToolRegistry()
        reg.register(_make_tool("a", tags=("diagnostic",)))
        reg.register(_make_tool("b", tags=("remediation",)))
        reg.register(_make_tool("c", tags=("diagnostic", "host")))
        diag = reg.list_tools(tags=("diagnostic",))
        ids = {t.tool_id for t in diag}
        assert ids == {"a", "c"}

    def test_list_tools_combined_filter(self) -> None:
        reg = ToolRegistry()
        reg.register(_make_tool("a", RiskClass.RC1, tags=("diagnostic",)))
        reg.register(_make_tool("b", RiskClass.RC2, tags=("diagnostic",)))
        reg.register(_make_tool("c", RiskClass.RC1, tags=("remediation",)))
        result = reg.list_tools(risk_class=RiskClass.RC1, tags=("diagnostic",))
        assert len(result) == 1
        assert result[0].tool_id == "a"

    def test_openai_tools_empty(self) -> None:
        reg = ToolRegistry()
        assert reg.openai_tools() == []

    def test_openai_tools_format(self) -> None:
        reg = ToolRegistry()
        reg.register(_make_tool("t1", RiskClass.RC1))
        tools = reg.openai_tools()
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "t1"

    def test_overwrite_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        reg = ToolRegistry()
        reg.register(_make_tool("dup"))
        with caplog.at_level(logging.WARNING, logger="internalcmdb.cognitive.tool_registry"):
            reg.register(_make_tool("dup"))
        assert any("already registered" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# get_registry singleton
# ---------------------------------------------------------------------------


class TestGetRegistry:
    def test_returns_tool_registry_instance(self) -> None:
        reg = get_registry()
        assert isinstance(reg, ToolRegistry)

    def test_singleton_same_object(self) -> None:
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_builtin_tools_registered(self) -> None:
        reg = get_registry()
        assert reg.get("query_host_health") is not None
        assert reg.get("query_active_insights") is not None
        assert reg.get("query_fleet_summary") is not None
        assert reg.get("query_recent_drifts") is not None
        assert reg.get("query_host_snapshots") is not None

    def test_phase4_tools_registered(self) -> None:
        reg = get_registry()
        assert reg.get("query_service_instances") is not None
        assert reg.get("search_knowledge_base") is not None
        assert reg.get("query_audit_trail") is not None
        assert reg.get("query_snapshot_history") is not None
        assert reg.get("remote_diagnostic") is not None
        assert reg.get("check_disk_usage") is not None

    def test_phase5_tools_registered(self) -> None:
        reg = get_registry()
        assert reg.get("restart_container") is not None
        assert reg.get("clear_disk_space") is not None
        assert reg.get("restart_systemd_service") is not None
        assert reg.get("execute_playbook") is not None

    def test_phase5_tools_require_hitl(self) -> None:
        reg = get_registry()
        for tool_id in ("restart_container", "clear_disk_space", "restart_systemd_service"):
            tool = reg.get(tool_id)
            assert tool is not None
            assert tool.requires_hitl is True, f"{tool_id} should require HITL"

    def test_rc1_tools_do_not_require_hitl(self) -> None:
        reg = get_registry()
        for tool_id in ("query_host_health", "query_fleet_summary", "check_disk_usage"):
            tool = reg.get(tool_id)
            assert tool is not None
            assert tool.requires_hitl is False, f"{tool_id} should not require HITL"


# ---------------------------------------------------------------------------
# _summarize_payload
# ---------------------------------------------------------------------------


class TestSummarizePayload:
    def test_non_dict_returns_raw(self) -> None:
        result = _summarize_payload("not a dict")
        assert "raw" in result
        assert isinstance(result["raw"], str)

    def test_none_returns_raw(self) -> None:
        result = _summarize_payload(None)
        assert "raw" in result

    def test_number_returns_raw(self) -> None:
        result = _summarize_payload(42)
        assert result == {"raw": "42"}

    def test_empty_dict_returns_empty_summary(self) -> None:
        result = _summarize_payload({})
        assert result == {}

    def test_unknown_keys_ignored(self) -> None:
        result = _summarize_payload({"unknown_key": 99})
        assert result == {}

    def test_scalar_value_included(self) -> None:
        result = _summarize_payload({"memory": {"total": 8192, "used": 4096}})
        assert "memory" in result
        assert result["memory"]["total"] == 8192
        assert result["memory"]["used"] == 4096

    def test_nested_dicts_filtered_from_inner(self) -> None:
        """Nested dict values inside a known key should be excluded."""
        result = _summarize_payload({
            "cpu_times": {
                "user": 12.5,
                "system": 3.1,
                "nested": {"deep": 1},  # should be excluded (is dict)
                "idle": 80.0,
            }
        })
        assert "cpu_times" in result
        assert "user" in result["cpu_times"]
        assert "nested" not in result["cpu_times"]

    def test_list_value_shows_count(self) -> None:
        result = _summarize_payload({"containers": [1, 2, 3, 4, 5]})
        assert "containers" in result
        assert result["containers"] == "5 items"

    def test_empty_list_shows_zero_items(self) -> None:
        result = _summarize_payload({"partitions": []})
        assert result["partitions"] == "0 items"

    def test_scalar_direct_value_preserved(self) -> None:
        result = _summarize_payload({"load_avg": 1.23})
        assert math.isclose(result["load_avg"], 1.23)

    def test_multiple_known_keys(self) -> None:
        result = _summarize_payload({
            "memory": {"total": 8192},
            "load_avg": 2.5,
            "containers": ["a", "b"],
        })
        assert "memory" in result
        assert "load_avg" in result
        assert math.isclose(result["load_avg"], 2.5)
        assert "containers" in result
        assert result["containers"] == "2 items"


# ---------------------------------------------------------------------------
# check_network_connectivity — URL validation and shlex safety
# ---------------------------------------------------------------------------

_MOCK_REMOTE = "internalcmdb.cognitive.tool_registry._tool_remote_diagnostic"


@pytest.mark.asyncio
class TestCheckNetworkConnectivity:
    """Test the validation logic and delegation inside _mk_check_net."""

    def _execute(self) -> Any:
        """Return the execute callable from the registered tool."""
        reg = get_registry()
        tool = reg.get("check_network_connectivity")
        assert tool is not None, "check_network_connectivity must be registered"
        return tool.execute

    def test_registered_in_registry(self) -> None:
        tool = get_registry().get("check_network_connectivity")
        assert tool is not None
        assert tool.tool_id == "check_network_connectivity"

    def test_is_rc1_no_hitl(self) -> None:
        tool = get_registry().get("check_network_connectivity")
        assert tool is not None
        assert tool.risk_class == RiskClass.RC1
        assert tool.requires_hitl is False

    async def test_empty_url_returns_error(self) -> None:
        result = await self._execute()({"agent_id": "ag1", "url": ""})
        assert "error" in result
        assert "url" in result["error"].lower()

    async def test_missing_url_key_returns_error(self) -> None:
        result = await self._execute()({"agent_id": "ag1"})
        assert "error" in result

    async def test_ftp_scheme_rejected(self) -> None:
        result = await self._execute()({"agent_id": "ag1", "url": "ftp://example.com/file"})
        assert "error" in result
        assert "http" in result["error"].lower()

    async def test_file_scheme_rejected(self) -> None:
        result = await self._execute()({"agent_id": "ag1", "url": "file:///etc/passwd"})
        assert "error" in result

    async def test_javascript_scheme_rejected(self) -> None:
        result = await self._execute()({"agent_id": "ag1", "url": "javascript:alert(1)"})
        assert "error" in result

    async def test_no_netloc_rejected(self) -> None:
        # "http:///path" has empty netloc
        result = await self._execute()({"agent_id": "ag1", "url": "http:///path/only"})
        assert "error" in result
        assert "host" in result["error"].lower() or "netloc" in result["error"].lower()

    async def test_valid_http_url_delegates(self) -> None:
        mock_result = {"output": "200", "success": True}
        with patch(_MOCK_REMOTE, new=AsyncMock(return_value=mock_result)) as mock:
            result = await self._execute()({"agent_id": "ag1", "url": "http://example.com"})
        assert result == mock_result
        mock.assert_awaited_once()

    async def test_valid_https_url_delegates(self) -> None:
        mock_result = {"output": "200", "success": True}
        with patch(_MOCK_REMOTE, new=AsyncMock(return_value=mock_result)) as mock:
            result = await self._execute()({"agent_id": "ag1", "url": "https://example.com/path?q=1"})
        assert result == mock_result
        call_params = mock.call_args[0][0]
        assert call_params["agent_id"] == "ag1"
        # shlex.quote must be applied — url must appear as single-quoted token in command
        assert "https://example.com/path?q=1" in call_params["command"]

    async def test_shlex_quoting_prevents_injection(self) -> None:
        """URL with special shell characters should be shlex-quoted, not executed raw."""
        injected_url = "http://example.com/; rm -rf /"
        mock_result = {"output": "200", "success": True}
        with patch(_MOCK_REMOTE, new=AsyncMock(return_value=mock_result)) as mock:
            await self._execute()({"agent_id": "ag1", "url": injected_url})
        call_params = mock.call_args[0][0]
        # The semicolons must NOT appear unquoted at the command level
        # shlex.quote wraps the whole url in single quotes
        assert "; rm -rf /" not in call_params["command"].split("'")[0]
        # The full command must contain a single-quoted version of the url
        assert "'" in call_params["command"]


# ---------------------------------------------------------------------------
# read_config_file — path allowlist validation
# ---------------------------------------------------------------------------

_ALLOWED_PREFIXES = ("/etc/", "/opt/stacks/", "/var/log/", "/home/", "/usr/local/etc/")


@pytest.mark.asyncio
class TestReadConfigFile:
    """Test path allowlist enforcement and delegation inside _mk_read_config."""

    def _execute(self) -> Any:
        reg = get_registry()
        tool = reg.get("read_config_file")
        assert tool is not None, "read_config_file must be registered"
        return tool.execute

    def test_registered_in_registry(self) -> None:
        tool = get_registry().get("read_config_file")
        assert tool is not None
        assert tool.tool_id == "read_config_file"

    def test_is_rc1_no_hitl(self) -> None:
        tool = get_registry().get("read_config_file")
        assert tool is not None
        assert tool.risk_class == RiskClass.RC1
        assert tool.requires_hitl is False

    async def test_empty_path_returns_error(self) -> None:
        result = await self._execute()({"agent_id": "ag1", "path": ""})
        assert "error" in result
        assert "path" in result["error"].lower()

    async def test_missing_path_key_returns_error(self) -> None:
        result = await self._execute()({"agent_id": "ag1"})
        assert "error" in result

    @pytest.mark.parametrize(
        "bad_path",
        [
            "/tmp/evil",
            "/root/.ssh/id_rsa",
            "/proc/1/mem",
            "/sys/kernel",
            "/dev/sda",
            "relative/path/file.conf",
            "/usr/etc/bad",      # does not start with /usr/local/etc/
        ],
    )
    async def test_disallowed_paths_rejected(self, bad_path: str) -> None:
        result = await self._execute()({"agent_id": "ag1", "path": bad_path})
        assert "error" in result
        assert "allowlist" in result["error"].lower() or "allowed" in result["error"].lower()

    @pytest.mark.parametrize(
        "good_path",
        [
            "/etc/ssh/sshd_config",
            "/etc/nginx/nginx.conf",
            "/opt/stacks/internalcmdb/docker-compose.yml",
            "/var/log/syslog",
            "/home/deploy/.bashrc",
            "/usr/local/etc/redis.conf",
        ],
    )
    async def test_allowed_paths_delegate(self, good_path: str) -> None:
        mock_result = {"output": "file content", "success": True}
        with patch(_MOCK_REMOTE, new=AsyncMock(return_value=mock_result)) as mock:
            result = await self._execute()({"agent_id": "ag1", "path": good_path})
        assert result == mock_result
        mock.assert_awaited_once()
        call_params = mock.call_args[0][0]
        assert call_params["agent_id"] == "ag1"
        # shlex.quote must wrap path — good_path must appear in command
        assert good_path in call_params["command"]

    async def test_shlex_quoting_in_cat_command(self) -> None:
        """Path with spaces/special chars must be shlex-quoted in the cat command."""
        tricky_path = "/etc/nginx/conf.d/my site.conf"
        mock_result = {"output": "server {}", "success": True}
        with patch(_MOCK_REMOTE, new=AsyncMock(return_value=mock_result)) as mock:
            await self._execute()({"agent_id": "ag1", "path": tricky_path})
        call_params = mock.call_args[0][0]
        # shlex.quote produces 'cat /path/...' with the path in single quotes
        assert "cat" in call_params["command"]
        assert tricky_path in call_params["command"]
        # Must not be bare (unquoted) in command string
        assert f"cat {tricky_path}" not in call_params["command"]
