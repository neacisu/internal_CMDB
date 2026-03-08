#!/usr/bin/env python3
"""Read-only runtime posture audit for continuity, release, and AI surfaces.

Collects live facts from SSH-reachable hosts without modifying remote state:
  - host metadata and mounted paths relevant to internalCMDB
  - Docker container and image posture
  - backup, restore, HA, and release automation indicators
  - systemd timers/services and cron entries related to continuity and release
  - AI runtime indicators from running containers and services

Examples:
  python subprojects/runtime-posture-audit/audit_runtime_posture.py
  python subprojects/runtime-posture-audit/audit_runtime_posture.py \
      --host orchestrator --host postgres-main --host hz.113
  python subprojects/runtime-posture-audit/audit_runtime_posture.py --json -
"""

from __future__ import annotations

import argparse
import functools
import json
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_result_store import build_result_envelope, is_local_host, write_retained_result

_Runner = Callable[[str], tuple[int, str, str]]

DEFAULT_HOSTS = [
    "orchestrator",
    "postgres-main",
    "imac",
    "hz.62",
    "hz.113",
    "hz.118",
    "hz.123",
    "hz.157",
    "hz.164",
    "hz.215",
    "hz.223",
    "hz.247",
]
RESULT_TYPE = "runtime_posture"
SSH_OPTS = [
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "LogLevel=ERROR",
]

AUDIT_CMD = r"""
set -u
echo "HOST=$(hostname 2>/dev/null || true)"
echo "DATE_UTC=$(date -u +%FT%TZ 2>/dev/null || true)"
echo "OS=$(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2- | tr -d '"' || true)"
echo "KERNEL=$(uname -r 2>/dev/null || true)"
echo "=== PATHS ==="
for p in \
  /mnt/HC_Volume_105014654 \
  /mnt/HC_Volume_105014654/docker \
  /mnt/HC_Volume_105014654/postgresql \
  /mnt/HC_Volume_105014654/postgresql/internalcmdb \
  /mnt/HC_Volume_105014654/postgresql/internalcmdb/backups \
  /mnt/HC_Volume_105014654/postgresql/internalcmdb/exports \
  /etc/traefik \
  /opt \
  /srv
do
  if [ -e "$p" ]; then
    stat_out=$(stat -f '%Sp|%Su|%Sg' "$p" 2>/dev/null \
      || stat -c '%A|%U|%G' "$p" 2>/dev/null || echo '?|?|?')
    echo "PATH|$p|present|$stat_out"
  else
    echo "PATH|$p|missing|-"
  fi
done
echo "=== DOCKER ==="
if command -v docker >/dev/null 2>&1; then
  echo "DOCKER_PRESENT=yes"
  docker version --format 'SERVER={{.Server.Version}}' 2>/dev/null || true
  docker ps --format 'CONTAINER|{{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null || true
  docker ps -a --format 'CONTAINER_ALL|{{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null || true
  docker image ls --format 'IMAGE|{{.Repository}}:{{.Tag}}|{{.ID}}' 2>/dev/null || true
else
  echo "DOCKER_PRESENT=no"
fi
echo "=== SYSTEMD_TIMERS ==="
TIMER_PAT='backup|restore|postgres|pg_|pg-|wal|recovery'
TIMER_PAT="${TIMER_PAT}|release|deploy|sync|renew|cert|acme"
TIMER_PAT="${TIMER_PAT}|grafana|prometheus|loki|tempo|ollama|vllm|model|vector"
systemctl list-timers --all --no-pager --no-legend 2>/dev/null \
| grep -Ei "${TIMER_PAT}" \
|| true
echo "=== SYSTEMD_UNITS ==="
UNIT_PAT='backup|restore|postgres|pg_|pg-|wal|recovery|patroni|repmgr'
UNIT_PAT="${UNIT_PAT}|keepalived|traefik|grafana|prometheus|loki|tempo"
UNIT_PAT="${UNIT_PAT}|ollama|vllm|model|vector|runner|jenkins|drone|argo"
systemctl list-units --type=service --all --no-pager --no-legend 2>/dev/null \
| grep -Ei "${UNIT_PAT}" \
|| true
echo "=== CRON ==="
for f in /etc/crontab /etc/cron.d/*; do
  [ -f "$f" ] || continue
  echo "CRONFILE|$f"
  CRON_PAT='backup|restore|postgres|pg_dump|pg_basebackup|wal'
  CRON_PAT="${CRON_PAT}|recovery|release|deploy|renew|cert|acme"
  CRON_PAT="${CRON_PAT}|model|ollama|vllm|vector"
  grep -Ei "${CRON_PAT}" "$f" 2>/dev/null || true
done
echo "=== INDICATORS ==="
IND_PAT='patroni|repmgr|pgbackrest|wal-g|restic|borg|keepalived'
IND_PAT="${IND_PAT}|haproxy|traefik|grafana|prometheus|loki|tempo"
IND_PAT="${IND_PAT}|ollama|vllm|text-generation|open-webui|litellm"
IND_PAT="${IND_PAT}|runner|jenkins|drone|argo"
ps aux 2>/dev/null \
| grep -Eiv 'grep|audit_runtime_posture' \
| grep -Ei "${IND_PAT}" || true
echo "=== END ==="
"""


