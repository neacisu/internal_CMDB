"""Collector: heartbeat — load avg, memory %, uptime. Tier: 5s."""

from __future__ import annotations

import os
import time
from typing import Any

_BOOT_TIME: float | None = None


def _read_uptime() -> float:
    """Return system uptime in seconds."""
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except FileNotFoundError:
        # macOS fallback
        global _BOOT_TIME  # noqa: PLW0603
        if _BOOT_TIME is None:
            import subprocess  # noqa: PLC0415

            out = subprocess.run(
                ["sysctl", "-n", "kern.boottime"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            # Format: { sec = 1710000000, usec = 0 } ...
            for part in out.split(","):
                if "sec" in part:
                    _BOOT_TIME = float(part.split("=")[1].strip().rstrip("}"))
                    break
            if _BOOT_TIME is None:
                _BOOT_TIME = time.time()
        return time.time() - _BOOT_TIME


def _read_loadavg() -> list[float]:
    return list(os.getloadavg())


def _read_memory_pct() -> float:
    """Return memory usage percentage."""
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemAvailable:"):
                    info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 1)
        available = info.get("MemAvailable", 0)
        return round((1 - available / total) * 100, 2)
    except FileNotFoundError:
        return 0.0


def collect() -> dict[str, Any]:
    """Return heartbeat payload."""
    return {
        "uptime_seconds": round(_read_uptime(), 1),
        "load_avg": [round(x, 2) for x in _read_loadavg()],
        "memory_pct": _read_memory_pct(),
    }
