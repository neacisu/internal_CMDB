"""Tests for the clear_disk_space playbook (real implementation).

Covers:
  - Pre-check: Docker socket available / unavailable / nothing to reclaim
  - Execute: cleanup delegation to SafeDockerCleaner
  - Post-check: Docker footprint verification
  - Full lifecycle via PlaybookExecutor
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.motor.playbooks import PLAYBOOKS, PlaybookExecutor

_SOCK_MOD = "internalcmdb.cognitive.self_heal_disk"


class TestClearDiskPreCheck:
    @pytest.mark.asyncio
    async def test_aborts_when_socket_missing(self) -> None:
        pre_fn = PLAYBOOKS["clear_disk_space"]["pre_check"]

        with patch(f"{_SOCK_MOD}.os.path.exists", return_value=False):
            result = await pre_fn({"host": "orchestrator"})

        assert result["pre_check"] == "failed"
        assert "Docker socket" in result["reason"]

    @pytest.mark.asyncio
    async def test_skips_when_nothing_to_reclaim(self) -> None:
        pre_fn = PLAYBOOKS["clear_disk_space"]["pre_check"]

        mock_analysis = MagicMock()
        mock_analysis.total_reclaimable_bytes = 10 * 1024 * 1024
        mock_analysis.removable_images = []
        mock_analysis.build_cache_reclaimable_bytes = 10 * 1024 * 1024
        mock_analysis.protected_images_skipped = 0
        mock_analysis.container_images_skipped = 0

        mock_cleaner = MagicMock()
        mock_cleaner.analyze.return_value = mock_analysis

        with (
            patch(f"{_SOCK_MOD}.os.path.exists", return_value=True),
            patch(f"{_SOCK_MOD}.os.access", return_value=True),
            patch(f"{_SOCK_MOD}.SafeDockerCleaner", return_value=mock_cleaner),
        ):
            result = await pre_fn({"host": "orchestrator"})

        assert result["pre_check"] == "skipped"

    @pytest.mark.asyncio
    async def test_passes_when_reclaimable(self) -> None:
        pre_fn = PLAYBOOKS["clear_disk_space"]["pre_check"]

        mock_analysis = MagicMock()
        mock_analysis.total_reclaimable_bytes = 500 * 1024 * 1024
        mock_analysis.removable_images = [{"id": "x", "tags": ["old:v1"], "size": 400_000_000}]
        mock_analysis.build_cache_reclaimable_bytes = 100 * 1024 * 1024
        mock_analysis.protected_images_skipped = 2
        mock_analysis.container_images_skipped = 3

        mock_cleaner = MagicMock()
        mock_cleaner.analyze.return_value = mock_analysis

        with (
            patch(f"{_SOCK_MOD}.os.path.exists", return_value=True),
            patch(f"{_SOCK_MOD}.os.access", return_value=True),
            patch(f"{_SOCK_MOD}.SafeDockerCleaner", return_value=mock_cleaner),
        ):
            result = await pre_fn({"host": "orchestrator"})

        assert result["pre_check"] == "passed"
        assert result["removable_images"] == 1


class TestClearDiskExecute:
    @pytest.mark.asyncio
    async def test_returns_freed_bytes(self) -> None:
        exec_fn = PLAYBOOKS["clear_disk_space"]["execute"]

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.total_freed_bytes = 1_000_000_000
        mock_result.build_cache_freed_bytes = 500_000_000
        mock_result.dangling_images_freed_bytes = 200_000_000
        mock_result.unused_images_freed_bytes = 300_000_000
        mock_result.unused_images_removed = ["old:v1"]
        mock_result.audit_log = ["step1", "step2"]
        mock_result.errors = []

        mock_cleaner = MagicMock()
        mock_cleaner.execute_cleanup.return_value = mock_result

        with patch(f"{_SOCK_MOD}.SafeDockerCleaner", return_value=mock_cleaner):
            result = await exec_fn({"host": "orchestrator", "disk_pct": 91.0})

        assert result["action"] == "disk_cleaned"
        assert result["freed_mb"] == pytest.approx(1_000_000_000 / (1024 * 1024), rel=0.01)
        assert result["executed"] is True


class TestClearDiskPostCheck:
    @pytest.mark.asyncio
    async def test_reports_remaining_docker_usage(self) -> None:
        post_fn = PLAYBOOKS["clear_disk_space"]["post_check"]

        sysdf = {
            "Images": [{"Size": 500_000_000}, {"Size": 300_000_000}],
            "BuildCache": [{"Size": 100_000_000}],
        }

        mock_cleaner = MagicMock()
        mock_cleaner._get_json.return_value = sysdf

        with (
            patch(f"{_SOCK_MOD}.os.path.exists", return_value=True),
            patch(f"{_SOCK_MOD}.os.access", return_value=True),
            patch(f"{_SOCK_MOD}.SafeDockerCleaner", return_value=mock_cleaner),
        ):
            result = await post_fn({"host": "orchestrator"})

        assert result["post_check"] == "passed"
        assert result["healthy"] is True
        assert result["docker_remaining_bytes"] == 900_000_000


class TestPlaybookExecutorClearDisk:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        """End-to-end: pre → exec → post for clear_disk_space."""
        executor = PlaybookExecutor()

        mock_analysis = MagicMock()
        mock_analysis.total_reclaimable_bytes = 1_000_000_000
        mock_analysis.removable_images = [{"id": "x", "tags": ["old:v1"], "size": 800_000_000}]
        mock_analysis.build_cache_reclaimable_bytes = 200_000_000
        mock_analysis.protected_images_skipped = 0
        mock_analysis.container_images_skipped = 2

        mock_cleanup = MagicMock()
        mock_cleanup.success = True
        mock_cleanup.total_freed_bytes = 900_000_000
        mock_cleanup.build_cache_freed_bytes = 200_000_000
        mock_cleanup.dangling_images_freed_bytes = 0
        mock_cleanup.unused_images_freed_bytes = 700_000_000
        mock_cleanup.unused_images_removed = ["old:v1"]
        mock_cleanup.audit_log = ["done"]
        mock_cleanup.errors = []

        sysdf = {"Images": [{"Size": 100_000_000}], "BuildCache": []}

        mock_cleaner = MagicMock()
        mock_cleaner.analyze.return_value = mock_analysis
        mock_cleaner.execute_cleanup.return_value = mock_cleanup
        mock_cleaner._get_json.return_value = sysdf

        with (
            patch(f"{_SOCK_MOD}.os.path.exists", return_value=True),
            patch(f"{_SOCK_MOD}.os.access", return_value=True),
            patch(f"{_SOCK_MOD}.SafeDockerCleaner", return_value=mock_cleaner),
        ):
            result = await executor.execute(
                "clear_disk_space", {"host": "orchestrator", "disk_pct": 93.0}
            )

        assert result.success is True
        assert result.steps_completed >= 3
        assert result.output["execute"]["action"] == "disk_cleaned"