@dataclass
class HostAuditResult:
    alias: str
    ok: bool
    error: str | None
    data: dict[str, Any]


def ssh(host: str, command: str, timeout: int = 30) -> tuple[int, str, str]:
    result = subprocess.run(
        ["ssh", *SSH_OPTS, host, command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _run_local(command: str, timeout: int = 30) -> tuple[int, str, str]:
    """Execute *command* in a local shell (no SSH hop needed)."""
    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _parse_kv_preamble(line: str, data: dict[str, Any]) -> bool:
    """Parse key=value header lines. Returns True if the line was consumed."""
    for key in ("HOST", "DATE_UTC", "OS", "KERNEL"):
        prefix = f"{key}="
        if line.startswith(prefix):
            data[key.lower()] = line.split("=", 1)[1]
            return True
    return False


def _parse_docker_state_line(line: str, data: dict[str, Any]) -> bool:
    """Parse DOCKER_PRESENT/SERVER lines. Returns True if consumed."""
    if line == "DOCKER_PRESENT=yes":
        data["docker_present"] = True
        return True
    if line == "DOCKER_PRESENT=no":
        data["docker_present"] = False
        return True
    if line.startswith("SERVER="):
        data["docker_server"] = line.split("=", 1)[1]
        return True
    return False


def _parse_record_line(line: str, data: dict[str, Any]) -> bool:
    """Parse structured PATH|, CONTAINER|, IMAGE| lines. Returns True if consumed."""
    if _parse_docker_state_line(line, data):
        return True
    if line.startswith("PATH|"):
        _, path, state, meta = line.split("|", 3)
        data["paths"].append({"path": path, "state": state, "meta": meta})
        return True
    if line.startswith("CONTAINER|"):
        _, name, image, status = line.split("|", 3)
        data["containers"].append({"name": name, "image": image, "status": status})
        return True
    if line.startswith("CONTAINER_ALL|"):
        _, name, image, status = line.split("|", 3)
        data["containers_all"].append({"name": name, "image": image, "status": status})
        return True
    if line.startswith("IMAGE|"):
        _, image, image_id = line.split("|", 2)
        data["images"].append({"image": image, "id": image_id})
        return True
    return False


def _apply_section_line(
    line: str,
    section: str,
    data: dict[str, Any],
    cron_data: dict[str, list[str]],
    current_cron: str,
) -> None:
    """Append a line to the active section collection."""
    if section == "=== SYSTEMD_TIMERS ===":
        data["systemd_timers"].append(line)
    elif section == "=== SYSTEMD_UNITS ===":
        data["systemd_units"].append(line)
    elif section == "=== CRON ===" and current_cron:
        cron_data[current_cron].append(line)
    elif section == "=== INDICATORS ===":
        data["indicators"].append(line)


def parse_output(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "host": "",
        "date_utc": "",
        "os": "",
        "kernel": "",
        "paths": [],
        "docker_present": False,
        "docker_server": "",
        "containers": [],
        "containers_all": [],
        "images": [],
        "systemd_timers": [],
        "systemd_units": [],
        "cron": {},
        "indicators": [],
    }
    section = ""
    current_cron = ""
    cron_data: dict[str, list[str]] = {}

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _parse_kv_preamble(line, data):
            continue
        if line.startswith("=== ") and line.endswith(" ==="):
            section = line
            continue
        if line.startswith("CRONFILE|"):
            current_cron = line.split("|", 1)[1]
            cron_data[current_cron] = []
            continue
        if _parse_record_line(line, data):
            continue
        _apply_section_line(line, section, data, cron_data, current_cron)

    data["cron"] = cron_data
    return data


def audit_host(alias: str) -> HostAuditResult:
    runner: _Runner = _run_local if is_local_host(alias) else functools.partial(ssh, alias)
    try:
        rc, out, err = runner(AUDIT_CMD)
    except subprocess.TimeoutExpired:
        return HostAuditResult(alias=alias, ok=False, error="timeout", data={})
    except Exception as exc:
        return HostAuditResult(alias=alias, ok=False, error=str(exc), data={})

    if rc != 0:
        detail = err.strip() or f"ssh exit {rc}"
        return HostAuditResult(alias=alias, ok=False, error=detail, data={})
    return HostAuditResult(alias=alias, ok=True, error=None, data=parse_output(out))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only runtime posture audit.")
    parser.add_argument("--host", action="append", default=[], help="SSH alias to audit")
    parser.add_argument("--workers", type=int, default=6, help="Parallel workers")
    parser.add_argument("--json", default=None, help="Output JSON file or - for stdout")
    return parser.parse_args()


def print_result(result: HostAuditResult) -> None:
    if not result.ok:
        print(f"[{result.alias}] ERROR: {result.error}")
        return

    data = result.data
    containers: list[dict[str, Any]] = data.get("containers") or []
    timers: list[str] = data.get("systemd_timers") or []
    units: list[str] = data.get("systemd_units") or []
    indicators: list[str] = data.get("indicators") or []

    print(
        f"[{result.alias}] host={data.get('host')}"
        f" os={data.get('os')} docker={data.get('docker_present')}"
    )
    print(
        f"  containers={len(containers)} timers={len(timers)}"
        f" units={len(units)} indicators={len(indicators)}"
    )
    names: list[str] = [str(item.get("name", "")) for item in containers[:8]]
    if names:
        print(f"  sample_containers={', '.join(names)}")


def main() -> int:
    args = parse_args()
    hosts = args.host or DEFAULT_HOSTS
    results: list[HostAuditResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {executor.submit(audit_host, host): host for host in hosts}
        for future in as_completed(future_map):
            results.append(future.result())

    results.sort(key=lambda item: item.alias)
    for result in results:
        print_result(result)

    if args.json:
        payload: list[dict[str, Any]] = [
            {"alias": r.alias, "ok": r.ok, "error": r.error, "data": r.data} for r in results
        ]
        content = json.dumps(payload, indent=2)
        if args.json == "-":
            print(content)
        else:
            with open(args.json, "w", encoding="utf-8") as handle:
                handle.write(content)

    retained_payload = build_result_envelope(
        RESULT_TYPE,
        {
            "hosts": hosts,
            "workers": args.workers,
            "results": [
                {"alias": result.alias, "ok": result.ok, "error": result.error, "data": result.data}
                for result in results
            ],
        },
    )
    saved_path = write_retained_result(__file__, RESULT_TYPE, retained_payload)
    print(f"Retained result: {saved_path}")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
