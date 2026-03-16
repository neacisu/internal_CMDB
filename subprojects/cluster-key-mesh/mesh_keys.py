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
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_result_store import (  # pylint: disable=import-error,wrong-import-position
    build_result_envelope,
    write_retained_result,
)

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

# Storage boxes — restricted SSH shell (no pipes/redirects); key distribution
# is done via SCP upload of a merged authorized_keys file instead of shell commands.
# These receive all cluster keys but do NOT contribute keys to the mesh
# (they are storage targets, not compute nodes).
STORAGE_BOXES: list[str] = [
    "hz.main-sb",  # u502048.your-storagebox.de — FSN1-BX1159
    "hz.sbx1",  # u382766.your-storagebox.de
]

# SSH config blocks to propagate to every compute node so that
# all machines in the cluster can reach storage boxes by alias.
# Format matches the cluster convention: 4-space indent, id_ed25519_production.
STORAGE_BOX_SSH_CONFIG: dict[str, str] = {
    "hz.main-sb": (
        "Host hz.main-sb\n"
        "    HostName u502048.your-storagebox.de\n"
        "    User u502048\n"
        "    Port 23\n"
        "    IdentityFile /root/.ssh/id_ed25519_production\n"
        "    IdentitiesOnly yes\n"
        "    StrictHostKeyChecking no"
    ),
    "hz.sbx1": (
        "Host hz.sbx1\n"
        "    HostName u382766.your-storagebox.de\n"
        "    User u382766-sub2\n"
        "    Port 23\n"
        "    IdentityFile /root/.ssh/id_ed25519_production\n"
        "    IdentitiesOnly yes\n"
        "    StrictHostKeyChecking no"
    ),
}

SSH_CONFIG_INCLUDE_LINE = "Include /root/.ssh/config.d/*.conf"
MANAGED_SSH_CONFIG_PATH = "/root/.ssh/config.d/internalcmdb-cluster.conf"


def build_compute_ssh_config(alias: str, ip: str) -> str:
    return (
        f"Host {alias}\n"
        f"    HostName {ip}\n"
        "    User root\n"
        "    IdentityFile /root/.ssh/id_ed25519_production\n"
        "    IdentityFile /root/.ssh/id_ed25519\n"
        "    IdentityFile /root/.ssh/id_rsa\n"
        "    IdentitiesOnly yes\n"
        "    StrictHostKeyChecking no"
    )


COMPUTE_SSH_CONFIG: dict[str, str] = {
    alias: build_compute_ssh_config(alias, ip) for alias, ip in CLUSTER
}

