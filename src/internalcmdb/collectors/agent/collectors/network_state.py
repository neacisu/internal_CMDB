"""Collector: network_state — interfaces, IPs, routes. Tier: 5min."""

from __future__ import annotations

import json
import subprocess
from typing import Any


def _ip_addr() -> list[dict[str, Any]]:
    """Return parsed ``ip -j addr`` output."""
    try:
        result = subprocess.run(
            ["ip", "-j", "addr"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)  # type: ignore[no-any-return]
    except FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError:
        pass
    return []


def _ip_route() -> list[dict[str, Any]]:
    """Return parsed ``ip -j route`` output."""
    try:
        result = subprocess.run(
            ["ip", "-j", "route"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)  # type: ignore[no-any-return]
    except FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError:
        pass
    return []


def collect() -> dict[str, Any]:
    """Return network state payload."""
    interfaces = _ip_addr()
    routes = _ip_route()
    return {
        "interfaces": interfaces,
        "interface_count": len(interfaces),
        "routes": routes,
        "route_count": len(routes),
    }
