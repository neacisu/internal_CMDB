"""Tests for internalcmdb.cognitive.self_heal_disk.

Covers:
  - Safety guarantees: protected images never removed, container images untouched
  - CleanupAnalysis correctness
  - CleanupResult audit trail
  - Docker API interaction (mocked Unix socket)
  - Edge cases: empty responses, API errors, missing socket
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.cognitive.self_heal_disk import (
    SafeDockerCleaner,
    docker_socket_available,
    format_bytes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_request(responses: dict[str, tuple[int, str]]):
    """Return a side_effect for SafeDockerCleaner._request.

    *responses* maps (METHOD, path_prefix) → (status, body).
    """

    def side_effect(method: str, path: str) -> tuple[int, str]:
        for key, val in responses.items():
            m, p = key.split(" ", 1)
            if method == m and path.startswith(p):
                return val
        return (404, '{"message":"not found"}')

    return side_effect


def _make_image(
    img_id: str,
    tags: list[str] | None = None,
    size: int = 100_000_000,
    containers: int = 0,
) -> dict[str, Any]:
    return {
        "Id": img_id,
        "RepoTags": tags or ["<none>:<none>"],
        "Size": size,
        "Containers": containers,
    }


def _make_container(image_id: str, image_name: str = "") -> dict[str, Any]:
    return {"ImageID": image_id, "Image": image_name or image_id}


# ---------------------------------------------------------------------------
# format_bytes
# ---------------------------------------------------------------------------


class TestFormatBytes:
    def test_gigabytes(self) -> None:
        assert "GB" in format_bytes(2 * 1024**3)

    def test_megabytes(self) -> None:
        assert "MB" in format_bytes(150 * 1024**2)

    def test_kilobytes(self) -> None:
        assert "KB" in format_bytes(512 * 1024)


# ---------------------------------------------------------------------------
# docker_socket_available
# ---------------------------------------------------------------------------


class TestDockerSocketAvailable:
    @patch("internalcmdb.cognitive.self_heal_disk.os.path.exists", return_value=False)
    def test_missing_socket(self, mock_exists: MagicMock) -> None:
        assert docker_socket_available() is False

    @patch("internalcmdb.cognitive.self_heal_disk.os.access", return_value=True)
    @patch("internalcmdb.cognitive.self_heal_disk.os.path.exists", return_value=True)
    def test_accessible_socket(self, mock_exists: MagicMock, mock_access: MagicMock) -> None:
        assert docker_socket_available() is True


# ---------------------------------------------------------------------------
# SafeDockerCleaner._is_protected
# ---------------------------------------------------------------------------


class TestIsProtected:
    @pytest.mark.parametrize(
        "tags",
        [
            ["ghcr.io/alexneacsu/internalcmdb-api:latest"],
            ["postgres:16"],
            ["prom/prometheus:v2.50"],
            ["grafana/grafana:11.0"],
            ["redis:7-alpine"],
        ],
    )
    def test_protected_images_detected(self, tags: list[str]) -> None:
        assert SafeDockerCleaner._is_protected(tags) is True

    @pytest.mark.parametrize(
        "tags",
        [
            ["dbeaver/cloudbeaver:latest"],
            ["roundcube/roundcubemail:1.6"],
            ["some-random-tool:v1"],
        ],
    )
    def test_unprotected_images_allowed(self, tags: list[str]) -> None:
        assert SafeDockerCleaner._is_protected(tags) is False


# ---------------------------------------------------------------------------
# SafeDockerCleaner.analyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_identifies_removable_images(self) -> None:
        cleaner = SafeDockerCleaner("/fake.sock")

        containers = [_make_container("sha256:aaa")]
        images = [
            _make_image("sha256:aaa", ["myapp:latest"], 500_000_000),
            _make_image("sha256:bbb", ["dbeaver/cloudbeaver:1.0"], 200_000_000),
            _make_image("sha256:ccc", ["postgres:16"], 300_000_000),
        ]
        sysdf = {"BuildCache": [{"InUse": False, "Size": 1_000_000}], "Images": []}

        with patch.object(cleaner, "_request") as mock_req:
            mock_req.side_effect = _mock_request(
                {
                    "GET /system/df": (200, json.dumps(sysdf)),
                    "GET /images/json": (200, json.dumps(images)),
                    "GET /containers/json": (200, json.dumps(containers)),
                }
            )

            analysis = cleaner.analyze()

        assert analysis.build_cache_reclaimable_bytes == 1_000_000
        assert analysis.container_images_skipped == 1
        assert analysis.protected_images_skipped == 1
        assert len(analysis.removable_images) == 1
        assert analysis.removable_images[0]["tags"] == ["dbeaver/cloudbeaver:1.0"]

    def test_empty_system_returns_zero(self) -> None:
        cleaner = SafeDockerCleaner("/fake.sock")

        with patch.object(cleaner, "_request") as mock_req:
            mock_req.side_effect = _mock_request(
                {
                    "GET /system/df": (200, json.dumps({"BuildCache": [], "Images": []})),
                    "GET /images/json": (200, "[]"),
                    "GET /containers/json": (200, "[]"),
                }
            )

            analysis = cleaner.analyze()

        assert analysis.total_reclaimable_bytes == 0
        assert len(analysis.removable_images) == 0

    def test_dangling_images_counted(self) -> None:
        cleaner = SafeDockerCleaner("/fake.sock")

        images = [_make_image("sha256:dangling1")]

        with patch.object(cleaner, "_request") as mock_req:
            mock_req.side_effect = _mock_request(
                {
                    "GET /system/df": (200, json.dumps({"BuildCache": []})),
                    "GET /images/json": (200, json.dumps(images)),
                    "GET /containers/json": (200, "[]"),
                }
            )

            analysis = cleaner.analyze()

        assert analysis.dangling_images_count == 1
        assert len(analysis.removable_images) == 0


# ---------------------------------------------------------------------------
# SafeDockerCleaner.execute_cleanup
# ---------------------------------------------------------------------------


class TestExecuteCleanup:
    def test_full_cleanup_cycle(self) -> None:
        cleaner = SafeDockerCleaner("/fake.sock")

        containers = [_make_container("sha256:keep-me")]
        images = [
            _make_image("sha256:keep-me", ["internalcmdb-api:latest"], 500_000_000),
            _make_image("sha256:remove-me", ["old-tool:v1"], 200_000_000),
        ]

        with patch.object(cleaner, "_request") as mock_req:
            mock_req.side_effect = _mock_request(
                {
                    "POST /build/prune": (200, json.dumps({"SpaceReclaimed": 50_000_000})),
                    "POST /images/prune": (
                        200,
                        json.dumps({"SpaceReclaimed": 10_000_000, "ImagesDeleted": []}),
                    ),
                    "GET /containers/json": (200, json.dumps(containers)),
                    "GET /images/json": (200, json.dumps(images)),
                    "DELETE /images/sha256:remove-me": (200, "[]"),
                }
            )

            result = cleaner.execute_cleanup(disk_pct=92.0)

        assert result.success is True
        assert result.build_cache_freed_bytes == 50_000_000
        assert result.dangling_images_freed_bytes == 10_000_000
        assert "old-tool:v1" in result.unused_images_removed
        assert result.total_freed_bytes == 260_000_000
        assert len(result.audit_log) > 0

    def test_protected_images_never_removed(self) -> None:
        cleaner = SafeDockerCleaner("/fake.sock")

        images = [
            _make_image("sha256:pg", ["postgres:16"], 300_000_000),
            _make_image("sha256:redis", ["redis:7"], 50_000_000),
            _make_image("sha256:graf", ["grafana/grafana:11"], 400_000_000),
        ]

        with patch.object(cleaner, "_request") as mock_req:
            mock_req.side_effect = _mock_request(
                {
                    "POST /build/prune": (200, json.dumps({"SpaceReclaimed": 0})),
                    "POST /images/prune": (200, json.dumps({"SpaceReclaimed": 0})),
                    "GET /containers/json": (200, "[]"),
                    "GET /images/json": (200, json.dumps(images)),
                }
            )

            result = cleaner.execute_cleanup()

        assert result.unused_images_removed == []
        assert result.unused_images_freed_bytes == 0
        protected_logs = [log for log in result.audit_log if "PROTECTED" in log]
        assert len(protected_logs) == 3

    def test_container_images_never_removed(self) -> None:
        cleaner = SafeDockerCleaner("/fake.sock")

        containers = [
            _make_container("sha256:img-a", "some-app:v2"),
            _make_container("sha256:img-b"),
        ]
        images = [
            _make_image("sha256:img-a", ["some-app:v2"], 100_000_000),
            _make_image("sha256:img-b", ["another-app:v1"], 200_000_000),
        ]

        with patch.object(cleaner, "_request") as mock_req:
            mock_req.side_effect = _mock_request(
                {
                    "POST /build/prune": (200, json.dumps({"SpaceReclaimed": 0})),
                    "POST /images/prune": (200, json.dumps({"SpaceReclaimed": 0})),
                    "GET /containers/json": (200, json.dumps(containers)),
                    "GET /images/json": (200, json.dumps(images)),
                }
            )

            result = cleaner.execute_cleanup()

        assert result.unused_images_removed == []

    def test_api_errors_handled_gracefully(self) -> None:
        cleaner = SafeDockerCleaner("/fake.sock")

        with patch.object(cleaner, "_request") as mock_req:
            mock_req.side_effect = _mock_request(
                {
                    "POST /build/prune": (500, "Internal Server Error"),
                    "POST /images/prune": (500, "Internal Server Error"),
                    "GET /containers/json": (500, "fail"),
                }
            )

            result = cleaner.execute_cleanup()

        assert result.success is False
        assert len(result.errors) > 0
        assert result.total_freed_bytes == 0
