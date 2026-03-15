"""Collector: security_posture — firewall, fail2ban, audit config. Tier: 3h."""

from __future__ import annotations

import subprocess
from typing import Any


def _iptables_rules() -> list[str]:
    """Return iptables rules."""
    try:
        result = subprocess.run(
            ["iptables", "-L", "-n", "--line-numbers"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return result.stdout.strip().splitlines() if result.returncode == 0 else []
    except FileNotFoundError, subprocess.TimeoutExpired:
        return []


def _ufw_status() -> dict[str, str | bool]:
    """Return UFW status."""
    try:
        result = subprocess.run(
            ["ufw", "status", "verbose"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return {"raw": result.stdout.strip(), "active": "active" in result.stdout.lower()}
    except FileNotFoundError, subprocess.TimeoutExpired:
        return {"raw": "", "active": "unknown"}


def _fail2ban_status() -> dict[str, Any]:
    """Return fail2ban jail status."""
    try:
        result = subprocess.run(
            ["fail2ban-client", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            return {"installed": False}
        jails = []
        for line in result.stdout.splitlines():
            if "Jail list" in line:
                jail_part = line.split(":", 1)
                if len(jail_part) > 1:
                    jails = [j.strip() for j in jail_part[1].split(",") if j.strip()]
        return {"installed": True, "jails": jails}
    except FileNotFoundError, subprocess.TimeoutExpired:
        return {"installed": False}


def collect() -> dict[str, Any]:
    """Return security posture payload."""
    return {
        "iptables_rules": _iptables_rules(),
        "ufw": _ufw_status(),
        "fail2ban": _fail2ban_status(),
    }
