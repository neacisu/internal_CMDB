#!/usr/bin/env python3
"""Read-only audit for TLS, secrets, and trust surfaces.

Collects live metadata only, without reading secret values:
  - SSH auth posture and authorized_keys counts
  - secret-bearing file locations and permissions by pattern
  - Let's Encrypt certificate inventory and expiry on reachable hosts
  - live TLS handshake summary for externally reachable endpoints

Examples:
  python subprojects/trust-surface-audit/audit_trust_surface.py
  python subprojects/trust-surface-audit/audit_trust_surface.py \
      --host orchestrator --host postgres-main --host hz.113 \
      --endpoint postgres.orchestrator.neanelu.ro:5432
  python subprojects/trust-surface-audit/audit_trust_surface.py --json -
"""

from __future__ import annotations

import argparse
import functools
import json
import socket
import ssl
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

_SSHDIR_PARTS_FULL = 4
_SSHDIR_PARTS_PARTIAL = 3

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
DEFAULT_ENDPOINTS = [
    "postgres.neanelu.ro:5432",
    "postgres.orchestrator.neanelu.ro:5432",
]
RESULT_TYPE = "trust_surface"
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

REMOTE_CMD = r"""
set -u
echo "HOST=$(hostname 2>/dev/null || true)"
echo "=== SSHD ==="
SSHD_PAT="^(permitrootlogin|passwordauthentication|pubkeyauthentication|port) "
sshd -T 2>/dev/null | grep -E "${SSHD_PAT}" || true
echo "=== SSH_KEYS ==="
for d in /root/.ssh /home/*/.ssh; do
  [ -d "$d" ] || continue
  perms=$(stat -f '%Sp|%Su|%Sg' "$d" 2>/dev/null \
    || stat -c '%A|%U|%G' "$d" 2>/dev/null || echo '?|?|?')
  count=$(find "$d" -maxdepth 1 -name 'authorized_keys' -type f \
    -exec sh -c 'wc -l < "$1"' _ {} \; 2>/dev/null \
    | paste -sd+ - | bc 2>/dev/null || echo 0)
  echo "SSHDIR|$d|$perms|authorized_keys_lines=$count"
done
echo "=== SECRET_PATHS ==="
for base in /etc /opt /srv /root /mnt/HC_Volume_105014654; do
  [ -d "$base" ] || continue
  find "$base" -maxdepth 3 \
    \( -name '*.env' -o -name '*.pem' -o -name '*.key' \
       -o -name '*.crt' -o -name '*.pfx' -o -name 'id_*' \) \
    -type f 2>/dev/null \
  | while read -r f; do
      perms=$(stat -f '%Sp|%Su|%Sg' "$f" 2>/dev/null \
        || stat -c '%A|%U|%G' "$f" 2>/dev/null || echo '?|?|?')
      echo "SECRETPATH|$f|$perms"
    done
done
echo "=== CERTS ==="
for cert in /etc/letsencrypt/live/*/cert.pem /etc/letsencrypt/live/*/fullchain.pem; do
  [ -f "$cert" ] || continue
  info=$(openssl x509 -in "$cert" -noout -subject -issuer -enddate \
    2>/dev/null | tr '\n' '|' || true)
  echo "CERT|$cert|$info"
done
echo "=== END ==="
"""


@dataclass
class HostTrustResult:
    alias: str
    ok: bool
    error: str | None
    data: dict[str, Any]


