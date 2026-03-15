"""Collector: system_vitals — CPU %, memory detail, swap, load. Tier: 10s."""

from __future__ import annotations

import os
from typing import Any


def _read_cpu_times() -> dict[str, float]:
    """Read /proc/stat for aggregate CPU times."""
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()
        names = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"]
        return {n: float(parts[i + 1]) for i, n in enumerate(names) if i + 1 < len(parts)}
    except FileNotFoundError:
        return {}


def _read_memory() -> dict[str, int]:
    """Read /proc/meminfo for memory details in kB."""
    keys = {
        "MemTotal",
        "MemFree",
        "MemAvailable",
        "Buffers",
        "Cached",
        "SwapTotal",
        "SwapFree",
    }
    result: dict[str, int] = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                name = parts[0].rstrip(":")
                if name in keys:
                    result[name] = int(parts[1])
    except FileNotFoundError:
        pass
    return result


def collect() -> dict[str, Any]:
    """Return system vitals payload."""
    load = list(os.getloadavg())
    mem = _read_memory()
    cpu = _read_cpu_times()
    return {
        "load_avg": [round(x, 2) for x in load],
        "cpu_times": cpu,
        "memory_kb": mem,
        "swap_total_kb": mem.get("SwapTotal", 0),
        "swap_free_kb": mem.get("SwapFree", 0),
    }
