"""Collector: full_hardware — complete hardware inventory. Tier: 12h."""

from __future__ import annotations

import json
import subprocess
from typing import Any


def _lscpu() -> dict[str, str]:
    """Return CPU info from ``lscpu``."""
    try:
        result = subprocess.run(
            ["lscpu", "-J"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)  # type: ignore[no-any-return]
    except FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError:
        pass
    return {}


def _lsblk() -> list[dict[str, Any]]:
    """Return block devices from ``lsblk``."""
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get("blockdevices", [])  # type: ignore[no-any-return]
    except FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError:
        pass
    return []


def _dmidecode_memory() -> list[dict[str, str]]:
    """Return memory module info from ``dmidecode``."""
    try:
        result = subprocess.run(
            ["dmidecode", "-t", "memory"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        modules: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if line.startswith("Size:") and "No Module" not in line:
                current["size"] = line.split(":", 1)[1].strip()
            elif line.startswith("Type:"):
                current["type"] = line.split(":", 1)[1].strip()
            elif line.startswith("Speed:"):
                current["speed"] = line.split(":", 1)[1].strip()
                modules.append(current)
                current = {}
        return modules
    except FileNotFoundError, subprocess.TimeoutExpired:
        return []


def collect() -> dict[str, Any]:
    """Return full hardware inventory payload."""
    return {
        "cpu": _lscpu(),
        "block_devices": _lsblk(),
        "memory_modules": _dmidecode_memory(),
    }
