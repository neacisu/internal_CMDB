"""Collector: network_latency — RTT ping and packet loss between nodes. Tier: 1min."""

from __future__ import annotations

import re
import subprocess
from typing import Any

DEFAULT_TARGETS: list[str] = [
    "127.0.0.1",
]

_LOSS_RE = re.compile(r"(\d+(?:\.\d+)?)% packet loss")
_RTT_RE = re.compile(r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)")


def _ping(host: str, count: int = 5, timeout: int = 5) -> dict[str, Any]:
    """Run ping and parse RTT + loss statistics."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            capture_output=True,
            text=True,
            check=False,
            timeout=count * timeout + 5,
        )
        output = result.stdout + result.stderr

        loss_pct = 100.0
        loss_match = _LOSS_RE.search(output)
        if loss_match:
            loss_pct = float(loss_match.group(1))

        latency_ms: float | None = None
        rtt_match = _RTT_RE.search(output)
        if rtt_match:
            latency_ms = float(rtt_match.group(2))

        return {
            "target": host,
            "latency_ms": latency_ms,
            "loss_pct": loss_pct,
            "reachable": loss_pct < 100.0,  # noqa: PLR2004
        }
    except FileNotFoundError:
        return {"target": host, "latency_ms": None, "loss_pct": 100.0, "reachable": False,
                "error": "ping not found"}
    except subprocess.TimeoutExpired:
        return {"target": host, "latency_ms": None, "loss_pct": 100.0, "reachable": False,
                "error": "timeout"}


_MAX_TARGETS = 50


def collect(targets: list[str] | None = None) -> dict[str, Any]:
    """Ping configured targets and return latency/loss data."""
    hosts = targets or DEFAULT_TARGETS
    if len(hosts) > _MAX_TARGETS:
        hosts = hosts[:_MAX_TARGETS]
    results = [_ping(h) for h in hosts]
    reachable = sum(1 for r in results if r.get("reachable"))
    return {
        "probes": results,
        "total": len(results),
        "reachable": reachable,
        "unreachable": len(results) - reachable,
    }
