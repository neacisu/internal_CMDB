"""Collector: disk_state — mount points, usage. Tier: 5min."""

from __future__ import annotations

import subprocess
from typing import Any


def collect() -> dict[str, Any]:
    """Return disk usage via ``df``."""
    try:
        result = subprocess.run(
            ["df", "-B1", "--output=source,target,size,used,avail,pcent"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            # macOS fallback
            result = subprocess.run(
                ["df", "-k"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )

        disks: list[dict[str, Any]] = []
        lines = result.stdout.strip().splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 6:  # noqa: PLR2004
                disks.append(
                    {
                        "device": parts[0],
                        "mountpoint": parts[1] if len(parts) == 6 else parts[5],  # noqa: PLR2004
                        "size_bytes": parts[2],
                        "used_bytes": parts[3],
                        "available_bytes": parts[4],
                        "used_pct": parts[5] if len(parts) == 6 else parts[4],  # noqa: PLR2004
                    }
                )
        return {"disks": disks, "total": len(disks)}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"disks": [], "error": "df not available"}
