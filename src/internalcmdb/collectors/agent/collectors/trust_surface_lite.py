"""Collector: trust_surface_lite — SSH keys, open ports. Tier: 1h."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _list_ssh_keys() -> list[dict[str, str]]:
    """List SSH authorized keys and host keys."""
    keys: list[dict[str, str]] = []

    # Host keys
    ssh_dir = Path("/etc/ssh")
    if ssh_dir.exists():
        for f in ssh_dir.glob("ssh_host_*_key.pub"):
            keys.append({"type": "host_key", "path": str(f), "algorithm": f.stem})

    # Authorized keys for root and common users
    for user_home in [Path("/root"), *Path("/home").glob("*")]:
        auth_file = user_home / ".ssh" / "authorized_keys"
        if auth_file.exists():
            try:
                count = sum(1 for line in auth_file.read_text().splitlines() if line.strip())
                keys.append(
                    {
                        "type": "authorized_keys",
                        "path": str(auth_file),
                        "key_count": str(count),
                    }
                )
            except PermissionError:
                keys.append(
                    {"type": "authorized_keys", "path": str(auth_file), "error": "permission"}
                )
    return keys


def _listening_ports() -> list[dict[str, str]]:
    """Return listening TCP ports via ``ss -tlnp``."""
    try:
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        ports = []
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 4:  # noqa: PLR2004
                ports.append({"state": parts[0], "local_addr": parts[3]})
        return ports
    except FileNotFoundError, subprocess.TimeoutExpired:
        return []


def collect() -> dict[str, Any]:
    """Return trust surface lite payload."""
    ssh_keys = _list_ssh_keys()
    ports = _listening_ports()
    return {
        "ssh_keys": ssh_keys,
        "ssh_key_count": len(ssh_keys),
        "listening_ports": ports,
        "listening_port_count": len(ports),
    }
