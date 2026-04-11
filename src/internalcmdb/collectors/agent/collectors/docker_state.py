"""Collector: docker_state — container list, status, resource usage. Tier: 15s."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

_HEALTH_RE = re.compile(r"\(([a-z]+)\)", re.IGNORECASE)


def _parse_health(status: str) -> str:
    """Extract health string from docker status, e.g. 'Up 2h (healthy)' -> 'healthy'."""
    m = _HEALTH_RE.search(status)
    return m.group(1).lower() if m else ""


def collect() -> dict[str, Any]:
    """Return Docker container state via ``docker ps``."""
    fmt = (
        '{"name":{{json .Names}},"image":{{json .Image}},'
        '"status":{{json .Status}},"ports":{{json .Ports}},'
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
                c = json.loads(line)
                c["health"] = _parse_health(str(c.get("status", "")))
                containers.append(c)
        return {"containers": containers, "total": len(containers)}
    except FileNotFoundError:
        return {"containers": [], "error": "docker not found"}
    except subprocess.TimeoutExpired:
        return {"containers": [], "error": "timeout"}