def ssh(host: str, command: str, timeout: int = 35) -> tuple[int, str, str]:
    result = subprocess.run(
        ["ssh", *SSH_OPTS, host, command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _run_local(command: str, timeout: int = 35) -> tuple[int, str, str]:
    """Execute *command* in a local shell (no SSH hop needed)."""
    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def parse_remote(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "host": "",
        "sshd": [],
        "ssh_dirs": [],
        "secret_paths": [],
        "certs": [],
    }
    section = ""
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("HOST="):
            data["host"] = line.split("=", 1)[1]
            continue
        if line.startswith("=== ") and line.endswith(" ==="):
            section = line
            continue
        if line.startswith("SSHDIR|"):
            parts = line.split("|", 3)
            if len(parts) == _SSHDIR_PARTS_FULL:
                _, path, perms, count = parts
            elif len(parts) == _SSHDIR_PARTS_PARTIAL:
                _, path, perms = parts
                count = "authorized_keys_lines=unknown"
            else:
                continue
            data["ssh_dirs"].append({"path": path, "perms": perms, "count": count})
            continue
        if line.startswith("SECRETPATH|"):
            _, path, perms = line.split("|", 2)
            data["secret_paths"].append({"path": path, "perms": perms})
            continue
        if line.startswith("CERT|"):
            _, path, info = line.split("|", 2)
            data["certs"].append({"path": path, "info": info})
            continue
        if section == "=== SSHD ===":
            data["sshd"].append(line)
    return data


def audit_host(alias: str) -> HostTrustResult:
    runner: _Runner = _run_local if is_local_host(alias) else functools.partial(ssh, alias)
    try:
        rc, out, err = runner(REMOTE_CMD)
    except subprocess.TimeoutExpired:
        return HostTrustResult(alias=alias, ok=False, error="timeout", data={})
    except Exception as exc:
        return HostTrustResult(alias=alias, ok=False, error=str(exc), data={})
    if rc != 0:
        return HostTrustResult(
            alias=alias, ok=False, error=err.strip() or f"ssh exit {rc}", data={}
        )
    return HostTrustResult(alias=alias, ok=True, error=None, data=parse_remote(out))


def tls_probe(endpoint: str, timeout: int = 8) -> dict[str, Any]:
    host, port_str = endpoint.rsplit(":", 1)
    port = int(port_str)
    try:
        context = ssl.create_default_context()
        with (
            socket.create_connection((host, port), timeout=timeout) as sock,
            context.wrap_socket(sock, server_hostname=host) as tls_sock,
        ):
            cert: dict[str, Any] = tls_sock.getpeercert() or {}
            return {
                "endpoint": endpoint,
                "ok": True,
                "subject": cert.get("subject", []),
                "issuer": cert.get("issuer", []),
                "notAfter": cert.get("notAfter"),
                "version": tls_sock.version(),
            }
    except Exception as exc:
        return {"endpoint": endpoint, "ok": False, "error": str(exc)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only trust surface audit.")
    parser.add_argument("--host", action="append", default=[], help="SSH alias to audit")
    parser.add_argument(
        "--endpoint", action="append", default=[], help="TLS endpoint in host:port format"
    )
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--json", default=None, help="Output JSON file or - for stdout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hosts = args.host or DEFAULT_HOSTS
    endpoints = args.endpoint or DEFAULT_ENDPOINTS

    host_results: list[HostTrustResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {executor.submit(audit_host, host): host for host in hosts}
        for future in as_completed(future_map):
            host_results.append(future.result())

    host_results.sort(key=lambda item: item.alias)
    endpoint_results = [tls_probe(endpoint) for endpoint in endpoints]

    for result in host_results:
        if not result.ok:
            print(f"[{result.alias}] ERROR: {result.error}")
            continue
        data = result.data
        print(
            f"[{result.alias}] host={data.get('host')} sshd_lines={len(data.get('sshd', []))} "
            f"secret_paths={len(data.get('secret_paths', []))} certs={len(data.get('certs', []))}"
        )

    for endpoint in endpoint_results:
        if endpoint.get("ok"):
            print(
                f"[tls] {endpoint['endpoint']} ok version={endpoint.get('version')} "
                f"notAfter={endpoint.get('notAfter')}"
            )
        else:
            print(f"[tls] {endpoint['endpoint']} ERROR: {endpoint.get('error')}")

    if args.json:
        payload: dict[str, Any] = {
            "hosts": [
                {"alias": result.alias, "ok": result.ok, "error": result.error, "data": result.data}
                for result in host_results
            ],
            "endpoints": endpoint_results,
        }
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
            "endpoints": endpoints,
            "workers": args.workers,
            "results": {
                "hosts": [
                    {
                        "alias": result.alias,
                        "ok": result.ok,
                        "error": result.error,
                        "data": result.data,
                    }
                    for result in host_results
                ],
                "endpoints": endpoint_results,
            },
        },
    )
    saved_path = write_retained_result(__file__, RESULT_TYPE, retained_payload)
    print(f"Retained result: {saved_path}")

    endpoint_ok = all(bool(item.get("ok")) for item in endpoint_results)
    return 0 if endpoint_ok and all(result.ok for result in host_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
