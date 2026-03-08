#!/usr/bin/env python3
"""Full-mesh SSH key distribution for the Hetzner cluster.

Three-phase workflow:
  1. COLLECT  — SSH into every node, harvest all ~/.ssh/*.pub keys
  2. DISTRIBUTE — push every collected key to every node (idempotent, no duplicates)
  3. VERIFY   — from every node, test direct SSH to every other node (optional)

Usage:
  python subprojects/cluster-key-mesh/mesh_keys.py
  python subprojects/cluster-key-mesh/mesh_keys.py --dry-run
  python subprojects/cluster-key-mesh/mesh_keys.py --verify
  python subprojects/cluster-key-mesh/mesh_keys.py --workers 16 --verify
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_result_store import build_result_envelope, write_retained_result

# ---------------------------------------------------------------------------
# Cluster definition — alias (used from localhost) + IP (used for node↔node)
# ---------------------------------------------------------------------------
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
    "ConnectTimeout=8",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "LogLevel=ERROR",
]

SSH_TIMEOUT_EXIT_CODE = 124
SSH_KEY_MIN_PARTS = 2
MAX_VERIFY_WORKERS = 32
RESULT_TYPE = "cluster_key_mesh_state"


# ---------------------------------------------------------------------------
# Core SSH helper
# ---------------------------------------------------------------------------


def ssh(host: str, command: str, timeout: int = 20) -> tuple[int, str, str]:
    cmd = ["ssh", *_SSH_OPTS, host, command]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


# ---------------------------------------------------------------------------
# Phase 1 — Collect
# ---------------------------------------------------------------------------


@dataclass
class CollectResult:
    alias: str
    keys: list[str] = field(default_factory=lambda: [])
    error: str | None = None


def collect_pubkeys(alias: str) -> CollectResult:
    rc, out, err = ssh(
        alias,
        'for f in /root/.ssh/*.pub; do [ -f "$f" ] && cat "$f"; done 2>/dev/null || true',
    )
    if rc == SSH_TIMEOUT_EXIT_CODE:
        return CollectResult(alias=alias, error="timeout connecting")
    if rc not in (0, 1):
        return CollectResult(alias=alias, error=f"rc={rc}: {err[:120]}")
    keys = [ln.strip() for ln in out.splitlines() if ln.strip().startswith(("ssh-", "ecdsa-"))]
    if not keys:
        return CollectResult(alias=alias, error="no public keys found")
    return CollectResult(alias=alias, keys=keys)


# ---------------------------------------------------------------------------
# Phase 2 — Distribute
# ---------------------------------------------------------------------------


@dataclass
class DistributeResult:
    alias: str
    added: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=lambda: [])


def install_keys_on_host(alias: str, all_keys: list[str], dry_run: bool) -> DistributeResult:
    result = DistributeResult(alias=alias)
    for key in all_keys:
        parts = key.split()
        if len(parts) < SSH_KEY_MIN_PARTS:
            continue
        key_body = parts[1]  # base64 portion — stable unique identifier, quote-safe

        if dry_run:
            result.added += 1
            continue

        # Idempotent: add only if base64 body not already present
        cmd = (
            f"grep -qF '{key_body}' /root/.ssh/authorized_keys 2>/dev/null"
            f" || echo '{key}' >> /root/.ssh/authorized_keys"
        )
        rc, _, err = ssh(alias, cmd)
        if rc == 0:
            result.added += 1
        else:
            result.skipped += 1
            result.errors.append(f"  key {key[:30]}… rc={rc} {err[:60]}")

    return result


# ---------------------------------------------------------------------------
# Phase 3 — Verify pairwise
# ---------------------------------------------------------------------------


@dataclass
class VerifyResult:
    src: str
    dst_alias: str
    dst_ip: str
    ok: bool
    detail: str


def verify_pair(src_alias: str, dst_alias: str, dst_ip: str, timeout: int = 8) -> VerifyResult:
    cmd = (
        f"ssh -o BatchMode=yes -o ConnectTimeout={timeout}"
        f" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null"
        f" -o LogLevel=ERROR root@{dst_ip} 'echo __MESH_OK__' 2>&1"
    )
    rc, out, _ = ssh(src_alias, cmd, timeout=timeout + 6)
    ok = rc == 0 and "__MESH_OK__" in out
    detail = out[:100] if not ok else "ok"
    return VerifyResult(src=src_alias, dst_alias=dst_alias, dst_ip=dst_ip, ok=ok, detail=detail)


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(s: str) -> str:
    return f"{GREEN}{s}{RESET}"


def fail(s: str) -> str:
    return f"{RED}{s}{RESET}"


def header(s: str) -> str:
    return f"{BOLD}{s}{RESET}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full-mesh SSH key distribution for Hetzner cluster."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate distribution without writing"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Test pairwise SSH connectivity after distribution"
    )
    parser.add_argument(
        "--workers", type=int, default=8, help="Parallel worker threads (default: 8)"
    )
    parser.add_argument(
        "--verify-timeout", type=int, default=8, help="Timeout in seconds for each verify hop"
    )
    return parser.parse_args()


def print_phase_header(title: str) -> None:
    print(header(f"\n{'═' * 60}"))
    print(header(f" {title}"))
    print(header(f"{'═' * 60}"))


def collect_all_keys(
    aliases: list[str],
    workers: int,
    width: int,
) -> tuple[dict[str, CollectResult], list[str]]:
    print_phase_header("PHASE 1 - Collecting public keys from all nodes")

    collect_results: dict[str, CollectResult] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(collect_pubkeys, alias): alias for alias in aliases}
        for collect_future in as_completed(futures):
            collect_result = collect_future.result()
            collect_results[collect_result.alias] = collect_result
            status = (
                ok(f"{len(collect_result.keys)} key(s)")
                if not collect_result.error
                else fail(f"ERROR: {collect_result.error}")
            )
            print(f"  [{collect_result.alias:<{width}}]  {status}")

    all_keys: list[str] = []
    seen_bodies: set[str] = set()
    for alias in aliases:
        for key in collect_results[alias].keys:
            parts = key.split()
            if len(parts) >= SSH_KEY_MIN_PARTS and parts[1] not in seen_bodies:
                seen_bodies.add(parts[1])
                all_keys.append(key)

    print(f"\n  Total unique keys collected: {BOLD}{len(all_keys)}{RESET}")
    return collect_results, all_keys


def distribute_all_keys(
    aliases: list[str],
    all_keys: list[str],
    dry_run: bool,
    workers: int,
    width: int,
) -> list[DistributeResult]:
    action = "Simulating distribution" if dry_run else "Distributing keys"
    print_phase_header(f"PHASE 2 - {action} to all nodes")

    dist_results: list[DistributeResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures_d: dict[Future[DistributeResult], str] = {
            executor.submit(install_keys_on_host, alias, all_keys, dry_run): alias
            for alias in aliases
        }
        for distribute_future in as_completed(futures_d):
            distribute_result = distribute_future.result()
            dist_results.append(distribute_result)
            status = (
                ok(f"added={distribute_result.added}")
                if not distribute_result.errors
                else fail(f"added={distribute_result.added} skipped={distribute_result.skipped}")
            )
            print(f"  [{distribute_result.alias:<{width}}]  {status}")
            for error_line in distribute_result.errors:
                print(f"    {fail(error_line)}")

    return dist_results


def verify_mesh(
    aliases: list[str],
    ips: dict[str, str],
    workers: int,
    verify_timeout: int,
    width: int,
) -> list[VerifyResult]:
    pair_count = len(aliases) * (len(aliases) - 1)
    print_phase_header(f"PHASE 3 - Verifying pairwise connectivity ({pair_count} pairs)")

    verify_results: list[VerifyResult] = []
    pairs = [
        (src, dst_alias, ips[dst_alias])
        for src in aliases
        for dst_alias in aliases
        if src != dst_alias
    ]

    with ThreadPoolExecutor(max_workers=min(workers * 4, MAX_VERIFY_WORKERS)) as executor:
        futures_v: dict[Future[VerifyResult], tuple[str, str]] = {
            executor.submit(verify_pair, src, dst_alias, dst_ip, verify_timeout): (src, dst_alias)
            for src, dst_alias, dst_ip in pairs
        }
        for verify_future in as_completed(futures_v):
            verify_results.append(verify_future.result())

    verify_results.sort(key=lambda result: (result.src, result.dst_alias))
    return verify_results


def print_verify_report(aliases: list[str], verify_results: list[VerifyResult], width: int) -> None:
    print(f"\n  {'FROM \\ TO':<{width}}  " + "  ".join(f"{alias:<{width}}" for alias in aliases))
    print(f"  {'-' * width}  " + "  ".join("-" * width for _ in aliases))

    by_src: dict[str, dict[str, VerifyResult]] = {}
    for verify_result in verify_results:
        by_src.setdefault(verify_result.src, {})[verify_result.dst_alias] = verify_result

    ok_total = 0
    fail_total = 0
    for src in aliases:
        row = f"  {src:<{width}}  "
        for dst in aliases:
            if src == dst:
                row += f"{'--':<{width}}  "
                continue

            current_result = by_src.get(src, {}).get(dst)
            if current_result and current_result.ok:
                row += ok(f"{'OK':<{width}}") + "  "
                ok_total += 1
            else:
                row += fail(f"{'FAIL':<{width}}") + "  "
                fail_total += 1
        print(row)

    fail_label = fail(str(fail_total)) if fail_total else ok("0")
    print(f"\n  Pairs OK: {ok(str(ok_total))}  |  Pairs FAIL: {fail_label}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()

    aliases = [a for a, _ in CLUSTER]
    ips = dict(CLUSTER)
    width = max(len(alias) for alias in aliases)

    _, all_keys = collect_all_keys(aliases, args.workers, width)

    if not all_keys:
        print(fail("No keys collected. Cannot continue."))
        return 2

    if args.dry_run:
        dry_run_message = (
            f"\n  {YELLOW}[DRY-RUN]{RESET} Would distribute {len(all_keys)} keys "
            f"to {len(aliases)} nodes."
        )
        print(dry_run_message)

    dist_results = distribute_all_keys(aliases, all_keys, args.dry_run, args.workers, width)

    total_added = sum(r.added for r in dist_results)
    total_errors = sum(len(r.errors) for r in dist_results)
    error_label = fail(str(total_errors)) if total_errors else ok("0")
    print(f"\n  Total keys installed: {BOLD}{total_added}{RESET}  |  Errors: {error_label}")

    verify_results: list[VerifyResult] = []
    if args.verify:
        verify_results = verify_mesh(aliases, ips, args.workers, args.verify_timeout, width)
        print_verify_report(aliases, verify_results, width)

    retained_payload = build_result_envelope(
        RESULT_TYPE,
        {
            "mode": {
                "dry_run": args.dry_run,
                "verify": args.verify,
                "workers": args.workers,
                "verify_timeout": args.verify_timeout,
            },
            "cluster": [{"alias": alias, "ip": ips[alias]} for alias in aliases],
            "key_inventory": {"unique_key_count": len(all_keys)},
            "distribution_results": [asdict(result) for result in dist_results],
            "verification_results": [asdict(result) for result in verify_results],
            "summary": {
                "total_added": total_added,
                "total_errors": total_errors,
                "verify_pairs": len(verify_results),
                "verify_failures": sum(1 for result in verify_results if not result.ok),
            },
        },
    )
    saved_path = write_retained_result(__file__, RESULT_TYPE, retained_payload)

    print(header(f"\n{'═' * 60}\n"))
    print(f"Retained result: {saved_path}")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
