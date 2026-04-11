"""Collector: system_vitals — CPU %, memory detail, swap, load. Tier: 10s."""

from __future__ import annotations

import os
import time
from typing import Any


def _read_cpu_times() -> dict[str, float]:
    """Read /proc/stat for aggregate CPU times."""
    try:
        with open("/proc/stat", encoding="utf-8") as f:
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
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                name = parts[0].rstrip(":")
                if name in keys:
                    result[name] = int(parts[1])
    except FileNotFoundError:
        pass
    return result


def _compute_cpu_pct() -> float | None:
    """Compute CPU utilisation % by sampling /proc/stat over 200 ms."""
    t1 = _read_cpu_times()
    time.sleep(0.2)
    t2 = _read_cpu_times()
    if not t1 or not t2:
        return None
    idle1 = t1.get("idle", 0) + t1.get("iowait", 0)
    idle2 = t2.get("idle", 0) + t2.get("iowait", 0)
    total1 = sum(t1.values())
    total2 = sum(t2.values())
    delta_total = total2 - total1
    delta_idle = idle2 - idle1
    if delta_total == 0:
        return None
    return round((1 - delta_idle / delta_total) * 100, 1)


def collect() -> dict[str, Any]:
    """Return system vitals payload."""
    load = list(os.getloadavg())
    mem = _read_memory()
    cpu = _read_cpu_times()
    cpu_pct = _compute_cpu_pct()
    return {
        "load_avg": [round(x, 2) for x in load],
        "cpu_times": cpu,
        "cpu_pct": cpu_pct,
        "memory_kb": mem,
        "swap_total_kb": mem.get("SwapTotal", 0),
        "swap_free_kb": mem.get("SwapFree", 0),
    }
