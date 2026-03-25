"""Collector: systemd_state — unit status, timers. Tier: 30min."""

from __future__ import annotations

import json
import subprocess
from typing import Any


def _list_units() -> list[dict[str, str]]:
    """Return systemd units via ``systemctl list-units``."""
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--output=json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)  # type: ignore[no-any-return]
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return []


def _list_timers() -> list[dict[str, str]]:
    """Return systemd timers via ``systemctl list-timers``."""
    try:
        result = subprocess.run(
            ["systemctl", "list-timers", "--all", "--output=json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)  # type: ignore[no-any-return]
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return []


def collect() -> dict[str, Any]:
    """Return systemd state payload."""
    units = _list_units()
    timers = _list_timers()
    active = sum(1 for u in units if u.get("active") == "active")
    failed = sum(1 for u in units if u.get("active") == "failed")
    return {
        "units": units,
        "timers": timers,
        "unit_count": len(units),
        "active_count": active,
        "failed_count": failed,
        "timer_count": len(timers),
    }
