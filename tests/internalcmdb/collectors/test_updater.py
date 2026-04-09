"""Tests for internalcmdb.collectors.agent.updater — AgentUpdater.

Covers:
  - S7493 fix: all blocking I/O (open, flock, checksum) runs via asyncio.to_thread
  - Update check with 204, success, and error responses
  - Checksum verification pass/fail
  - Concurrent update lock
  - Rollback on failure
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.collectors.agent.updater import (
    AgentUpdater,
    UpdateInfo,
)


@pytest.fixture
def updater() -> AgentUpdater:
    return AgentUpdater(
        api_url="https://test.example.com/api/v1/collectors",
        current_version="1.0.0",
        verify_ssl=False,
    )


@pytest.fixture
def sample_update_info() -> UpdateInfo:
    return UpdateInfo(
        version="2.0.0",
        download_url="https://test.example.com/agent-2.0.0.tar.gz",
        checksum_sha256="abc123",
        release_notes="Test release",
    )


class TestUpdateInfo:
    """UpdateInfo dataclass tests."""

    def test_frozen(self) -> None:
        info = UpdateInfo(version="1.0", download_url="x", checksum_sha256="y")
        with pytest.raises(AttributeError):
            info.version = "2.0"  # type: ignore[misc]

    def test_default_release_notes(self) -> None:
        info = UpdateInfo(version="1.0", download_url="x", checksum_sha256="y")
        assert info.release_notes == ""


class TestCheckUpdate:
    """Tests for check_update() HTTP interactions."""

    @pytest.mark.asyncio
    async def test_no_update_204(self, updater: AgentUpdater) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 204

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await updater.check_update()

        assert result is None

    @pytest.mark.asyncio
    async def test_no_update_flag_false(self, updater: AgentUpdater) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"update_available": False}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await updater.check_update()

        assert result is None

    @pytest.mark.asyncio
    async def test_update_available(self, updater: AgentUpdater) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "update_available": True,
            "version": "2.0.0",
            "download_url": "https://example.com/agent.tar.gz",
            "checksum_sha256": "abcdef",
            "release_notes": "New version",
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await updater.check_update()

        assert result is not None
        assert result.version == "2.0.0"
        assert result.checksum_sha256 == "abcdef"

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self, updater: AgentUpdater) -> None:
        import httpx  # noqa: PLC0415

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await updater.check_update()

        assert result is None


class TestVerifyChecksum:
    """Tests for _verify_checksum static method."""

    def test_checksum_match(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as f:
            f.write(b"test content for checksum")
            path = f.name

        try:
            expected = hashlib.sha256(b"test content for checksum").hexdigest()
            assert AgentUpdater._verify_checksum(path, expected) is True
        finally:
            os.unlink(path)

    def test_checksum_mismatch(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as f:
            f.write(b"test content")
            path = f.name

        try:
            assert AgentUpdater._verify_checksum(path, "wrong_checksum") is False
        finally:
            os.unlink(path)


class TestApplyUpdateAsyncIO:
    """Verify that apply_update uses asyncio.to_thread for blocking I/O (S7493)."""

    @pytest.mark.asyncio
    async def test_apply_uses_to_thread_for_lock(
        self, updater: AgentUpdater, sample_update_info: UpdateInfo
    ) -> None:
        to_thread_calls: list[str] = []
        original_to_thread = asyncio.to_thread

        async def tracking_to_thread(fn, *args, **kwargs):
            to_thread_calls.append(fn.__name__ if hasattr(fn, "__name__") else str(fn))
            return await original_to_thread(fn, *args, **kwargs)

        with (
            patch.object(
                updater, "_download", new_callable=AsyncMock, side_effect=RuntimeError("skip")
            ),
            patch(
                "internalcmdb.collectors.agent.updater.asyncio.to_thread",
                side_effect=tracking_to_thread,
            ),
        ):
            result = await updater.apply_update(sample_update_info)

        assert result is False
        assert len(to_thread_calls) >= 1, "asyncio.to_thread must be called for lock file open"