# LXC containers — reachable only via their gateway (Proxmox host).
# From the gateway, id_ed25519_production is already authorized on each LXC.
# Format: (alias, ip, gateway_alias)
# NOTE: cerniq LXCs (10.10.1.x) are on an isolated VLAN not routable from any
# hz.* node directly — excluded until a reachable gateway is confirmed.
PROXIED_NODES: list[tuple[str, str, str]] = [
    ("postgres-main", "10.0.1.107", "hz.164"),  # on hz.164's private network
    ("neanelu-prod", "10.0.1.111", "hz.164"),
    ("neanelu-staging", "10.0.1.112", "hz.164"),
    ("neanelu-ci", "10.0.1.108", "hz.164"),
    ("staging-cerniq", "10.0.1.110", "hz.164"),
    ("prod-cerniq", "10.0.1.109", "hz.164"),
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
VERIFY_RETRIES = 3


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


def ssh_via_gateway(
    gateway: str, target_ip: str, command: str, timeout: int = 25
) -> tuple[int, str, str]:
    """Run a command on a proxied node (LXC) via its gateway using the gateway's production key."""
    inner = (
        f"ssh -o BatchMode=yes -o ConnectTimeout=8"
        f" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null"
        f" -o LogLevel=ERROR"
        f" -i /root/.ssh/id_ed25519_production"
        f" root@{target_ip} {command!r}"
    )
    return ssh(gateway, inner, timeout=timeout)


# ---------------------------------------------------------------------------
# Phase 0 — Propagate storage-box SSH config to all compute nodes
# ---------------------------------------------------------------------------


@dataclass
class ConfigPropagateResult:
    alias: str
    added: list[str] = field(default_factory=lambda: [])
    skipped: list[str] = field(default_factory=lambda: [])
    error: str | None = None


def propagate_ssh_config_to_host(
    alias: str,
    dry_run: bool,
    config_blocks: dict[str, str],
    gateway: str | None = None,
) -> ConfigPropagateResult:
    result = ConfigPropagateResult(alias=alias)
    if gateway is not None:
        result.skipped = list(config_blocks.keys())
        return result

    managed_config = "\n\n".join(config_blocks.values()) + "\n"

    include_rc, _, include_err = ssh(
        alias,
        f"grep -qxF '{SSH_CONFIG_INCLUDE_LINE}' /root/.ssh/config 2>/dev/null",
        timeout=20,
    )
    if include_rc == SSH_TIMEOUT_EXIT_CODE:
        result.error = "timeout"
        return result
    if include_rc not in (0, 1):
        result.error = f"include-check failed rc={include_rc}: {include_err[:80]}"
        return result

    managed_rc, managed_out, managed_err = ssh(
        alias,
        f"cat {MANAGED_SSH_CONFIG_PATH} 2>/dev/null || true",
        timeout=20,
    )
    if managed_rc == SSH_TIMEOUT_EXIT_CODE:
        result.error = "timeout"
        return result
    if managed_rc != 0:
        result.error = f"managed-read failed rc={managed_rc}: {managed_err[:80]}"
        return result

    include_present = include_rc == 0
    managed_matches = managed_out == managed_config.rstrip("\n")
    if include_present and managed_matches:
        result.skipped = list(config_blocks.keys())
        return result

    check_cmd = (
        f"grep -qxF '{SSH_CONFIG_INCLUDE_LINE}' /root/.ssh/config 2>/dev/null"
        f" && test -f {MANAGED_SSH_CONFIG_PATH} && echo READY || echo MISSING"
    )
    rc, out, err = ssh(alias, check_cmd, timeout=20)
    if rc == SSH_TIMEOUT_EXIT_CODE:
        result.error = "timeout"
        return result
    if rc != 0 and "MISSING" not in out:
        result.error = f"check failed rc={rc}: {err[:80]}"
        return result

    if dry_run:
        result.added = list(config_blocks.keys())
        return result

    ensure_cmd = (
        "mkdir -p /root/.ssh/config.d && chmod 700 /root/.ssh /root/.ssh/config.d && "
        f"(grep -qxF '{SSH_CONFIG_INCLUDE_LINE}' /root/.ssh/config 2>/dev/null || "
        "{ tmp=$(mktemp); printf '%s\n' '"
        + SSH_CONFIG_INCLUDE_LINE
        + '\' > "$tmp"; cat /root/.ssh/config >> "$tmp" 2>/dev/null || true; '
        'mv "$tmp" /root/.ssh/config; chmod 600 /root/.ssh/config; })'
    )
    rc, _, err = ssh(alias, ensure_cmd, timeout=20)
    if rc != 0:
        result.error = f"include failed rc={rc}: {err[:80]}"
        return result

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(managed_config)
        local_path = handle.name

    try:
        upload = subprocess.run(
            ["scp", *_SSH_OPTS, local_path, f"{alias}:{MANAGED_SSH_CONFIG_PATH}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        os.unlink(local_path)

    if upload.returncode != 0:
        result.error = f"upload failed rc={upload.returncode}: {upload.stderr[:80]}"
        return result

    rc, _, err = ssh(alias, f"chmod 600 {MANAGED_SSH_CONFIG_PATH}", timeout=20)
    if rc != 0:
        result.error = f"chmod failed rc={rc}: {err[:80]}"
        return result

    result.added = list(config_blocks.keys())

    return result


def propagate_ssh_config_all(
    aliases: list[str],
    proxied: list[tuple[str, str, str]],
    dry_run: bool,
    workers: int,
    width: int,
) -> list[ConfigPropagateResult]:
    action = "Simulating SSH config propagation" if dry_run else "Propagating SSH config"
    print_phase_header(f"PHASE 0 - {action} (compute + storage aliases) to compute nodes")

    config_blocks = {**COMPUTE_SSH_CONFIG, **STORAGE_BOX_SSH_CONFIG}

    results: list[ConfigPropagateResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures: dict[Future[ConfigPropagateResult], str] = {}
        # Direct compute nodes
        for alias in aliases:
            futures[
                executor.submit(propagate_ssh_config_to_host, alias, dry_run, config_blocks, None)
            ] = alias
        # Proxied LXC containers — immediately reported as skipped (no SSH config push needed)
        for lxc_alias, _lxc_ip, gateway in proxied:
            futures[
                executor.submit(
                    propagate_ssh_config_to_host, lxc_alias, dry_run, config_blocks, gateway
                )
            ] = lxc_alias
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            if r.error:
                status = fail(f"ERROR: {r.error}")
            else:
                added_str = ok(f"added={r.added}") if r.added else ok("added=[]")
                status = f"{added_str}  skipped={r.skipped}"
            print(f"  [{r.alias:<{width}}]  {status}")

    return results


# ---------------------------------------------------------------------------
# Phase 1 — Collect
# ---------------------------------------------------------------------------


@dataclass
class CollectResult:
    alias: str
    keys: list[str] = field(default_factory=lambda: [])
    error: str | None = None


def collect_pubkeys(alias: str, gateway: str | None = None) -> CollectResult:
    collect_cmd = 'for f in /root/.ssh/*.pub; do [ -f "$f" ] && cat "$f"; done 2>/dev/null || true'
    if gateway:
        rc, out, err = ssh_via_gateway(gateway, alias, collect_cmd)
    else:
        rc, out, err = ssh(alias, collect_cmd)
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


def install_keys_on_host(
    alias: str, all_keys: list[str], dry_run: bool, gateway: str | None = None
) -> DistributeResult:
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
            "mkdir -p /root/.ssh && chmod 700 /root/.ssh"
            " && touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys && "
            f"if grep -qF '{key_body}' /root/.ssh/authorized_keys 2>/dev/null; then "
            "echo SKIP; "
            f"else echo '{key}' >> /root/.ssh/authorized_keys && echo ADD; fi"
        )
        if gateway:
            rc, out, err = ssh_via_gateway(gateway, alias, cmd)
        else:
            rc, out, err = ssh(alias, cmd)
        if rc == 0 and "ADD" in out:
            result.added += 1
        elif rc == 0 and "SKIP" in out:
            result.skipped += 1
        else:
            result.errors.append(f"  key {key[:30]}… rc={rc} {err[:60]}")

    return result


def install_keys_on_storagebox(alias: str, all_keys: list[str], dry_run: bool) -> DistributeResult:
    """Distribute keys to a Hetzner Storage Box via SCP.

    Storage Boxes have a restricted shell that does not support pipes or
    redirects, so the normal grep/echo idiom cannot be used.  Instead we:
      1. Download the current authorized_keys (if it exists) via SCP.
      2. Merge new keys (idempotent dedup by base64 body).
      3. Upload the merged file back via SCP.
    """
    result = DistributeResult(alias=alias)

    if dry_run:
        result.added = len(all_keys)
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        local_ak = os.path.join(tmpdir, "authorized_keys")

        # Step 1 — download existing authorized_keys (ignore error if absent)
        dl = subprocess.run(
            [
                "scp",
                "-P",
                "23",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "LogLevel=ERROR",
                f"{alias}:.ssh/authorized_keys",
                local_ak,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        existing_bodies: set[str] = set()
        existing_lines: list[str] = []
        if dl.returncode == 0 and os.path.exists(local_ak):
            with open(local_ak, encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    existing_lines.append(line)
                    parts = line.split()
                    if len(parts) >= SSH_KEY_MIN_PARTS:
                        existing_bodies.add(parts[1])

        # Step 2 — merge, deduplicate
        merged = list(existing_lines)
        for key in all_keys:
            parts = key.split()
            if len(parts) < SSH_KEY_MIN_PARTS:
                continue
            if parts[1] not in existing_bodies:
                merged.append(key)
                existing_bodies.add(parts[1])
                result.added += 1
            else:
                result.skipped += 1

        if result.added == 0:
            return result  # nothing new, skip upload

        with open(local_ak, "w", encoding="utf-8") as fh:
            fh.write("\n".join(merged) + "\n")

        # Step 3 — ensure .ssh dir exists, then upload
        subprocess.run(
            [
                "ssh",
                "-p",
                "23",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "LogLevel=ERROR",
                alias,
                "mkdir .ssh",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )  # ignore rc — dir may already exist

        ul = subprocess.run(
            [
                "scp",
                "-P",
                "23",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "LogLevel=ERROR",
                local_ak,
                f"{alias}:.ssh/authorized_keys",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if ul.returncode != 0:
            result.skipped += result.added
            result.errors.append(f"scp upload failed rc={ul.returncode}: {ul.stderr[:80]}")
            result.added = 0

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
        f"ssh -o BatchMode=yes -o NumberOfPasswordPrompts=0 -o ConnectTimeout={timeout}"
        f" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null"
        f" -o LogLevel=ERROR {dst_alias} 'echo __MESH_OK__' 2>&1"
    )
    last_detail = "unknown error"

    for attempt in range(VERIFY_RETRIES):
        rc, out, err = ssh(src_alias, cmd, timeout=timeout + 6)
        is_ok = rc == 0 and "__MESH_OK__" in out
        if is_ok:
            return VerifyResult(
                src=src_alias, dst_alias=dst_alias, dst_ip=dst_ip, ok=True, detail="ok"
            )

        last_detail = (out or err or "unknown error")[:160]
        is_transient = "Connection reset by peer" in last_detail or "Maxstartups" in last_detail
        if not is_transient or attempt == VERIFY_RETRIES - 1:
            break
        time.sleep(0.5 * (attempt + 1))

    return VerifyResult(
        src=src_alias,
        dst_alias=dst_alias,
        dst_ip=dst_ip,
        ok=False,
        detail=last_detail,
    )


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
    proxied: list[tuple[str, str, str]],
    workers: int,
    width: int,
) -> tuple[dict[str, CollectResult], list[str]]:
    print_phase_header("PHASE 1 - Collecting public keys from all nodes + LXCs")

    collect_results: dict[str, CollectResult] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures: dict[Future[CollectResult], str] = {}
        for alias in aliases:
            futures[executor.submit(collect_pubkeys, alias, None)] = alias
        for lxc_alias, lxc_ip, gateway in proxied:
            futures[executor.submit(collect_pubkeys, lxc_ip, gateway)] = lxc_alias

        for collect_future in as_completed(futures):
            collect_result = collect_future.result()
            collect_results[collect_result.alias] = collect_result
            status = (
                ok(f"{len(collect_result.keys)} key(s)")
                if not collect_result.error
                else fail(f"ERROR: {collect_result.error}")
            )
            print(f"  [{collect_result.alias:<{width}}]  {status}")

    all_collect_aliases = aliases + [a for a, _, _ in proxied]
    all_keys: list[str] = []
    seen_bodies: set[str] = set()
    for alias in all_collect_aliases:
        for key in collect_results.get(alias, CollectResult(alias=alias)).keys:
            parts = key.split()
            if len(parts) >= SSH_KEY_MIN_PARTS and parts[1] not in seen_bodies:
                seen_bodies.add(parts[1])
                all_keys.append(key)

    print(f"\n  Total unique keys collected: {BOLD}{len(all_keys)}{RESET}")
    return collect_results, all_keys


def distribute_all_keys(
    aliases: list[str],
    proxied: list[tuple[str, str, str]],
    all_keys: list[str],
    dry_run: bool,
    workers: int,
    width: int,
) -> list[DistributeResult]:
    action = "Simulating distribution" if dry_run else "Distributing keys"
    print_phase_header(f"PHASE 2 - {action} to all nodes + LXCs")

    dist_results: list[DistributeResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures_d: dict[Future[DistributeResult], str] = {}
        for alias in aliases:
            if alias in STORAGE_BOXES:
                futures_d[executor.submit(install_keys_on_storagebox, alias, all_keys, dry_run)] = (
                    alias
                )
            else:
                futures_d[executor.submit(install_keys_on_host, alias, all_keys, dry_run, None)] = (
                    alias
                )
        for lxc_alias, lxc_ip, gateway in proxied:
            futures_d[executor.submit(install_keys_on_host, lxc_ip, all_keys, dry_run, gateway)] = (
                lxc_alias
            )
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
    _workers: int,
    verify_timeout: int,
) -> list[VerifyResult]:
    pair_count = len(aliases) * (len(aliases) - 1)
    print_phase_header(f"PHASE 3 - Verifying pairwise connectivity ({pair_count} pairs)")

    verify_results: list[VerifyResult] = []
    for dst_alias in aliases:
        for src in aliases:
            if src == dst_alias:
                continue
            verify_results.append(verify_pair(src, dst_alias, ips[dst_alias], verify_timeout))

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

    aliases = [a for a, _ in CLUSTER] + STORAGE_BOXES
    ips = dict(CLUSTER)  # storage boxes have no IP (connect via SSH alias only)
    compute_aliases = [a for a, _ in CLUSTER]
    proxied = PROXIED_NODES
    all_aliases = aliases + [a for a, _, _ in proxied]
    width = max(len(a) for a in all_aliases)

    # Phase 0 — push storage-box SSH config entries to all compute nodes + LXCs
    propagate_ssh_config_all(compute_aliases, proxied, args.dry_run, args.workers, width)

    # Phase 1 — collect keys from compute nodes + LXCs (not storage boxes)
    _, all_keys = collect_all_keys(compute_aliases, proxied, args.workers, width)

    if not all_keys:
        print(fail("No keys collected. Cannot continue."))
        return 2

    if args.dry_run:
        dry_run_message = (
            f"\n  {YELLOW}[DRY-RUN]{RESET} Would distribute {len(all_keys)} keys "
            f"to {len(all_aliases)} nodes."
        )
        print(dry_run_message)

    # Phase 2 — distribute all keys to compute nodes, LXCs, and storage boxes
    dist_results = distribute_all_keys(
        aliases, proxied, all_keys, args.dry_run, args.workers, width
    )

    total_added = sum(r.added for r in dist_results)
    total_errors = sum(len(r.errors) for r in dist_results)
    error_label = fail(str(total_errors)) if total_errors else ok("0")
    print(f"\n  Total keys installed: {BOLD}{total_added}{RESET}  |  Errors: {error_label}")

    verify_results: list[VerifyResult] = []
    if args.verify:
        # Verify only compute nodes (storage boxes and LXCs don't do outbound SSH mesh)
        verify_results = verify_mesh(compute_aliases, ips, args.workers, args.verify_timeout)
        print_verify_report(compute_aliases, verify_results, width)

    retained_payload = build_result_envelope(
        RESULT_TYPE,
        {
            "mode": {
                "dry_run": args.dry_run,
                "verify": args.verify,
                "workers": args.workers,
                "verify_timeout": args.verify_timeout,
            },
            "cluster": [{"alias": alias, "ip": ips[alias]} for alias in compute_aliases]
            + [{"alias": alias, "ip": "storagebox"} for alias in STORAGE_BOXES]
            + [{"alias": a, "ip": ip, "gateway": gw} for a, ip, gw in proxied],
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
