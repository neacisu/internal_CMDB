"""Collector: docker_state — container list, status, resource usage. Tier: 15s."""

from __future__ import annotations

import json
import subprocess
from typing import Any


def collect() -> dict[str, Any]:
    """Return Docker container state via ``docker ps``."""
    fmt = (
        '{"name":{{json .Names}},"image":{{json .Image}},'
        '"status":{{json .Status}},"health":{{json .Health}},'
        '"ports":{{json .Ports}},'
        '"created":{{json .CreatedAt}},"id":{{json .ID}}}'
    )
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--no-trunc", "--format", fmt],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return {"containers": [], "error": result.stderr.strip()}

        containers: list[dict[str, Any]] = []
        for line in result.stdout.strip().splitlines():
            if line.strip():
                containers.append(json.loads(line))
        return {"containers": containers, "total": len(containers)}
    except FileNotFoundError:
        return {"containers": [], "error": "docker not found"}
    except subprocess.TimeoutExpired:
        return {"containers": [], "error": "timeout"}
