from __future__ import annotations

import json
import re
import shlex
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Local-host detection
# ---------------------------------------------------------------------------


def _parse_ssh_hostname(alias: str) -> str | None:
    """Return the HostName value for *alias* from ~/.ssh/config, or None."""
    config_path = Path.home() / ".ssh" / "config"
    if not config_path.exists():
        return None
    in_block = False
    for raw in config_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = shlex.split(line)
        if not parts:
            continue
        key = parts[0].lower()
        value = parts[1] if len(parts) > 1 else ""
        if key == "host":
            # A Host block can list multiple patterns; check exact match.
            in_block = alias.lower() in [p.lower() for p in parts[1:]]
        elif in_block and key == "hostname":
            return value.strip()
    return None


def _local_interface_ips() -> frozenset[str]:
    """Return all IPv4 addresses assigned to local network interfaces."""
    for cmd in (["ip", "-4", "addr", "show"], ["ifconfig"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=3).stdout
            found = re.findall(r"\binet (\d+\.\d+\.\d+\.\d+)", out)
            if found:
                return frozenset(found)
        except FileNotFoundError, subprocess.TimeoutExpired:
            continue
    return frozenset()


def is_local_host(alias: str) -> bool:
    """Return True when the SSH *alias* refers to the machine running this process.

    Detection uses two independent strategies so that a stale IP in ~/.ssh/config
    (e.g. DHCP reassignment) does not cause a false-negative:

    1. **Hostname substring match** — the alias tokens (letters/digits) are
       compared case-insensitively against the local hostname.  For example,
       alias ``imac`` matches hostname ``Alexs-iMac.local``.
    2. **IP intersection** — the HostName from ~/.ssh/config is resolved to IPv4
       addresses and compared against all local interface IPs.
    """
    # --- Strategy 1: hostname name match ---
    local_hostname = socket.gethostname().lower()
    # Strip non-alphanumeric separators for a robust substring comparison.
    alias_clean = re.sub(r"[^a-z0-9]", "", alias.lower())
    hostname_clean = re.sub(r"[^a-z0-9]", "", local_hostname)
    if alias_clean and (alias_clean in hostname_clean or hostname_clean in alias_clean):
        return True

    # --- Strategy 2: SSH HostName → IP intersection ---
    ssh_hostname = _parse_ssh_hostname(alias)
    if ssh_hostname:
        try:
            resolved = {
                info[4][0] for info in socket.getaddrinfo(ssh_hostname, None, socket.AF_INET)
            }
        except socket.gaierror:
            resolved = {ssh_hostname}  # direct IP literal
        if resolved & _local_interface_ips():
            return True

    return False


CURRENT_FILENAME = "current.json"
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"
MAX_HISTORY_FILES = 2


def build_result_envelope(result_type: str, payload: Any) -> dict[str, Any]:
    return {
        "result_type": result_type,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "payload": payload,
    }


def write_retained_result(script_path: str | Path, result_type: str, payload: Any) -> Path:
    results_dir = Path(script_path).resolve().parent / "results" / result_type
    results_dir.mkdir(parents=True, exist_ok=True)

    current_path = results_dir / CURRENT_FILENAME
    if current_path.exists():
        _archive_current_file(current_path, results_dir, result_type)

    current_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _prune_history(results_dir)
    return current_path


def _archive_current_file(current_path: Path, results_dir: Path, result_type: str) -> None:
    archive_stamp = _read_archive_stamp(current_path)
    archive_path = results_dir / f"{result_type}-{archive_stamp}.json"
    suffix = 1
    while archive_path.exists():
        archive_path = results_dir / f"{result_type}-{archive_stamp}-{suffix}.json"
        suffix += 1
    archive_path.write_text(current_path.read_text(encoding="utf-8"), encoding="utf-8")


def _read_archive_stamp(current_path: Path) -> str:
    try:
        parsed = json.loads(current_path.read_text(encoding="utf-8"))
        generated_at = parsed.get("generated_at_utc")
        if isinstance(generated_at, str):
            normalized = generated_at.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).astimezone(UTC).strftime(TIMESTAMP_FORMAT)
    except OSError, ValueError, TypeError, json.JSONDecodeError:
        pass

    return datetime.fromtimestamp(current_path.stat().st_mtime, UTC).strftime(TIMESTAMP_FORMAT)


def _prune_history(results_dir: Path) -> None:
    history_files = sorted(
        [path for path in results_dir.glob("*.json") if path.name != CURRENT_FILENAME],
        key=lambda path: path.name,
        reverse=True,
    )
    for stale_path in history_files[MAX_HISTORY_FILES:]:
        stale_path.unlink(missing_ok=True)
