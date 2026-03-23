"""Collector: container_resources — CPU%, MEM%, net, disk, restarts per container. Tier: 15s."""

from __future__ import annotations

import json
import subprocess
from typing import Any


def _docker_stats() -> list[dict[str, Any]]:
    """Return per-container resource stats via ``docker stats --no-stream``."""
    fmt = (
        '{"name":{{json .Name}},"cpu_pct":{{json .CPUPerc}},'
        '"mem_pct":{{json .MemPerc}},"mem_usage":{{json .MemUsage}},'
        '"net_io":{{json .NetIO}},"block_io":{{json .BlockIO}},'
        '"pids":{{json .PIDs}}}'
    )
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", fmt],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        return []

    containers: list[dict[str, Any]] = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return containers


def _parse_pct(val: str) -> float:
    """Parse '12.34%' → 12.34."""
    if not val:
        return 0.0
    try:
        return float(val.rstrip("%"))
    except (ValueError, TypeError):
        return 0.0


def _parse_bytes_pair(val: str) -> tuple[float, float]:
    """Parse '1.23kB / 4.56MB' → (in_bytes, out_bytes) — best effort."""
    multipliers = {"B": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12,
                   "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}
    parts = val.split("/")
    if len(parts) != 2:  # noqa: PLR2004
        return 0.0, 0.0

    results: list[float] = []
    for p in parts:
        p = p.strip()
        num = 0.0
        for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
            if p.endswith(suffix):
                try:
                    num = float(p[: -len(suffix)].strip()) * mult
                except ValueError:
                    num = 0.0
                break
        results.append(num)
    return results[0], results[1]


def _inspect_restarts() -> dict[str, dict[str, Any]]:
    """Return restart count and uptime per container via ``docker inspect``."""
    ps_result = subprocess.run(
        ["docker", "ps", "-q"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    container_ids = ps_result.stdout.strip().split()
    if not container_ids or ps_result.returncode != 0:
        return {}

    result = subprocess.run(
        [
            "docker", "inspect",
            "--format", '{{json .Name}} {{json .RestartCount}} {{json .State.StartedAt}}',
            *container_ids,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    info: dict[str, dict[str, Any]] = {}
    if result.returncode != 0:
        return info

    for line in result.stdout.strip().splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) >= 2:  # noqa: PLR2004
            name = parts[0].strip('"').lstrip("/")
            restart_count = int(parts[1]) if parts[1].isdigit() else 0
            started_at = parts[2].strip('"') if len(parts) > 2 else None  # noqa: PLR2004
            info[name] = {"restart_count": restart_count, "started_at": started_at}
    return info


_MAX_CONTAINERS = 500


def collect() -> dict[str, Any]:
    """Return per-container resource metrics."""
    try:
        raw_stats = _docker_stats()
    except FileNotFoundError:
        return {"containers": [], "error": "docker not found"}
    except subprocess.TimeoutExpired:
        return {"containers": [], "error": "timeout"}
    except Exception as exc:
        return {"containers": [], "error": f"unexpected: {exc}"}

    try:
        restarts = _inspect_restarts()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        restarts = {}

    containers: list[dict[str, Any]] = []
    for c in raw_stats:
        name = c.get("name", "")
        net_in, net_out = _parse_bytes_pair(c.get("net_io", ""))
        disk_read, disk_write = _parse_bytes_pair(c.get("block_io", ""))
        extra = restarts.get(name, {})
        containers.append({
            "name": name,
            "cpu_pct": _parse_pct(c.get("cpu_pct", "0%")),
            "mem_pct": _parse_pct(c.get("mem_pct", "0%")),
            "net_bytes_in": net_in,
            "net_bytes_out": net_out,
            "disk_read_bytes": disk_read,
            "disk_write_bytes": disk_write,
            "restart_count": extra.get("restart_count", 0),
            "started_at": extra.get("started_at"),
        })

    if len(containers) > _MAX_CONTAINERS:
        containers = containers[:_MAX_CONTAINERS]
    return {"containers": containers, "total": len(containers),
            "truncated": len(raw_stats) > _MAX_CONTAINERS}
