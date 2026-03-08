"""Read-only cluster network audit — vSwitch / VLAN / IP discovery.

Usage:
  python subprojects/cluster-audit/audit_cluster.py
  python subprojects/cluster-audit/audit_cluster.py --workers 8
  python subprojects/cluster-audit/audit_cluster.py --node hz.113
"""

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_result_store import build_result_envelope, write_retained_result

INTERFACE_ADDR_INDEX = 2
SUBNET_OCTET_COUNT = 3
SUMMARY_OK = "ok"
SUMMARY_MISSING = "missing"
SUMMARY_ERROR = "error"
SUMMARY_VSWITCH = "vswitch"
SUMMARY_NO_VSWITCH = "no_vswitch"
SUMMARY_ERRORS = "errors"
RESULT_TYPE = "network_audit"


class NetworkAuditResult(TypedDict):
    alias: str
    pub_ip: str
    error: str | None
    hostname: str
    kernel: str
    os: str
    interfaces: list[str]
    vlans: list[str]
    vlan_ids: list[str]
    routes: list[str]
    netplan: dict[str, list[str]]
    private_ips: list[str]


SectionName = Literal["iface", "vlans", "vlan_ids", "routes", "netplan", "private"] | None
VSwitchNodeSummary = tuple[str, list[str], list[str]]

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

# Comandă read-only care colectează tot ce ne interesează despre rețea
_AUDIT_CMD = r"""
echo "HOSTNAME=$(hostname)"
echo "KERNEL=$(uname -r)"
echo "OS=$(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '\"')"
echo "--- INTERFACES ---"
ip -br addr 2>/dev/null
echo "--- VLANS ---"
ip -d link show 2>/dev/null | grep -A2 "vlan\|VLAN" | grep -v "^--$" || echo "(none)"
echo "--- VLAN IDS ---"
ip -d link 2>/dev/null | grep "vlan id" || echo "(no vlan ids found)"
echo "--- ROUTES ---"
ip route 2>/dev/null
echo "--- NETPLAN ---"
for f in /etc/netplan/*.yaml; do echo "FILE:$f"; cat "$f"; echo "ENDFILE"; done
echo "--- PRIVATE IPS ---"
ip addr 2>/dev/null | grep "inet " | grep -v "127.0.0.1" | awk '{print $2}' \
| grep -vE "^49\.|^95\.|^94\.|^135\.|^77\." || echo "(none)"
echo "--- END ---"
"""

# Culori ANSI
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"


