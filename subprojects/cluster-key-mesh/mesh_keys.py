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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Cluster definition — alias (used from localhost) + IP (used for node↔node)
# ---------------------------------------------------------------------------
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
    "ConnectTimeout=8",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "LogLevel=ERROR",
]


# ---------------------------------------------------------------------------
# Core SSH helper
# ---------------------------------------------------------------------------


def ssh(host: str, command: str, timeout: int = 20) -> tuple[int, str, str]:
    cmd = ["ssh"] + _SSH_OPTS + [host, command]
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
    keys: list[str] = field(default_factory=list)
    error: str | None = None


def collect_pubkeys(alias: str) -> CollectResult:
    rc, out, err = ssh(
        alias,
        'for f in /root/.ssh/*.pub; do [ -f "$f" ] && cat "$f"; done 2>/dev/null || true',
    )
    if rc == 124:
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
    errors: list[str] = field(default_factory=list)


def install_keys_on_host(alias: str, all_keys: list[str], dry_run: bool) -> DistributeResult:
    result = DistributeResult(alias=alias)
    for key in all_keys:
        parts = key.split()
        if len(parts) < 2:
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
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
    args = parser.parse_args()

    aliases = [a for a, _ in CLUSTER]
    ips = {a: ip for a, ip in CLUSTER}
    w = max(len(a) for a in aliases)

    # ── Phase 1: Collect ──────────────────────────────────────────────────
    print(header(f"\n{'═' * 60}"))
    print(header(" PHASE 1 — Collecting public keys from all nodes"))
    print(header(f"{'═' * 60}"))

    collect_results: dict[str, CollectResult] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(collect_pubkeys, alias): alias for alias in aliases}
        for future in as_completed(futures):
            r = future.result()
            collect_results[r.alias] = r
            status = ok(f"{len(r.keys)} key(s)") if not r.error else fail(f"ERROR: {r.error}")
            print(f"  [{r.alias:<{w}}]  {status}")

    all_keys: list[str] = []
    seen_bodies: set[str] = set()
    for alias in aliases:
        for key in collect_results[alias].keys:
            parts = key.split()
            if len(parts) >= 2 and parts[1] not in seen_bodies:
                seen_bodies.add(parts[1])
                all_keys.append(key)

    print(f"\n  Total unique keys collected: {BOLD}{len(all_keys)}{RESET}")

    if not all_keys:
        print(fail("No keys collected. Cannot continue."))
        return 2

    if args.dry_run:
        print(
            f"\n  {YELLOW}[DRY-RUN]{RESET} Would distribute {len(all_keys)} keys to {len(aliases)} nodes."
        )

    # ── Phase 2: Distribute ───────────────────────────────────────────────
    print(header(f"\n{'═' * 60}"))
    action = "Simulating distribution" if args.dry_run else "Distributing keys"
    print(header(f" PHASE 2 — {action} to all nodes"))
    print(header(f"{'═' * 60}"))

    dist_results: list[DistributeResult] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures_d = {
            ex.submit(install_keys_on_host, alias, all_keys, args.dry_run): alias
            for alias in aliases
        }
        for future in as_completed(futures_d):
            r = future.result()
            dist_results.append(r)
            status = (
                ok(f"added={r.added}")
                if not r.errors
                else fail(f"added={r.added} skipped={r.skipped}")
            )
            print(f"  [{r.alias:<{w}}]  {status}")
            for e in r.errors:
                print(f"    {fail(e)}")

    total_added = sum(r.added for r in dist_results)
    total_errors = sum(len(r.errors) for r in dist_results)
    print(
        f"\n  Total keys installed: {BOLD}{total_added}{RESET}  |  Errors: {fail(str(total_errors)) if total_errors else ok('0')}"
    )

    # ── Phase 3: Verify (optional) ────────────────────────────────────────
    if args.verify:
        print(header(f"\n{'═' * 60}"))
        print(
            header(
                f" PHASE 3 — Verifying pairwise connectivity ({len(aliases) * (len(aliases) - 1)} pairs)"
            )
        )
        print(header(f"{'═' * 60}"))

        verify_results: list[VerifyResult] = []
        pairs = [
            (src, dst_alias, ips[dst_alias])
            for src in aliases
            for dst_alias in aliases
            if src != dst_alias
        ]

        with ThreadPoolExecutor(max_workers=min(args.workers * 4, 32)) as ex:
            futures_v = {
                ex.submit(verify_pair, src, dst_alias, dst_ip, args.verify_timeout): (
                    src,
                    dst_alias,
                )
                for src, dst_alias, dst_ip in pairs
            }
            for future in as_completed(futures_v):
                verify_results.append(future.result())

        verify_results.sort(key=lambda r: (r.src, r.dst_alias))

        # Print matrix-style
        print(f"\n  {'FROM \\ TO':<{w}}  " + "  ".join(f"{a:<{w}}" for a in aliases))
        print(f"  {'-' * w}  " + "  ".join("-" * w for _ in aliases))

        by_src: dict[str, dict[str, VerifyResult]] = {}
        for vr in verify_results:
            by_src.setdefault(vr.src, {})[vr.dst_alias] = vr

        ok_total = fail_total = 0
        for src in aliases:
            row = f"  {src:<{w}}  "
            for dst in aliases:
                if src == dst:
                    row += f"{'--':<{w}}  "
                else:
                    vr = by_src.get(src, {}).get(dst)
                    if vr and vr.ok:
                        row += ok(f"{'OK':<{w}}") + "  "
                        ok_total += 1
                    else:
                        detail = vr.detail[:w] if vr else "err"
                        row += fail(f"{'FAIL':<{w}}") + "  "
                        fail_total += 1
            print(row)

        print(
            f"\n  Pairs OK: {ok(str(ok_total))}  |  Pairs FAIL: {fail(str(fail_total)) if fail_total else ok('0')}"
        )

    print(header(f"\n{'═' * 60}\n"))
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
