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
from typing import Literal, TypedDict

INTERFACE_ADDR_INDEX = 2
SUBNET_OCTET_COUNT = 3


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


def parse_output(alias: str, pub_ip: str, raw: str) -> NetworkAuditResult:
    result = _empty_result(alias, pub_ip)
    section: SectionName = None
    netplan_file = None
    netplan_content: dict[str, list[str]] = {}
    interfaces: list[str] = []
    vlans: list[str] = []
    vlan_ids: list[str] = []
    routes: list[str] = []
    private_ips: list[str] = []

    for line in raw.splitlines():
        if line.startswith("HOSTNAME="):
            result["hostname"] = line.split("=", 1)[1]
        elif line.startswith("KERNEL="):
            result["kernel"] = line.split("=", 1)[1]
        elif line.startswith("OS="):
            result["os"] = line.split("=", 1)[1]
        elif line == "--- INTERFACES ---":
            section = "iface"
        elif line == "--- VLANS ---":
            section = "vlans"
        elif line == "--- VLAN IDS ---":
            section = "vlan_ids"
        elif line == "--- ROUTES ---":
            section = "routes"
        elif line == "--- NETPLAN ---":
            section = "netplan"
        elif line == "--- PRIVATE IPS ---":
            section = "private"
        elif line == "--- END ---":
            section = None
        elif section == "iface" and line.strip():
            interfaces.append(line.strip())
        elif section == "vlans" and line.strip() and line != "(none)":
            vlans.append(line.strip())
        elif section == "vlan_ids" and line.strip() and "no vlan ids" not in line:
            vlan_ids.append(line.strip())
        elif section == "routes" and line.strip():
            routes.append(line.strip())
        elif section == "netplan":
            if line.startswith("FILE:"):
                netplan_file = line[5:]
                netplan_content[netplan_file] = []
            elif line == "ENDFILE":
                netplan_file = None
            elif netplan_file:
                netplan_content[netplan_file].append(line)
        elif section == "private" and line.strip() and line != "(none)":
            private_ips.append(line.strip())

    result["interfaces"] = interfaces
    result["vlans"] = vlans
    result["vlan_ids"] = vlan_ids
    result["routes"] = routes
    result["netplan"] = netplan_content
    result["private_ips"] = private_ips
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

    # Interfețe
    print(f"\n  {BOLD}Interfețe:{RESET}")
    for iface in r.get("interfaces", []):
        parts = iface.split()
        name = parts[0] if parts else iface
        state = parts[1] if len(parts) > 1 else ""
        addrs = (
            " ".join(parts[INTERFACE_ADDR_INDEX:])
            if len(parts) > INTERFACE_ADDR_INDEX
            else "(no IP)"
        )
        state_col = GREEN if state == "UP" else (YELLOW if state == "UNKNOWN" else RED)
        print(f"    {state_col}{name:<30}{RESET}  {state:<8}  {addrs}")

    # IP-uri private (non-publice)
    private = r.get("private_ips", [])
    if private:
        print(f"\n  {BOLD}{GREEN}IP-uri rețea privată (vSwitch candidat):{RESET}")
        for ip in private:
            print(f"    {GREEN}✓  {ip}{RESET}")
    else:
        print(f"\n  {YELLOW}  ⚠  Niciun IP privat detectat — vSwitch neconfigurat{RESET}")

    # VLAN IDs
    vids = r.get("vlan_ids", [])
    if vids:
        print(f"\n  {BOLD}VLAN IDs active:{RESET}")
        for v in vids:
            print(f"    {CYAN}{v}{RESET}")

    # Netplan
    netplan = r.get("netplan", {})
    if netplan:
        print(f"\n  {BOLD}Netplan configs:{RESET}")
        for fname, lines in netplan.items():
            short = fname.split("/")[-1]
            content = "\n".join(lines)
            # Evidențiază liniile VLAN
            has_vlan = "vlan" in content.lower() or "id:" in content
            marker = f" {CYAN}← conține VLAN{RESET}" if has_vlan else ""
            print(f"    {DIM}{short}{RESET}{marker}")
            for ln in lines:
                stripped = ln.rstrip()
                if not stripped:
                    continue
                color = CYAN if any(k in ln.lower() for k in ("vlan", "id:", "addresses")) else DIM
                print(f"      {color}{stripped}{RESET}")

    # Rute default
    default_routes = [r2 for r2 in r.get("routes", []) if r2.startswith("default")]
    if default_routes:
        print(f"\n  {BOLD}Rute default:{RESET}")
        for rt in default_routes:
            print(f"    {DIM}{rt}{RESET}")


def print_summary(results: list[NetworkAuditResult]) -> None:
    print(f"\n\n{'═' * 60}")
    print(f"{BOLD}  SUMAR VSWITCH CLUSTER{RESET}")
    print(f"{'═' * 60}")

    has_vswitch: list[VSwitchNodeSummary] = []
    no_vswitch: list[str] = []
    errors: list[str] = []

    for r in results:
        if r.get("error"):
            errors.append(r["alias"])
        elif r["private_ips"] or r["vlan_ids"]:
            has_vswitch.append((r["alias"], r["private_ips"], r["vlan_ids"]))
        else:
            no_vswitch.append(r["alias"])

    if has_vswitch:
        print(f"\n  {GREEN}{BOLD}Noduri cu rețea privată / VLAN configurată:{RESET}")
        for alias, ips, vids in has_vswitch:
            ip_str = ", ".join(ips) if ips else "(IP nealocat)"
            vid_str = f"  VLAN: {', '.join(vids)}" if vids else ""
            print(f"    {GREEN}✓  {alias:<12}  {ip_str}{vid_str}{RESET}")

    if no_vswitch:
        print(f"\n  {YELLOW}{BOLD}Noduri FĂRĂ vSwitch/IP privat:{RESET}")
        for alias in no_vswitch:
            print(f"    {YELLOW}⚠  {alias}{RESET}")

    if errors:
        print(f"\n  {RED}{BOLD}Noduri inaccesibile:{RESET}")
        for alias in errors:
            print(f"    {RED}✗  {alias}{RESET}")

    # Detectăm VLAN ID comun și subnet comun
    all_private: list[str] = []
    for r in results:
        all_private.extend(r.get("private_ips", []))
    all_vids: list[str] = []
    for r in results:
        all_vids.extend(r.get("vlan_ids", []))

    if all_private:
        subnets: set[str] = set()
        for ip_cidr in all_private:
            parts = ip_cidr.split(".")
            if len(parts) >= SUBNET_OCTET_COUNT:
                subnets.add(f"{parts[0]}.{parts[1]}.{parts[2]}.x")
        print(f"\n  {BOLD}Subnete private detectate:{RESET} {', '.join(sorted(subnets))}")

    if all_vids:
        vids_uniq = sorted(set(all_vids))
        print(f"  {BOLD}VLAN IDs detectate:{RESET} {', '.join(vids_uniq)}")


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


if __name__ == "__main__":
    main()
