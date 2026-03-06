#!/usr/bin/env python3
"""Add cluster IPs as allowed in firewall on every node — non-destructive (append only).

Detects firewall type per node:
  - UFW active  → ufw allow from <IP> to any
  - iptables     → insert ACCEPT rules for each cluster IP in INPUT and OUTPUT chains

Existing rules are never removed.
"""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

CLUSTER: list[tuple[str, str]] = [
    ("hz.113", "49.13.97.113"),
    ("hz.118", "95.216.72.118"),
    ("hz.123", "94.130.68.123"),
    ("hz.157", "95.216.225.157"),
    ("hz.164", "135.181.183.164"),
    ("hz.215", "95.216.36.215"),
    ("hz.223", "95.217.32.223"),
    ("hz.247", "95.216.68.247"),
]

_SSH_OPTS = [
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


def ssh(host: str, command: str, timeout: int = 30) -> tuple[int, str, str]:
    cmd = ["ssh"] + _SSH_OPTS + [host, command]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


def detect_firewall(alias: str) -> str:
    rc, out, _ = ssh(alias, "ufw status 2>/dev/null | head -1")
    if rc == 0 and "active" in out.lower():
        return "ufw"
    return "iptables"


def allow_ufw(alias: str, peer_ips: list[str]) -> list[str]:
    """Add ufw allow rules non-destructively. Returns list of log lines."""
    logs = []
    for ip in peer_ips:
        # Check if rule already exists
        rc_check, out_check, _ = ssh(
            alias, f"ufw status | grep -qF '{ip}' && echo EXISTS || echo MISSING"
        )
        if "EXISTS" in out_check:
            logs.append(f"  [SKIP] {ip} already in ufw rules")
            continue
        rc, _, err = ssh(alias, f"ufw allow from {ip} to any comment 'cluster-mesh' && echo UFW_OK")
        if rc == 0:
            logs.append(f"  [ADD ] ufw allow from {ip}")
        else:
            logs.append(f"  [ERR ] ufw allow from {ip}: {err[:80]}")
    return logs


def allow_iptables(alias: str, peer_ips: list[str]) -> list[str]:
    """Add iptables ACCEPT rules non-destructively via -C check before -I insert."""
    logs = []
    for ip in peer_ips:
        for chain, flag in [("INPUT", "-s"), ("OUTPUT", "-d")]:
            # -C returns 0 if rule already exists, non-zero if missing
            check = f"iptables -C {chain} {flag} {ip} -j ACCEPT 2>/dev/null"
            rc_check, _, _ = ssh(alias, check)
            if rc_check == 0:
                logs.append(f"  [SKIP] iptables {chain} {flag} {ip} ACCEPT — already exists")
                continue
            rc, _, err = ssh(alias, f"iptables -I {chain} 1 {flag} {ip} -j ACCEPT")
            if rc == 0:
                logs.append(f"  [ADD ] iptables -I {chain} 1 {flag} {ip} ACCEPT")
            else:
                logs.append(f"  [ERR ] iptables {chain} {flag} {ip}: {err[:80]}")
    return logs


def process_node(alias: str, peer_ips: list[str]) -> tuple[str, str, list[str]]:
    fw = detect_firewall(alias)
    if fw == "ufw":
        logs = allow_ufw(alias, peer_ips)
    else:
        logs = allow_iptables(alias, peer_ips)
    return alias, fw, logs


BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


def main() -> int:
    aliases = [a for a, _ in CLUSTER]
    ip_map = {a: ip for a, ip in CLUSTER}
    print(f"{BOLD}Cluster IPs to allow: {', '.join(ip_map.values())}{RESET}\n")

    results: list[tuple[str, str, list[str]]] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {
            ex.submit(process_node, alias, [ip for a, ip in CLUSTER if a != alias]): alias
            for alias in aliases
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: r[0])
    errors = 0
    for alias, fw, logs in results:
        adds = sum(1 for l in logs if "[ADD " in l)
        skips = sum(1 for l in logs if "[SKIP]" in l)
        errs = sum(1 for l in logs if "[ERR ]" in l)
        errors += errs
        color = RED if errs else GREEN
        print(
            f"{BOLD}[{alias}]{RESET} firewall={fw}  added={color}{adds}{RESET}  skipped={skips}  errors={errs}"
        )
        for line in logs:
            print(line)
        print()

    status = (
        f"{GREEN}All done, 0 errors{RESET}"
        if not errors
        else f"{RED}{errors} error(s) — check output above{RESET}"
    )
    print(f"{BOLD}{'═' * 60}{RESET}")
    print(f" {status}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
