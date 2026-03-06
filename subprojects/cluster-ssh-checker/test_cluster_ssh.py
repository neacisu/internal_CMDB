#!/usr/bin/env python3
"""Test SSH connectivity for all concrete hosts defined in ~/.ssh/config.

Examples:
  python subprojects/cluster-ssh-checker/test_cluster_ssh.py
  python subprojects/cluster-ssh-checker/test_cluster_ssh.py --timeout 4 --workers 12
  python subprojects/cluster-ssh-checker/test_cluster_ssh.py --include-regex '^(hz\\.|orchestrator|postgres-main)'
"""

from __future__ import annotations

import argparse
import concurrent.futures
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    host: str
    ok: bool
    return_code: int
    detail: str


def parse_hosts(config_path: Path) -> list[str]:
    """Parse concrete host aliases from an OpenSSH config file."""
    if not config_path.exists():
        raise FileNotFoundError(f"SSH config not found: {config_path}")

    hosts: list[str] = []
    seen: set[str] = set()

    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        parts = shlex.split(line)
        if len(parts) < 2:
            continue

        if parts[0].lower() != "host":
            continue

        for pattern in parts[1:]:
            # Skip wildcards and negated patterns; test only concrete aliases.
            if any(ch in pattern for ch in ("*", "?", "!")):
                continue
            if pattern not in seen:
                seen.add(pattern)
                hosts.append(pattern)

    return hosts


def check_host(host: str, timeout: int) -> CheckResult:
    """Attempt a non-interactive SSH handshake and simple command execution."""
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "NumberOfPasswordPrompts=0",
        "-o",
        f"ConnectTimeout={timeout}",
        host,
        "echo __SSH_OK__",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 3, check=False)
    except subprocess.TimeoutExpired:
        return CheckResult(host=host, ok=False, return_code=124, detail="timeout")
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult(host=host, ok=False, return_code=125, detail=str(exc))

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    if proc.returncode == 0 and "__SSH_OK__" in stdout:
        return CheckResult(host=host, ok=True, return_code=0, detail="ok")

    detail = stderr or stdout or "unknown error"
    return CheckResult(host=host, ok=False, return_code=proc.returncode, detail=detail)


def filter_hosts(
    hosts: list[str], include_regex: str | None, exclude_regex: str | None
) -> list[str]:
    filtered = hosts
    if include_regex:
        include_pat = re.compile(include_regex)
        filtered = [h for h in filtered if include_pat.search(h)]
    if exclude_regex:
        exclude_pat = re.compile(exclude_regex)
        filtered = [h for h in filtered if not exclude_pat.search(h)]
    return filtered


def main() -> int:
    parser = argparse.ArgumentParser(description="Test SSH connectivity to hosts in SSH config.")
    parser.add_argument(
        "--config", default=str(Path.home() / ".ssh" / "config"), help="Path to SSH config"
    )
    parser.add_argument("--timeout", type=int, default=5, help="SSH connect timeout in seconds")
    parser.add_argument("--workers", type=int, default=8, help="Parallel worker count")
    parser.add_argument("--include-regex", default=None, help="Only test hosts matching regex")
    parser.add_argument("--exclude-regex", default=None, help="Skip hosts matching regex")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    hosts = parse_hosts(config_path)
    hosts = filter_hosts(hosts, args.include_regex, args.exclude_regex)

    if not hosts:
        print("No concrete hosts found to test.")
        return 2

    print(f"Testing {len(hosts)} host(s) from {config_path} with timeout={args.timeout}s")

    results: list[CheckResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {executor.submit(check_host, host, args.timeout): host for host in hosts}
        for future in concurrent.futures.as_completed(future_map):
            results.append(future.result())

    results.sort(key=lambda r: r.host)
    width = max(len(r.host) for r in results)

    ok_count = 0
    fail_count = 0

    for result in results:
        status = "OK" if result.ok else "FAIL"
        if result.ok:
            ok_count += 1
        else:
            fail_count += 1
        print(f"[{status:4}] {result.host:<{width}} | rc={result.return_code} | {result.detail}")

    print("-" * 80)
    print(f"Summary: total={len(results)} ok={ok_count} fail={fail_count}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
