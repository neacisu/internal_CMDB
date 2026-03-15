"""Collector: process_inventory — key processes from ps. Tier: 30min."""

from __future__ import annotations

import subprocess
from typing import Any


def collect() -> dict[str, Any]:
    """Return process inventory from ``ps aux``."""
    try:
        result = subprocess.run(
            ["ps", "aux", "--sort=-%mem"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            # macOS: ps aux without --sort
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )

        processes: list[dict[str, Any]] = []
        lines = result.stdout.strip().splitlines()
        for line in lines[1:]:  # skip header
            parts = line.split(None, 10)
            if len(parts) >= 11:  # noqa: PLR2004
                processes.append(
                    {
                        "user": parts[0],
                        "pid": int(parts[1]),
                        "cpu_pct": float(parts[2]),
                        "mem_pct": float(parts[3]),
                        "vsz_kb": int(parts[4]),
                        "rss_kb": int(parts[5]),
                        "command": parts[10],
                    }
                )
        return {"processes": processes, "total": len(processes)}
    except FileNotFoundError, subprocess.TimeoutExpired:
        return {"processes": [], "error": "ps not available"}