def ssh(alias: str, cmd: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["ssh", *_SSH_OPTS, alias, cmd],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return result.returncode, result.stdout, result.stderr


def _empty_result(alias: str, pub_ip: str, error: str | None = None) -> NetworkAuditResult:
    return {
        "alias": alias,
        "pub_ip": pub_ip,
        "error": error,
        "hostname": "",
        "kernel": "",
        "os": "",
        "interfaces": [],
        "vlans": [],
        "vlan_ids": [],
        "routes": [],
        "netplan": {},
        "private_ips": [],
    }


def audit_node(alias: str, pub_ip: str) -> NetworkAuditResult:
    try:
        rc, out, err = ssh(alias, _AUDIT_CMD)
        if rc != 0:
            return _empty_result(alias, pub_ip, err.strip() or f"exit {rc}")
        return parse_output(alias, pub_ip, out)
    except Exception as e:
        return _empty_result(alias, pub_ip, str(e))


def _detect_section(line: str) -> SectionName:
    section_markers: dict[str, SectionName] = {
        "--- INTERFACES ---": "iface",
        "--- VLANS ---": "vlans",
        "--- VLAN IDS ---": "vlan_ids",
        "--- ROUTES ---": "routes",
        "--- NETPLAN ---": "netplan",
        "--- PRIVATE IPS ---": "private",
        "--- END ---": None,
    }
    return section_markers.get(line)


def _parse_metadata_line(result: NetworkAuditResult, line: str) -> bool:
    if line.startswith("HOSTNAME="):
        result["hostname"] = line.split("=", 1)[1]
        return True
    if line.startswith("KERNEL="):
        result["kernel"] = line.split("=", 1)[1]
        return True
    if line.startswith("OS="):
        result["os"] = line.split("=", 1)[1]
        return True
    return False


def _append_section_line(
    section: SectionName,
    line: str,
    result: NetworkAuditResult,
) -> None:
    stripped = line.strip()
    if not stripped:
        return
    if section == "iface":
        result["interfaces"].append(stripped)
    elif section == "vlans" and stripped != "(none)":
        result["vlans"].append(stripped)
    elif section == "vlan_ids" and "no vlan ids" not in line:
        result["vlan_ids"].append(stripped)
    elif section == "routes":
        result["routes"].append(stripped)
    elif section == "private" and stripped != "(none)":
        result["private_ips"].append(stripped)


def _update_netplan(
    line: str,
    netplan_file: str | None,
    netplan_content: dict[str, list[str]],
) -> str | None:
    if line.startswith("FILE:"):
        new_netplan_file = line[5:]
        netplan_content[new_netplan_file] = []
        return new_netplan_file
    if line == "ENDFILE":
        return None
    if netplan_file:
        netplan_content[netplan_file].append(line)
    return netplan_file


def parse_output(alias: str, pub_ip: str, raw: str) -> NetworkAuditResult:
    result = _empty_result(alias, pub_ip)
    section: SectionName = None
    netplan_file = None
    netplan_content: dict[str, list[str]] = {}

    for line in raw.splitlines():
        if _parse_metadata_line(result, line):
            continue

        next_section = _detect_section(line)
        if next_section is not None or line == "--- END ---":
            section = next_section
            continue

        if section == "netplan":
            netplan_file = _update_netplan(line, netplan_file, netplan_content)
            continue

        _append_section_line(
            section,
            line,
            result,
        )

    result["netplan"] = netplan_content

    return result


def print_node_report(r: NetworkAuditResult) -> None:
    alias = r["alias"]
    pub_ip = r["pub_ip"]

    if r.get("error"):
        print(f"\n{RED}{'═' * 60}{RESET}")
        print(f"{RED}{BOLD}  {alias}  ({pub_ip}){RESET}")
        print(f"{RED}  ERROR: {r['error']}{RESET}")
        return

    print(f"\n{CYAN}{'═' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {alias}  ({pub_ip}){RESET}")
    print(
        f"{DIM}  OS: {r.get('os', '?')}  |  Kernel: {r.get('kernel', '?')}"
        f"  |  Host: {r.get('hostname', '?')}{RESET}"
    )

    _print_interfaces(r)
    _print_private_ips(r)
    _print_vlan_ids(r)
    _print_netplan(r)
    _print_default_routes(r)


def _print_interfaces(r: NetworkAuditResult) -> None:
    print(f"\n  {BOLD}Interfețe:{RESET}")
    for iface in r.get("interfaces", []):
        parts = iface.split()
        name = parts[0] if parts else iface
        state = parts[1] if len(parts) > 1 else ""
        if len(parts) > INTERFACE_ADDR_INDEX:
            addrs = " ".join(parts[INTERFACE_ADDR_INDEX:])
        else:
            addrs = "(no IP)"
        state_col = GREEN if state == "UP" else (YELLOW if state == "UNKNOWN" else RED)
        print(f"    {state_col}{name:<30}{RESET}  {state:<8}  {addrs}")


def _print_private_ips(r: NetworkAuditResult) -> None:
    private = r.get("private_ips", [])
    if private:
        print(f"\n  {BOLD}{GREEN}IP-uri rețea privată (vSwitch candidat):{RESET}")
        for ip in private:
            print(f"    {GREEN}✓  {ip}{RESET}")
        return
    print(f"\n  {YELLOW}  ⚠  Niciun IP privat detectat — vSwitch neconfigurat{RESET}")


def _print_vlan_ids(r: NetworkAuditResult) -> None:
    vids = r.get("vlan_ids", [])
    if not vids:
        return
    print(f"\n  {BOLD}VLAN IDs active:{RESET}")
    for vlan_id in vids:
        print(f"    {CYAN}{vlan_id}{RESET}")


def _print_netplan(r: NetworkAuditResult) -> None:
    netplan = r.get("netplan", {})
    if not netplan:
        return
    print(f"\n  {BOLD}Netplan configs:{RESET}")
    for fname, lines in netplan.items():
        short = fname.split("/")[-1]
        content = "\n".join(lines)
        has_vlan = "vlan" in content.lower() or "id:" in content
        marker = f" {CYAN}← conține VLAN{RESET}" if has_vlan else ""
        print(f"    {DIM}{short}{RESET}{marker}")
        for line in lines:
            stripped = line.rstrip()
            if not stripped:
                continue
            highlight_terms = ("vlan", "id:", "addresses")
            color = CYAN if any(key in line.lower() for key in highlight_terms) else DIM
            print(f"      {color}{stripped}{RESET}")


def _print_default_routes(r: NetworkAuditResult) -> None:
    default_routes = [route for route in r.get("routes", []) if route.startswith("default")]
    if not default_routes:
        return
    print(f"\n  {BOLD}Rute default:{RESET}")
    for route in default_routes:
        print(f"    {DIM}{route}{RESET}")


def _classify_result(result: NetworkAuditResult) -> str:
    if result.get("error"):
        return SUMMARY_ERROR
    if result["private_ips"] or result["vlan_ids"]:
        return SUMMARY_OK
    return SUMMARY_MISSING


def _collect_private_subnets(results: list[NetworkAuditResult]) -> list[str]:
    subnets: set[str] = set()
    for result in results:
        for ip_cidr in result.get("private_ips", []):
            parts = ip_cidr.split(".")
            if len(parts) >= SUBNET_OCTET_COUNT:
                subnets.add(f"{parts[0]}.{parts[1]}.{parts[2]}.x")
    return sorted(subnets)


def _group_results(
    results: list[NetworkAuditResult],
) -> tuple[list[VSwitchNodeSummary], list[str], list[str]]:
    has_vswitch: list[VSwitchNodeSummary] = []
    no_vswitch: list[str] = []
    errors: list[str] = []

    for result in results:
        classification = _classify_result(result)
        if classification == SUMMARY_ERROR:
            errors.append(result["alias"])
        elif classification == SUMMARY_OK:
            has_vswitch.append((result["alias"], result["private_ips"], result["vlan_ids"]))
        else:
            no_vswitch.append(result["alias"])

    return has_vswitch, no_vswitch, errors


def _print_summary_group(title: str, color: str, values: list[str], marker: str) -> None:
    if not values:
        return
    print(f"\n  {color}{BOLD}{title}{RESET}")
    for value in values:
        print(f"    {color}{marker}  {value}{RESET}")


def _print_vswitch_group(has_vswitch: list[VSwitchNodeSummary]) -> None:
    if not has_vswitch:
        return
    print(f"\n  {GREEN}{BOLD}Noduri cu rețea privată / VLAN configurată:{RESET}")
    for alias, ips, vids in has_vswitch:
        ip_str = ", ".join(ips) if ips else "(IP nealocat)"
        vid_str = f"  VLAN: {', '.join(vids)}" if vids else ""
        print(f"    {GREEN}✓  {alias:<12}  {ip_str}{vid_str}{RESET}")


def print_summary(results: list[NetworkAuditResult]) -> None:
    print(f"\n\n{'═' * 60}")
    print(f"{BOLD}  SUMAR VSWITCH CLUSTER{RESET}")
    print(f"{'═' * 60}")

    has_vswitch, no_vswitch, errors = _group_results(results)
    _print_vswitch_group(has_vswitch)
    _print_summary_group("Noduri FĂRĂ vSwitch/IP privat:", YELLOW, no_vswitch, "⚠")
    _print_summary_group("Noduri inaccesibile:", RED, errors, "✗")

    # Detectăm VLAN ID comun și subnet comun
    all_vids: list[str] = []
    for r in results:
        all_vids.extend(r.get("vlan_ids", []))

    private_subnets = _collect_private_subnets(results)
    if private_subnets:
        print(f"\n  {BOLD}Subnete private detectate:{RESET} {', '.join(private_subnets)}")

    if all_vids:
        vids_uniq = sorted(set(all_vids))
        print(f"  {BOLD}VLAN IDs detectate:{RESET} {', '.join(vids_uniq)}")


def _build_summary(results: list[NetworkAuditResult]) -> dict[str, object]:
    has_vswitch, no_vswitch, errors = _group_results(results)
    return {
        SUMMARY_VSWITCH: [
            {"alias": alias, "private_ips": private_ips, "vlan_ids": vlan_ids}
            for alias, private_ips, vlan_ids in has_vswitch
        ],
        SUMMARY_NO_VSWITCH: no_vswitch,
        SUMMARY_ERRORS: errors,
        "private_subnets": _collect_private_subnets(results),
        "vlan_ids": sorted(
            {vlan_id for result in results for vlan_id in result.get("vlan_ids", [])}
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only network audit for Hetzner cluster.")
    parser.add_argument("--workers", type=int, default=8, help="Parallel SSH workers (default: 8)")
    parser.add_argument(
        "--node", type=str, default=None, help="Auditează doar un nod specific (alias)"
    )
    args = parser.parse_args()

    targets = [(a, ip) for a, ip in CLUSTER if args.node is None or a == args.node]
    if not targets:
        print(f"{RED}Nodul '{args.node}' nu a fost găsit în cluster.{RESET}")
        sys.exit(1)

    print(f"{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  CLUSTER NETWORK AUDIT — READ ONLY{RESET}")
    print(f"{BOLD}  {len(targets)} noduri  |  workers={args.workers}{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")

    results: list[NetworkAuditResult] = [_empty_result(alias, ip) for alias, ip in targets]
    alias_index = {a: i for i, (a, _) in enumerate(targets)}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(audit_node, a, ip): a for a, ip in targets}
        for fut in as_completed(futures):
            alias = futures[fut]
            r = fut.result()
            results[alias_index[alias]] = r
            status = f"{RED}ERR{RESET}" if r.get("error") else f"{GREEN}OK{RESET}"
            print(f"  [{status}] {alias}")

    for r in results:
        print_node_report(r)

    print_summary(results)

    payload = build_result_envelope(
        RESULT_TYPE,
        {
            "targets": [{"alias": alias, "pub_ip": ip} for alias, ip in targets],
            "results": results,
            "summary": _build_summary(results),
        },
    )
    saved_path = write_retained_result(__file__, RESULT_TYPE, payload)
    print(f"\n{GREEN}Rezultate salvate → {saved_path}{RESET}")


if __name__ == "__main__":
    main()
