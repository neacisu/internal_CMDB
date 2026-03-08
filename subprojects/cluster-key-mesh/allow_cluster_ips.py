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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_result_store import build_result_envelope, write_retained_result

CLUSTER: list[tuple[str, str]] = [
    ("hz.62", "95.216.66.62"),
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

ADD_MARKER = "[ADD ]"
SKIP_MARKER = "[SKIP]"
ERROR_MARKER = "[ERR ]"
RESULT_TYPE = "cluster_firewall_state"


def ssh(host: str, command: str, timeout: int = 30) -> tuple[int, str, str]:
    cmd = ["ssh", *_SSH_OPTS, host, command]
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
    logs: list[str] = []
    for ip in peer_ips:
        # Check if rule already exists
        _, out_check, _ = ssh(alias, f"ufw status | grep -qF '{ip}' && echo EXISTS || echo MISSING")
        if "EXISTS" in out_check:
            logs.append(f"  {SKIP_MARKER} {ip} already in ufw rules")
            continue
        rc, _, err = ssh(alias, f"ufw allow from {ip} to any comment 'cluster-mesh' && echo UFW_OK")
        if rc == 0:
            logs.append(f"  {ADD_MARKER} ufw allow from {ip}")
        else:
            logs.append(f"  {ERROR_MARKER} ufw allow from {ip}: {err[:80]}")
    return logs


def allow_iptables(alias: str, peer_ips: list[str]) -> list[str]:
    """Add iptables ACCEPT rules non-destructively via -C check before -I insert."""
    logs: list[str] = []
    for ip in peer_ips:
        for chain, flag in [("INPUT", "-s"), ("OUTPUT", "-d")]:
            # -C returns 0 if rule already exists, non-zero if missing
            check = f"iptables -C {chain} {flag} {ip} -j ACCEPT 2>/dev/null"
            rc_check, _, _ = ssh(alias, check)
            if rc_check == 0:
                logs.append(f"  {SKIP_MARKER} iptables {chain} {flag} {ip} ACCEPT - already exists")
                continue
            rc, _, err = ssh(alias, f"iptables -I {chain} 1 {flag} {ip} -j ACCEPT")
            if rc == 0:
                logs.append(f"  {ADD_MARKER} iptables -I {chain} 1 {flag} {ip} ACCEPT")
            else:
                logs.append(f"  {ERROR_MARKER} iptables {chain} {flag} {ip}: {err[:80]}")
    return logs


def process_node(alias: str, peer_ips: list[str]) -> tuple[str, str, list[str]]:
    fw = detect_firewall(alias)
    logs = allow_ufw(alias, peer_ips) if fw == "ufw" else allow_iptables(alias, peer_ips)
    return alias, fw, logs


BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


def main() -> int:
    aliases = [a for a, _ in CLUSTER]
    ip_map = dict(CLUSTER)
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
        adds = sum(1 for log_line in logs if ADD_MARKER in log_line)
        skips = sum(1 for log_line in logs if SKIP_MARKER in log_line)
        errs = sum(1 for log_line in logs if ERROR_MARKER in log_line)
        errors += errs
        color = RED if errs else GREEN
        print(
            f"{BOLD}[{alias}]{RESET} firewall={fw} "
            f" added={color}{adds}{RESET} skipped={skips} errors={errs}"
        )
        for line in logs:
            print(line)
        print()

    status = (
        f"{GREEN}All done, 0 errors{RESET}"
        if not errors
        else f"{RED}{errors} error(s) — check output above{RESET}"
    )

    retained_payload = build_result_envelope(
        RESULT_TYPE,
        {
            "cluster": [{"alias": alias, "ip": ip} for alias, ip in CLUSTER],
            "results": [
                {
                    "alias": alias,
                    "firewall": fw,
                    "logs": logs,
                    "summary": {
                        "added": sum(1 for log_line in logs if ADD_MARKER in log_line),
                        "skipped": sum(1 for log_line in logs if SKIP_MARKER in log_line),
                        "errors": sum(1 for log_line in logs if ERROR_MARKER in log_line),
                    },
                }
                for alias, fw, logs in results
            ],
            "global_summary": {"error_count": errors},
        },
    )
    saved_path = write_retained_result(__file__, RESULT_TYPE, retained_payload)

    print(f"{BOLD}{'═' * 60}{RESET}")
    print(f" {status}")
    print(f" Retained result: {saved_path}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
