"""Tests for the restart_container playbook functions.

Covers:
  - Pre-check: container found / not found / container.id is None
  - Execute: restart via Docker API, container.id None guard
  - Post-check: container health verification, container.id None guard
  - Rollback: idempotent no-op
  - Docker import failure graceful handling
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.motor.playbooks import PLAYBOOKS


def _make_mock_docker(
    *, container_id: str | None, name: str, status: str
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build a mock ``docker`` module with a single mock container."""
    mock_container = MagicMock()
    mock_container.id = container_id
    mock_container.name = name
    mock_container.status = status

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    mock_docker = MagicMock()
    mock_docker.from_env.return_value = mock_client

    return mock_docker, mock_client, mock_container


class TestRestartContainerPreCheck:
    """Pre-check function tests for restart_container playbook."""

    @pytest.mark.asyncio
    async def test_pre_check_passes_with_running_container(self) -> None:
        pre_fn = PLAYBOOKS["restart_container"]["pre_check"]
        mock_docker, mock_client, _ = _make_mock_docker(
            container_id="abc123def456",
            name="internalcmdb-api",
            status="running",
        )

        with patch.dict(sys.modules, {"docker": mock_docker}):
            result = await pre_fn({"container_id": "abc123def456"})

        assert result["pre_check"] == "passed"
        assert result["container_id"] == "abc123def456"
        assert result["container_name"] == "internalcmdb-api"
        assert result["status"] == "running"
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_pre_check_guards_none_container_id(self) -> None:
        """When container.id is None (rare Docker daemon edge case),
        the function must not raise TypeError on [:12] subscript."""
        pre_fn = PLAYBOOKS["restart_container"]["pre_check"]
        mock_docker, _, _ = _make_mock_docker(
            container_id=None,
            name="ghost-container",
            status="running",
        )

        with patch.dict(sys.modules, {"docker": mock_docker}):
            result = await pre_fn({"container_id": "my-cid"})

        # Falls back to cid param when container.id is None
        assert result["pre_check"] == "passed"
        assert result["container_id"] == "my-cid"

    @pytest.mark.asyncio
    async def test_pre_check_fails_on_missing_container(self) -> None:
        pre_fn = PLAYBOOKS["restart_container"]["pre_check"]

        mock_docker = MagicMock()
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = Exception("No such container")
        mock_docker.from_env.return_value = mock_client

        with patch.dict(sys.modules, {"docker": mock_docker}):
            result = await pre_fn({"container_id": "missing"})

        assert result["pre_check"] == "failed"
        assert "No such container" in result["error"]

    @pytest.mark.asyncio
    async def test_pre_check_handles_docker_import_failure(self) -> None:
        """If docker package is not installed, pre_check should fail gracefully."""
        pre_fn = PLAYBOOKS["restart_container"]["pre_check"]

        with patch.dict(sys.modules, {"docker": None}):
            result = await pre_fn({"container_id": "test"})

        assert result["pre_check"] == "failed"


class TestRestartContainerExec:
    """Execute function tests for restart_container playbook."""

    @pytest.mark.asyncio
    async def test_exec_restarts_container_successfully(self) -> None:
        exec_fn = PLAYBOOKS["restart_container"]["execute"]
        mock_docker, mock_client, mock_container = _make_mock_docker(
            container_id="abc123def456789",
            name="internalcmdb-api",
            status="running",
        )

        with patch.dict(sys.modules, {"docker": mock_docker}):
            result = await exec_fn({"container_id": "abc123def456789"})

        assert result["action"] == "restarted"
        assert result["container_id"] == "abc123def456"  # 12 char truncation
        mock_container.restart.assert_called_once_with(timeout=30)
        mock_container.reload.assert_called_once()
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_exec_guards_none_container_id(self) -> None:
        """Execute must handle container.id == None without TypeError."""
        exec_fn = PLAYBOOKS["restart_container"]["execute"]
        mock_docker, _, _ = _make_mock_docker(
            container_id=None,
            name="ghost",
            status="running",
        )

        with patch.dict(sys.modules, {"docker": mock_docker}):
            result = await exec_fn({"container_name": "ghost"})

        # Falls back to param-provided name when id is None
        assert result["container_id"] == "ghost"
        assert result["action"] == "restarted"


class TestRestartContainerPostCheck:
    """Post-check function tests for restart_container playbook."""

    @pytest.mark.asyncio
    async def test_post_check_passes_when_running(self) -> None:
        post_fn = PLAYBOOKS["restart_container"]["post_check"]
        mock_docker, _, _ = _make_mock_docker(
            container_id="abc123def456",
            name="api",
            status="running",
        )

        with patch.dict(sys.modules, {"docker": mock_docker}):
            result = await post_fn({"container_id": "abc123def456"})

        assert result["post_check"] == "passed"
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_post_check_warns_when_not_running(self) -> None:
        post_fn = PLAYBOOKS["restart_container"]["post_check"]
        mock_docker, _, _ = _make_mock_docker(
            container_id="abc123def456",
            name="api",
            status="exited",
        )

        with patch.dict(sys.modules, {"docker": mock_docker}):
            result = await post_fn({"container_id": "abc123def456"})

        assert result["post_check"] == "warning"
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_post_check_guards_none_container_id(self) -> None:
        post_fn = PLAYBOOKS["restart_container"]["post_check"]
        mock_docker, _, _ = _make_mock_docker(
            container_id=None,
            name="api",
            status="running",
        )

        with patch.dict(sys.modules, {"docker": mock_docker}):
            result = await post_fn({"container_id": "fallback-cid"})

        assert result["post_check"] == "passed"
        assert result["container_id"] == "fallback-cid"

    @pytest.mark.asyncio
    async def test_post_check_fails_on_exception(self) -> None:
        post_fn = PLAYBOOKS["restart_container"]["post_check"]

        mock_docker = MagicMock()
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = Exception("Docker unreachable")
        mock_docker.from_env.return_value = mock_client

        with patch.dict(sys.modules, {"docker": mock_docker}):
            result = await post_fn({"container_id": "test"})

        assert result["post_check"] == "failed"
        assert result["healthy"] is False


class TestRestartContainerRollback:
    """Rollback is idempotent for container restart."""

    @pytest.mark.asyncio
    async def test_rollback_is_noop(self) -> None:
        rollback_fn = PLAYBOOKS["restart_container"]["rollback"]
        result = await rollback_fn({"container_id": "abc"})

        assert result["rolled_back"] is True
        assert "idempotent" in result.get("note", "")
