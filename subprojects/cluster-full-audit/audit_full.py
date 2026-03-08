#!/usr/bin/env python3
"""Full-spectrum read-only cluster audit.

Acoperă toate mașinile din cluster și colectează:
  • System   — OS, kernel, hostname, uptime, load, users logați
  • Hardware — CPU (model, cores, threads), RAM total/used/free, swap
  • GPU      — nvidia-smi: model, VRAM, utilizare, temperatură, putere (skip dacă absent)
  • Disk     — partiții mounted, spațiu liber, inode usage
  • Network  — interfețe, IP-uri (publice + private), VLAN IDs, rute, netplan
  • Docker   — versiune, containere running/stopped, imagini, volumes
  • Services — servicii systemd active/failed, porturi TCP/UDP ascultate
  • Firewall — UFW (status + reguli) sau iptables summary
  • Security — SSH config (PermitRoot, PasswordAuth), eșecuri autentificare, sudo users
  • Processes— top-5 CPU, top-5 RAM (snapshot)

Usage:
  python subprojects/cluster-full-audit/audit_full.py
  python subprojects/cluster-full-audit/audit_full.py --workers 6
  python subprojects/cluster-full-audit/audit_full.py --node hz.113
  python subprojects/cluster-full-audit/audit_full.py --section network
  python subprojects/cluster-full-audit/audit_full.py --json /tmp/cluster-audit.json
  python subprojects/cluster-full-audit/audit_full.py --json -        # stdout JSON
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import TypedDict, cast

SystemInfo = dict[str, str]
HardwareValue = str | float | bool
HardwareInfo = dict[str, HardwareValue]
SecurityInfo = dict[str, str]


class GpuInfo(TypedDict):
    gpu_name: str
    gpu_uuid: str
    gpu_driver: str
    gpu_mem_total: str
    gpu_mem_used: str
    gpu_mem_free: str
    gpu_util: str
    gpu_mem_util: str
    gpu_temp: str
    gpu_power_draw: str
    gpu_power_limit: str
    gpu_fan: str
    gpu_sm_clock: str
    gpu_gr_clock: str
    gpu_compute_cap: str


class PartitionInfo(TypedDict):
    fs: str
    size_kb: str
    used_kb: str
    avail_kb: str
    pct: str
    mountpoint: str


class BlockDeviceInfo(TypedDict):
    name: str
    size: str
    rotational: bool
    type: str
    model: str


class DiskInfo(TypedDict):
    partitions: list[PartitionInfo]
    block_devs: list[BlockDeviceInfo]


class InterfaceInfo(TypedDict):
    name: str
    state: str
    addrs: list[str]


class NetworkInfo(TypedDict):
    interfaces: list[InterfaceInfo]
    vlan_ids: list[str]
    routes: list[str]
    netplan: dict[str, str]
    dns: str
    private_ips: list[str]


class RunningContainerInfo(TypedDict):
    name: str
    image: str
    status: str
    ports: str


class StoppedContainerInfo(TypedDict):
    name: str
    image: str
    status: str


class ContainerStats(TypedDict):
    cpu: str
    mem: str
    mem_pct: str


class DockerDfInfo(TypedDict):
    type: str
    size: str
    reclaimable: str


class DockerInfo(TypedDict):
    present: bool
    version: str
    compose_version: str
    containers_running: list[RunningContainerInfo]
    containers_stats: dict[str, ContainerStats]
    containers_stopped: list[StoppedContainerInfo]
    images: int
    volumes: int
    networks: int
    df: list[DockerDfInfo]


class PortInfo(TypedDict):
    local: str
    proc: str


class FailedServiceInfo(TypedDict):
    unit: str
    sub: str


class ServicesInfo(TypedDict):
    ports_tcp: list[PortInfo]
    ports_udp: list[PortInfo]
    failed: list[FailedServiceInfo]
    key_services: dict[str, str]


class FirewallInfo(TypedDict):
    type: str
    status: str
    rules: list[str]
    input_rules: int
    custom_chains: int
    policy_input: str
    forward_rules: int


class ProcessInfo(TypedDict):
    user: str
    pid: str
    cpu: str
    mem: str
    cmd: str


class ProcessesInfo(TypedDict):
    top_cpu: list[ProcessInfo]
    top_mem: list[ProcessInfo]


class AuditReport(TypedDict):
    alias: str
    pub_ip: str
    error: str | None
    system: SystemInfo
    hardware: HardwareInfo
    gpu: list[GpuInfo]
    disk: DiskInfo
    network: NetworkInfo
    docker: DockerInfo
    services: ServicesInfo
    firewall: FirewallInfo
    security: SecurityInfo
    processes: ProcessesInfo


def _empty_gpu_info() -> GpuInfo:
    return {
        "gpu_name": "",
        "gpu_uuid": "",
        "gpu_driver": "",
        "gpu_mem_total": "0",
        "gpu_mem_used": "0",
        "gpu_mem_free": "0",
        "gpu_util": "0",
        "gpu_mem_util": "0",
        "gpu_temp": "0",
        "gpu_power_draw": "0",
        "gpu_power_limit": "0",
        "gpu_fan": "0",
        "gpu_sm_clock": "0",
        "gpu_gr_clock": "0",
        "gpu_compute_cap": "",
    }


def _empty_report(
    alias: str, pub_ip: str, error: str | None = None, *, docker_present: bool = True
) -> AuditReport:
    return {
        "alias": alias,
        "pub_ip": pub_ip,
        "error": error,
        "system": {
            "hostname": "",
            "kernel": "",
            "arch": "",
            "os": "",
            "uptime_sec": "0",
            "uptime_human": "",
            "load": "",
            "logged_users": "0",
            "date_utc": "",
        },
        "hardware": {
            "cpu_model": "",
            "cpu_physical": "0",
            "cpu_cores": "0",
            "ram_total_kb": "0",
            "ram_free_kb": "0",
            "ram_buffers_kb": "0",
            "ram_cached_kb": "0",
            "swap_total_kb": "0",
            "swap_free_kb": "0",
            "gpu_count": "0",
            "gpu_present": False,
            "ram_total_gb": 0.0,
            "ram_used_gb": 0.0,
            "ram_free_gb": 0.0,
            "ram_used_pct": 0.0,
            "swap_total_gb": 0.0,
            "swap_used_gb": 0.0,
        },
        "gpu": [],
        "disk": {"partitions": [], "block_devs": []},
        "network": {
            "interfaces": [],
            "vlan_ids": [],
            "routes": [],
            "netplan": {},
            "dns": "",
            "private_ips": [],
        },
        "docker": {
            "present": docker_present,
            "version": "",
            "compose_version": "",
            "containers_running": [],
            "containers_stats": {},
            "containers_stopped": [],
            "images": 0,
            "volumes": 0,
            "networks": 0,
            "df": [],
        },
        "services": {
            "ports_tcp": [],
            "ports_udp": [],
            "failed": [],
            "key_services": {},
        },
        "firewall": {
            "type": "unknown",
            "status": "unknown",
            "rules": [],
            "input_rules": 0,
            "custom_chains": 0,
            "policy_input": "unknown",
            "forward_rules": 0,
        },
        "security": {
            "sec_permit_root": "not-set",
            "sec_pass_auth": "not-set",
            "sec_pubkey_auth": "not-set",
            "sec_ssh_port": "22",
            "sec_fail2ban": "inactive",
            "sec_root_keys": "0",
            "sec_sudo_users": "",
            "sec_unattended": "0",
        },
        "processes": {"top_cpu": [], "top_mem": []},
    }


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value or 0))
    except (TypeError, ValueError):
        return 0


def _as_float(value: object) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _set_gpu_field(gpu: GpuInfo, key: str, value: str) -> None:
    if key == "GPU_NAME":
        gpu["gpu_name"] = value
    elif key == "GPU_UUID":
        gpu["gpu_uuid"] = value
    elif key == "GPU_DRIVER":
        gpu["gpu_driver"] = value
    elif key == "GPU_MEM_TOTAL":
        gpu["gpu_mem_total"] = value
    elif key == "GPU_MEM_USED":
        gpu["gpu_mem_used"] = value
    elif key == "GPU_MEM_FREE":
        gpu["gpu_mem_free"] = value
    elif key == "GPU_UTIL":
        gpu["gpu_util"] = value
    elif key == "GPU_MEM_UTIL":
        gpu["gpu_mem_util"] = value
    elif key == "GPU_TEMP":
        gpu["gpu_temp"] = value
    elif key == "GPU_POWER_DRAW":
        gpu["gpu_power_draw"] = value
    elif key == "GPU_POWER_LIMIT":
        gpu["gpu_power_limit"] = value
    elif key == "GPU_FAN":
        gpu["gpu_fan"] = value
    elif key == "GPU_SM_CLOCK":
        gpu["gpu_sm_clock"] = value
    elif key == "GPU_GR_CLOCK":
        gpu["gpu_gr_clock"] = value
    elif key == "GPU_COMPUTE_CAP":
        gpu["gpu_compute_cap"] = value


# ---------------------------------------------------------------------------
# Cluster definition
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

# Public IP prefixes — folosite să detectăm IP-urile private
_PUBLIC_PREFIXES = ("49.", "95.", "94.", "135.", "77.")

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
BLUE = "\033[34m"
MAG = "\033[35m"
DIM = "\033[2m"
RESET = "\033[0m"

# ---------------------------------------------------------------------------
# SSH helper
# ---------------------------------------------------------------------------
_SSH_OPTS = [
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "LogLevel=ERROR",
]


def _ssh(alias: str, cmd: str, timeout: int = 45) -> tuple[int, str, str]:
    r = subprocess.run(
        ["ssh", *_SSH_OPTS, alias, cmd],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr


# ---------------------------------------------------------------------------
# Remote audit command — un singur round-trip SSH per nod
# ---------------------------------------------------------------------------
_AUDIT_CMD = r"""
set -o pipefail 2>/dev/null; true

###  SYSTEM  ###
echo "=== SYSTEM ==="
echo "HOSTNAME=$(hostname -f 2>/dev/null || hostname)"
echo "KERNEL=$(uname -r)"
echo "ARCH=$(uname -m)"
echo "OS=$(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' || echo unknown)"
echo "UPTIME_SEC=$(cat /proc/uptime 2>/dev/null | awk '{print int($1)}')"
echo "UPTIME_HUMAN=$(uptime -p 2>/dev/null || uptime | sed 's/.*up //' | sed 's/,.*//')"
echo "LOAD=$(cat /proc/loadavg 2>/dev/null)"
echo "LOGGED_USERS=$(who 2>/dev/null | wc -l)"
echo "DATE_UTC=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

###  HARDWARE  ###
echo "=== HARDWARE ==="
echo "CPU_MODEL=$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo unknown)"
echo "CPU_PHYSICAL=$(grep 'physical id' /proc/cpuinfo 2>/dev/null | sort -u | wc -l)"
echo "CPU_CORES=$(grep -c '^processor' /proc/cpuinfo 2>/dev/null)"
echo "RAM_TOTAL_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')"
echo "RAM_FREE_KB=$(grep MemAvailable /proc/meminfo 2>/dev/null | awk '{print $2}')"
echo "RAM_BUFFERS_KB=$(grep ^Buffers /proc/meminfo 2>/dev/null | awk '{print $2}')"
echo "RAM_CACHED_KB=$(grep '^Cached:' /proc/meminfo 2>/dev/null | awk '{print $2}')"
echo "SWAP_TOTAL_KB=$(grep SwapTotal /proc/meminfo 2>/dev/null | awk '{print $2}')"
echo "SWAP_FREE_KB=$(grep SwapFree /proc/meminfo 2>/dev/null | awk '{print $2}')"

###  GPU  ###
echo "=== GPU ==="
if command -v nvidia-smi &>/dev/null; then
    nvidia-smi --query-gpu=name,uuid,driver_version,memory.total,memory.used,memory.free,utilization.gpu,utilization.memory,temperature.gpu,power.draw,power.limit,fan.speed,clocks.sm,clocks.gr,compute_cap \
        --format=csv,noheader,nounits 2>/dev/null \
    | while IFS=',' read -r name uuid drv mem_tot mem_used mem_free util_gpu util_mem temp pwr_draw pwr_lim fan sm_clk gr_clk cc; do
        echo "GPU_NAME=$(echo $name | xargs)"
        echo "GPU_UUID=$(echo $uuid | xargs)"
        echo "GPU_DRIVER=$(echo $drv | xargs)"
        echo "GPU_MEM_TOTAL=$(echo $mem_tot | xargs)"
        echo "GPU_MEM_USED=$(echo $mem_used | xargs)"
        echo "GPU_MEM_FREE=$(echo $mem_free | xargs)"
        echo "GPU_UTIL=$(echo $util_gpu | xargs)"
        echo "GPU_MEM_UTIL=$(echo $util_mem | xargs)"
        echo "GPU_TEMP=$(echo $temp | xargs)"
        echo "GPU_POWER_DRAW=$(echo $pwr_draw | xargs)"
        echo "GPU_POWER_LIMIT=$(echo $pwr_lim | xargs)"
        echo "GPU_FAN=$(echo $fan | xargs)"
        echo "GPU_SM_CLOCK=$(echo $sm_clk | xargs)"
        echo "GPU_GR_CLOCK=$(echo $gr_clk | xargs)"
        echo "GPU_COMPUTE_CAP=$(echo $cc | xargs)"
        echo "GPU_ENTRY_END"
    done
    echo "GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l)"
else
    echo "GPU_COUNT=0"
    echo "GPU_PRESENT=false"
fi

###  DISK  ###
echo "=== DISK ==="
df -P -x tmpfs -x devtmpfs -x squashfs 2>/dev/null | tail -n +2 | while read fs size used avail pct mp; do
    echo "DF|$fs|$size|$used|$avail|$pct|$mp"
done
# Disk I/O scheduler & block devices
lsblk -d -o NAME,SIZE,ROTA,TYPE,MODEL 2>/dev/null | tail -n +2 | while read name size rota type model; do
    echo "BLK|$name|$size|$rota|$type|$model"
done

###  NETWORK  ###
echo "=== NETWORK ==="
ip -br addr 2>/dev/null | while read iface state addrs; do
    echo "IFACE|$iface|$state|$addrs"
done
echo "--- NET_VLANS ---"
ip -d link show 2>/dev/null | grep "vlan id" | while read line; do echo "VLANID|$line"; done
echo "--- NET_ROUTES ---"
ip route 2>/dev/null | while read line; do echo "ROUTE|$line"; done
echo "--- NET_NETPLAN ---"
for f in /etc/netplan/*.yaml; do
    [ -f "$f" ] || continue
    echo "NETPLAN_FILE:$f"
    cat "$f" 2>/dev/null
    echo "NETPLAN_END"
done
echo "--- DNS ---"
echo "DNS_RESOLV=$(grep '^nameserver' /etc/resolv.conf 2>/dev/null | awk '{print $2}' | tr '\n' ',' | sed 's/,$//')"

###  DOCKER  ###
echo "=== DOCKER ==="
if command -v docker &>/dev/null; then
    echo "DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo error)"
    echo "DOCKER_COMPOSE=$(docker compose version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo N/A)"
    # Running containers: ID|Name|Image|Status|Ports|CPUPerc|MemUsage|MemPerc|RestartCount
    docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}' 2>/dev/null \
        | while IFS='|' read name img status ports; do
        echo "CONTAINER_RUN|$name|$img|$status|$ports"
    done
    # Stats (non-blocking snapshot)
    docker stats --no-stream --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}' 2>/dev/null \
        | while IFS='|' read name cpu mem memp; do
        echo "CONTAINER_STAT|$name|$cpu|$mem|$memp"
    done
    # Stopped containers
    docker ps -a --filter status=exited --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null \
        | while IFS='|' read name img status; do
        echo "CONTAINER_STOP|$name|$img|$status"
    done
    echo "DOCKER_IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | wc -l)"
    echo "DOCKER_VOLUMES=$(docker volume ls -q 2>/dev/null | wc -l)"
    echo "DOCKER_NETWORKS=$(docker network ls -q 2>/dev/null | wc -l)"
    # Disk usage by docker
    docker system df --format '{{.Type}}|{{.Size}}|{{.Reclaimable}}' 2>/dev/null \
        | while IFS='|' read type size reclaim; do
        echo "DOCKER_DF|$type|$size|$reclaim"
    done
else
    echo "DOCKER_PRESENT=false"
fi

###  SERVICES  ###
echo "=== SERVICES ==="
# Porturi ascultate
ss -tlnp 2>/dev/null | tail -n +2 | while read state recvq sendq local remote proc; do
    echo "PORT_TCP|$local|$proc"
done
ss -ulnp 2>/dev/null | tail -n +2 | while read state recvq sendq local remote proc; do
    echo "PORT_UDP|$local|$proc"
done
# Servicii systemd failed
systemctl list-units --state=failed --no-legend --no-pager 2>/dev/null | while read unit load active sub desc; do
    echo "SVC_FAILED|$unit|$sub"
done
# Servicii running cheie
for svc in docker ssh nginx haproxy postgresql mysql redis grafana prometheus loki; do
    st=$(systemctl is-active "$svc" 2>/dev/null || echo inactive)
    echo "SVC_KEY|$svc|$st"
done

###  FIREWALL  ###
echo "=== FIREWALL ==="
if command -v ufw &>/dev/null; then
    echo "FW_TYPE=ufw"
    echo "FW_STATUS=$(ufw status 2>/dev/null | head -1 | awk '{print $2}')"
    ufw status numbered 2>/dev/null | grep '^\[' | while read line; do
        echo "FW_RULE|$line"
    done
elif command -v iptables &>/dev/null; then
    echo "FW_TYPE=iptables"
    echo "FW_POLICY_INPUT=$(iptables -L INPUT --line-numbers -n 2>/dev/null | head -1 | grep -oE 'policy [A-Z]+' | cut -d' ' -f2 || echo unknown)"
    echo "FW_INPUT_RULES=$(iptables -L INPUT -n 2>/dev/null | tail -n +3 | wc -l)"
    echo "FW_FORWARD_RULES=$(iptables -L FORWARD -n 2>/dev/null | tail -n +3 | wc -l)"
    echo "FW_CUSTOM_CHAINS=$(iptables -L -n 2>/dev/null | grep '^Chain ' | grep -vE 'INPUT|OUTPUT|FORWARD' | wc -l)"
else
    echo "FW_TYPE=none"
fi

###  SECURITY  ###
echo "=== SECURITY ==="
echo "SEC_PERMIT_ROOT=$(grep -E '^PermitRootLogin' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo not-set)"
echo "SEC_PASS_AUTH=$(grep -E '^PasswordAuthentication' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo not-set)"
echo "SEC_PUBKEY_AUTH=$(grep -E '^PubkeyAuthentication' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo not-set)"
echo "SEC_SSH_PORT=$(grep -E '^Port ' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo 22)"
echo "SEC_FAIL2BAN=$(systemctl is-active fail2ban 2>/dev/null || echo inactive)"
echo "SEC_ROOT_KEYS=$(cat /root/.ssh/authorized_keys 2>/dev/null | grep -c 'ssh-' || echo 0)"
echo "SEC_SUDO_USERS=$(getent group sudo 2>/dev/null | cut -d: -f4 || getent group wheel 2>/dev/null | cut -d: -f4 || echo unknown)"
# Last 5 failed SSH logins
echo "--- SEC_FAILED_LOGINS ---"
journalctl -u ssh -u sshd --since '24h ago' --no-pager -q 2>/dev/null \
    | grep -i 'failed\|invalid\|error' | tail -5 \
    | while read line; do echo "SEC_FAILLOG|$line"; done
echo "--- SEC_FAIL_END ---"
# Unattended upgrades
echo "SEC_UNATTENDED=$(dpkg -l unattended-upgrades 2>/dev/null | grep '^ii' | wc -l)"

###  PROCESSES  ###
echo "=== PROCESSES ==="
# Top 5 CPU
ps aux --sort=-%cpu 2>/dev/null | awk 'NR>1 && NR<=6 {print "PROC_CPU|"$1"|"$2"|"$3"|"$4"|"$11}'
# Top 5 MEM
ps aux --sort=-%mem 2>/dev/null | awk 'NR>1 && NR<=6 {print "PROC_MEM|"$1"|"$2"|"$3"|"$4"|"$11}'

echo "=== END ==="
"""


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _kb_to_gb(kb: str) -> float:
    try:
        return round(int(kb) / 1024 / 1024, 2)
    except (ValueError, TypeError):
        return 0.0


def parse_output(alias: str, pub_ip: str, raw: str) -> AuditReport:
    r = _empty_report(alias, pub_ip)

    section = ""
    gpu_current: GpuInfo | None = None
    netplan_file: str | None = None
    netplan_buf: list[str] = []

    for raw_line in raw.splitlines():
        line = raw_line.rstrip()

        # --- section headers ---
        if line in (
            "=== SYSTEM ===",
            "=== HARDWARE ===",
            "=== GPU ===",
            "=== DISK ===",
            "=== NETWORK ===",
            "=== DOCKER ===",
            "=== SERVICES ===",
            "=== FIREWALL ===",
            "=== SECURITY ===",
            "=== PROCESSES ===",
            "=== END ===",
        ):
            section = line.strip("= ").lower()
            continue

        # --- netplan multi-line ---
        if line.startswith("NETPLAN_FILE:"):
            netplan_file = line[13:]
            netplan_buf = []
            continue
        if line == "NETPLAN_END":
            if netplan_file:
                r["network"]["netplan"][netplan_file] = "\n".join(netplan_buf)
            netplan_file = None
            netplan_buf = []
            continue
        if netplan_file is not None:
            netplan_buf.append(line)
            continue

        # --- skip sub-section markers ---
        if line.startswith("--- ") and line.endswith(" ---"):
            continue

        # ===== SYSTEM =====
        if section == "system":
            for key in (
                "HOSTNAME",
                "KERNEL",
                "ARCH",
                "OS",
                "UPTIME_SEC",
                "UPTIME_HUMAN",
                "LOAD",
                "LOGGED_USERS",
                "DATE_UTC",
            ):
                if line.startswith(f"{key}="):
                    r["system"][key.lower()] = line.split("=", 1)[1]

        # ===== HARDWARE =====
        elif section == "hardware":
            for key in (
                "CPU_MODEL",
                "CPU_PHYSICAL",
                "CPU_CORES",
                "RAM_TOTAL_KB",
                "RAM_FREE_KB",
                "RAM_BUFFERS_KB",
                "RAM_CACHED_KB",
                "SWAP_TOTAL_KB",
                "SWAP_FREE_KB",
            ):
                if line.startswith(f"{key}="):
                    r["hardware"][key.lower()] = line.split("=", 1)[1]

        # ===== GPU =====
        elif section == "gpu":
            if line.startswith("GPU_COUNT="):
                r["hardware"]["gpu_count"] = line.split("=", 1)[1]
            elif line == "GPU_ENTRY_END":
                if gpu_current is not None:
                    r["gpu"].append(gpu_current)
                gpu_current = None
            elif line.startswith("GPU_PRESENT="):
                r["hardware"]["gpu_present"] = False
            else:
                for key in (
                    "GPU_NAME",
                    "GPU_UUID",
                    "GPU_DRIVER",
                    "GPU_MEM_TOTAL",
                    "GPU_MEM_USED",
                    "GPU_MEM_FREE",
                    "GPU_UTIL",
                    "GPU_MEM_UTIL",
                    "GPU_TEMP",
                    "GPU_POWER_DRAW",
                    "GPU_POWER_LIMIT",
                    "GPU_FAN",
                    "GPU_SM_CLOCK",
                    "GPU_GR_CLOCK",
                    "GPU_COMPUTE_CAP",
                ):
                    if line.startswith(f"{key}="):
                        if gpu_current is None:
                            gpu_current = _empty_gpu_info()
                        _set_gpu_field(gpu_current, key, line.split("=", 1)[1])

        # ===== DISK =====
        elif section == "disk":
            if line.startswith("DF|"):
                parts = line.split("|")
                if len(parts) >= 7:
                    r["disk"]["partitions"].append(
                        {
                            "fs": parts[1],
                            "size_kb": parts[2],
                            "used_kb": parts[3],
                            "avail_kb": parts[4],
                            "pct": parts[5],
                            "mountpoint": parts[6],
                        }
                    )
            elif line.startswith("BLK|"):
                parts = line.split("|", 5)
                if len(parts) >= 5:
                    r["disk"]["block_devs"].append(
                        {
                            "name": parts[1],
                            "size": parts[2],
                            "rotational": parts[3] == "1",
                            "type": parts[4],
                            "model": parts[5] if len(parts) > 5 else "",
                        }
                    )

        # ===== NETWORK =====
        elif section == "network":
            if line.startswith("IFACE|"):
                parts = line.split("|", 3)
                if len(parts) >= 3:
                    r["network"]["interfaces"].append(
                        {
                            "name": parts[1],
                            "state": parts[2],
                            "addrs": parts[3].split() if len(parts) > 3 else [],
                        }
                    )
            elif line.startswith("VLANID|"):
                r["network"]["vlan_ids"].append(line[7:].strip())
            elif line.startswith("ROUTE|"):
                r["network"]["routes"].append(line[6:].strip())
            elif line.startswith("DNS_RESOLV="):
                r["network"]["dns"] = line.split("=", 1)[1]

        # ===== DOCKER =====
        elif section == "docker":
            if line.startswith("DOCKER_PRESENT="):
                r["docker"]["present"] = False
            elif line.startswith("DOCKER_VERSION="):
                r["docker"]["version"] = line.split("=", 1)[1]
            elif line.startswith("DOCKER_COMPOSE="):
                r["docker"]["compose_version"] = line.split("=", 1)[1]
            elif line.startswith("DOCKER_IMAGES="):
                r["docker"]["images"] = int(line.split("=", 1)[1] or 0)
            elif line.startswith("DOCKER_VOLUMES="):
                r["docker"]["volumes"] = int(line.split("=", 1)[1] or 0)
            elif line.startswith("DOCKER_NETWORKS="):
                r["docker"]["networks"] = int(line.split("=", 1)[1] or 0)
            elif line.startswith("CONTAINER_RUN|"):
                parts = line.split("|", 4)
                if len(parts) >= 4:
                    r["docker"]["containers_running"].append(
                        {
                            "name": parts[1],
                            "image": parts[2],
                            "status": parts[3],
                            "ports": parts[4] if len(parts) > 4 else "",
                        }
                    )
            elif line.startswith("CONTAINER_STAT|"):
                parts = line.split("|", 4)
                if len(parts) >= 4:
                    r["docker"]["containers_stats"][parts[1]] = {
                        "cpu": parts[2],
                        "mem": parts[3],
                        "mem_pct": parts[4] if len(parts) > 4 else "",
                    }
            elif line.startswith("CONTAINER_STOP|"):
                parts = line.split("|", 3)
                if len(parts) >= 3:
                    r["docker"]["containers_stopped"].append(
                        {
                            "name": parts[1],
                            "image": parts[2],
                            "status": parts[3] if len(parts) > 3 else "",
                        }
                    )
            elif line.startswith("DOCKER_DF|"):
                parts = line.split("|", 3)
                if len(parts) >= 3:
                    r["docker"]["df"].append(
                        {
                            "type": parts[1],
                            "size": parts[2],
                            "reclaimable": parts[3] if len(parts) > 3 else "",
                        }
                    )

        # ===== SERVICES =====
        elif section == "services":
            if line.startswith("PORT_TCP|"):
                parts = line.split("|", 2)
                r["services"]["ports_tcp"].append(
                    {"local": parts[1], "proc": parts[2] if len(parts) > 2 else ""}
                )
            elif line.startswith("PORT_UDP|"):
                parts = line.split("|", 2)
                r["services"]["ports_udp"].append(
                    {"local": parts[1], "proc": parts[2] if len(parts) > 2 else ""}
                )
            elif line.startswith("SVC_FAILED|"):
                parts = line.split("|", 2)
                r["services"]["failed"].append(
                    {"unit": parts[1], "sub": parts[2] if len(parts) > 2 else ""}
                )
            elif line.startswith("SVC_KEY|"):
                parts = line.split("|", 2)
                if len(parts) >= 3:
                    r["services"]["key_services"][parts[1]] = parts[2]

        # ===== FIREWALL =====
        elif section == "firewall":
            if line.startswith("FW_TYPE="):
                r["firewall"]["type"] = line.split("=", 1)[1]
            elif line.startswith("FW_STATUS="):
                r["firewall"]["status"] = line.split("=", 1)[1]
            elif line.startswith("FW_RULE|"):
                r["firewall"]["rules"].append(line[8:].strip())
            elif line.startswith("FW_POLICY_INPUT="):
                r["firewall"]["policy_input"] = line.split("=", 1)[1]
            elif line.startswith("FW_INPUT_RULES="):
                r["firewall"]["input_rules"] = int(line.split("=", 1)[1] or 0)
            elif line.startswith("FW_CUSTOM_CHAINS="):
                r["firewall"]["custom_chains"] = int(line.split("=", 1)[1] or 0)
            elif line.startswith("FW_FORWARD_RULES="):
                r["firewall"]["forward_rules"] = int(line.split("=", 1)[1] or 0)

        # ===== SECURITY =====
        elif section == "security":
            for key in (
                "SEC_PERMIT_ROOT",
                "SEC_PASS_AUTH",
                "SEC_PUBKEY_AUTH",
                "SEC_SSH_PORT",
                "SEC_FAIL2BAN",
                "SEC_ROOT_KEYS",
                "SEC_SUDO_USERS",
                "SEC_UNATTENDED",
            ):
                if line.startswith(f"{key}="):
                    r["security"][key.lower()] = line.split("=", 1)[1]

        # ===== PROCESSES =====
        elif section == "processes":
            if line.startswith("PROC_CPU|"):
                parts = line.split("|", 5)
                if len(parts) >= 6:
                    r["processes"]["top_cpu"].append(
                        {
                            "user": parts[1],
                            "pid": parts[2],
                            "cpu": parts[3],
                            "mem": parts[4],
                            "cmd": parts[5],
                        }
                    )
            elif line.startswith("PROC_MEM|"):
                parts = line.split("|", 5)
                if len(parts) >= 6:
                    r["processes"]["top_mem"].append(
                        {
                            "user": parts[1],
                            "pid": parts[2],
                            "cpu": parts[3],
                            "mem": parts[4],
                            "cmd": parts[5],
                        }
                    )

    # Compute derived fields
    hw = r["hardware"]
    ram_total = _as_int(hw.get("ram_total_kb", 0))
    ram_free = _as_int(hw.get("ram_free_kb", 0))
    hw["ram_total_gb"] = _kb_to_gb(str(ram_total))
    hw["ram_used_gb"] = _kb_to_gb(str(ram_total - ram_free))
    hw["ram_free_gb"] = _kb_to_gb(str(ram_free))
    hw["ram_used_pct"] = round((ram_total - ram_free) / ram_total * 100, 1) if ram_total else 0

    swap_total = _as_int(hw.get("swap_total_kb", 0))
    swap_free = _as_int(hw.get("swap_free_kb", 0))
    hw["swap_total_gb"] = _kb_to_gb(str(swap_total))
    hw["swap_used_gb"] = _kb_to_gb(str(swap_total - swap_free))

    # Private IPs — only IPv4, non-public, non-loopback, non-docker-bridge
    private_ips: list[str] = []
    for iface in r["network"]["interfaces"]:
        name = iface["name"]
        if name.startswith(("docker", "br-", "veth", "lo")):
            continue
        for addr in iface["addrs"]:
            ip = addr.split("/")[0]
            # Skip IPv6, loopback, and public Hetzner prefixes
            if ":" in ip:
                continue
            if ip in ("", "127.0.0.1"):
                continue
            if any(ip.startswith(p) for p in _PUBLIC_PREFIXES):
                continue
            private_ips.append(addr)
    r["network"]["private_ips"] = private_ips

    return r


def audit_node(alias: str, pub_ip: str) -> AuditReport:
    try:
        rc, out, err = _ssh(alias, _AUDIT_CMD)
        if rc != 0:
            return _empty_report(alias, pub_ip, err.strip() or f"exit {rc}", docker_present=False)
        return parse_output(alias, pub_ip, out)
    except Exception as exc:
        return _empty_report(alias, pub_ip, str(exc), docker_present=False)


# ---------------------------------------------------------------------------
# Pretty-printing helpers
# ---------------------------------------------------------------------------
def _bar(pct: float, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    color = GREEN if pct < 60 else (YELLOW if pct < 80 else RED)
    return f"{color}{'█' * filled}{'░' * (width - filled)}{RESET} {pct:5.1f}%"


W = 72  # report width


def _hdr(title: str, color: str = CYAN) -> str:
    return f"\n{color}{'─' * W}{RESET}\n{color}{BOLD}  {title}{RESET}"


def _sep() -> str:
    return f"{DIM}{'─' * W}{RESET}"


# ---------------------------------------------------------------------------
# Per-node report
# ---------------------------------------------------------------------------
def print_node_report(r: AuditReport, sections: list[str] | None = None) -> None:
    alias = r["alias"]
    pub_ip = r["pub_ip"]
    all_sec = sections is None
    selected_sections = sections or []

    print(f"\n{CYAN}{'═' * W}{RESET}")
    if r.get("error"):
        print(f"{RED}{BOLD}  ✗  {alias}  ({pub_ip}){RESET}")
        print(f"{RED}     ERROR: {r['error']}{RESET}")
        return

    sys_ = r["system"]
    hw = r["hardware"]
    print(f"{BOLD}{CYAN}  {alias}  ({pub_ip}){RESET}")
    print(
        f"{DIM}  {sys_.get('os', '?')}  │  Kernel {sys_.get('kernel', '?')}  │  "
        f"{sys_.get('arch', '?')}  │  Up {sys_.get('uptime_human', '?')}  │  "
        f"Load {sys_.get('load', '?')}{RESET}"
    )

    # ── HARDWARE ─────────────────────────────────────────────────────────
    if all_sec or "hardware" in selected_sections:
        print(_hdr("HARDWARE"))
        ram_used = _as_float(hw.get("ram_used_pct", 0.0))
        swap_tot = _as_float(hw.get("swap_total_gb", 0.0))
        swap_used = _as_float(hw.get("swap_used_gb", 0.0))
        print(
            f"  CPU  {BOLD}{hw.get('cpu_model', '?')}{RESET}  "
            f"[{hw.get('cpu_cores', '?')} cores · {hw.get('cpu_physical', '?')} socket(s)]"
        )
        print(
            f"  RAM  {_bar(ram_used)}  "
            f"{_as_float(hw.get('ram_used_gb', 0.0)):.2f} / {_as_float(hw.get('ram_total_gb', 0.0)):.2f} GB"
        )
        if swap_tot:
            swap_pct = round(swap_used / swap_tot * 100, 1) if swap_tot else 0
            print(f"  SWAP {_bar(swap_pct)}  {swap_used:.2f} / {swap_tot:.2f} GB")
        else:
            print(f"  SWAP {YELLOW}none{RESET}")

        blk = r["disk"]["block_devs"]
        if blk:
            print("\n  Block Devices:")
            for bd in blk:
                rot = "HDD" if bd["rotational"] else "SSD/NVMe"
                print(
                    f"    {DIM}{bd['name']:<12}{RESET}  {bd['size']:<8}  {rot:<10}  {bd['model'].strip()}"
                )

    # ── GPU ──────────────────────────────────────────────────────────────
    if all_sec or "gpu" in selected_sections:
        gpus = r["gpu"]
        if gpus:
            print(_hdr("GPU", MAG))
            for i, g in enumerate(gpus):
                mem_tot = _as_int(g["gpu_mem_total"])
                mem_used = _as_int(g["gpu_mem_used"])
                mem_pct = round(mem_used / mem_tot * 100, 1) if mem_tot else 0
                util_gpu = _as_float(g["gpu_util"])
                try:
                    temp = _as_float(g["gpu_temp"])
                    temp_color = GREEN if temp < 70 else (YELLOW if temp < 82 else RED)
                    temp_str = f"{temp_color}{temp:.0f}°C{RESET}"
                except (ValueError, TypeError):
                    temp_str = g["gpu_temp"]
                print(f"\n  GPU[{i}]  {BOLD}{MAG}{g['gpu_name']}{RESET}")
                print(
                    f"  Driver {g['gpu_driver']}  │  Compute {g['gpu_compute_cap']}  │  Temp {temp_str}"
                )
                print(f"  UTIL   {_bar(util_gpu)}")
                print(f"  VRAM   {_bar(mem_pct)}  {mem_used} / {mem_tot} MiB")
                pwr_draw = g["gpu_power_draw"]
                pwr_limit = g["gpu_power_limit"]
                fan = g["gpu_fan"] or "N/A"
                print(
                    f"  Power  {pwr_draw} W  /  {pwr_limit} W limit  │  Fan {fan}%  │  "
                    f"Clocks GR:{g['gpu_gr_clock']} SM:{g['gpu_sm_clock']} MHz"
                )
        elif hw.get("gpu_count", "0") == "0":
            print(f"\n  {DIM}[ No GPU ]{RESET}")

    # ── DISK ─────────────────────────────────────────────────────────────
    if all_sec or "disk" in selected_sections:
        _SKIP_FS = (
            "overlay",
            "efivarfs",
            "tmpfs",
            "devtmpfs",
            "squashfs",
            "cgroup",
            "nsfs",
            "proc",
            "sysfs",
            "debugfs",
            "hugetlbfs",
            "mqueue",
            "tracefs",
            "pstore",
            "bpf",
        )
        parts = [
            p
            for p in r["disk"]["partitions"]
            if p["fs"] not in _SKIP_FS
            and not p["mountpoint"].startswith(
                ("/sys", "/proc", "/dev", "/var/lib/docker/rootfs", "/run/", "/snap/")
            )
        ]
        if parts:
            print(_hdr("DISK"))
            for p in parts:
                pct_str = p["pct"].rstrip("%")
                try:
                    pct_val = float(pct_str)
                except ValueError:
                    pct_val = 0
                size_kb = _as_int(p["size_kb"])
                used_kb = _as_int(p["used_kb"])
                size_gb = round(size_kb / 1024 / 1024, 1)
                used_gb = round(used_kb / 1024 / 1024, 1)
                print(
                    f"  {_bar(pct_val)}  {p['mountpoint']:<20}  {used_gb:.1f}/{size_gb:.1f} GB  {DIM}{p['fs']}{RESET}"
                )

    # ── NETWORK ──────────────────────────────────────────────────────────
    if all_sec or "network" in selected_sections:
        print(_hdr("NETWORK"))
        for iface in r["network"]["interfaces"]:
            st = iface["state"]
            sc = GREEN if st == "UP" else (YELLOW if st == "UNKNOWN" else RED)
            addrs = "  ".join(iface["addrs"]) or "(no IP)"
            print(f"  {sc}{iface['name']:<22}{RESET}  {sc}{st:<10}{RESET}  {addrs}")

        priv = r["network"]["private_ips"]
        if priv:
            print(f"\n  {GREEN}{BOLD}Private IPs (vSwitch):{RESET}  {', '.join(priv)}")
        else:
            print(f"\n  {YELLOW}⚠  No private IPs — vSwitch not configured{RESET}")

        vids = r["network"]["vlan_ids"]
        if vids:
            print(f"  {CYAN}VLAN IDs:{RESET}  {', '.join(vids)}")

        dns = r["network"]["dns"]
        if dns:
            print(f"  DNS: {DIM}{dns}{RESET}")

        default_routes = [rt for rt in r["network"]["routes"] if rt.startswith("default")]
        if default_routes:
            print(f"  Default routes: {DIM}{' | '.join(default_routes)}{RESET}")

        netplan = r["network"]["netplan"]
        if netplan:
            print(f"\n  Netplan files: {DIM}{', '.join(f.split('/')[-1] for f in netplan)}{RESET}")

    # ── DOCKER ───────────────────────────────────────────────────────────
    if all_sec or "docker" in selected_sections:
        dk = r["docker"]
        if not dk["present"]:
            print(f"\n  {DIM}[ Docker not present ]{RESET}")
        else:
            print(_hdr("DOCKER"))
            ver = dk["version"] or "?"
            comp = dk["compose_version"] or "?"
            imgs = dk["images"]
            vols = dk["volumes"]
            nets = dk["networks"]
            print(
                f"  Docker {BOLD}{ver}{RESET}  Compose {comp}  │  Images {imgs}  Volumes {vols}  Networks {nets}"
            )

            # docker system df
            df_lines = dk["df"]
            if df_lines:
                dk_df_str = ", ".join(f"{d['type']} {d['size']}" for d in df_lines)
                print(f"  {DIM}Disk usage: {dk_df_str}{RESET}")

            running = dk["containers_running"]
            stats = dk["containers_stats"]
            if running:
                print(f"\n  {GREEN}{BOLD}Running containers ({len(running)}):{RESET}")
                for container in running:
                    container_stats = stats.get(container["name"])
                    cpu = container_stats["cpu"] if container_stats else "?"
                    mem = container_stats["mem"] if container_stats else "?"
                    memp = container_stats["mem_pct"] if container_stats else "?"
                    ports = container["ports"]
                    # Truncate long port strings
                    if len(ports) > 40:
                        ports = ports[:37] + "..."
                    print(
                        f"    {GREEN}▶{RESET}  {BOLD}{container['name']:<28}{RESET}  "
                        f"cpu {CYAN}{cpu:>6}{RESET}  mem {CYAN}{memp:>6}{RESET} ({mem})"
                    )
                    print(f"       {DIM}image: {container['image']}{RESET}")
                    if ports:
                        print(f"       {DIM}ports: {ports}{RESET}")
            else:
                print(f"\n  {YELLOW}No running containers{RESET}")

            stopped = dk["containers_stopped"]
            if stopped:
                print(f"\n  {YELLOW}Stopped containers ({len(stopped)}):{RESET}")
                for stopped_container in stopped:
                    print(
                        f"    {YELLOW}■{RESET}  {stopped_container['name']:<28}  "
                        f"{DIM}{stopped_container['status']}{RESET}"
                    )

    # ── SERVICES & PORTS ─────────────────────────────────────────────────
    if all_sec or "services" in selected_sections:
        svc = r["services"]
        print(_hdr("SERVICES & PORTS"))

        key_svcs = svc["key_services"]
        if key_svcs:
            active_svcs = [s for s, st in key_svcs.items() if st == "active"]
            inactive_svcs = [s for s, st in key_svcs.items() if st != "active"]
            if active_svcs:
                print(f"  Running: {GREEN}{', '.join(active_svcs)}{RESET}")
            if inactive_svcs:
                print(f"  Inactive: {DIM}{', '.join(inactive_svcs)}{RESET}")

        failed = svc["failed"]
        if failed:
            print(f"  {RED}{BOLD}Failed units ({len(failed)}):{RESET}")
            for f in failed:
                print(f"    {RED}✗  {f['unit']}{RESET}")

        tcp_ports = svc["ports_tcp"]
        if tcp_ports:
            print(f"\n  Listening TCP ports ({len(tcp_ports)}):")
            for tcp_port in tcp_ports[:20]:  # limit to first 20
                print(f"    {DIM}{tcp_port['local']:<28}{RESET}  {tcp_port['proc']}")
            if len(tcp_ports) > 20:
                print(f"    {DIM}... and {len(tcp_ports) - 20} more{RESET}")

    # ── FIREWALL ─────────────────────────────────────────────────────────
    if all_sec or "firewall" in selected_sections:
        fw = r["firewall"]
        fw_type = fw["type"]
        print(_hdr("FIREWALL"))
        if fw_type == "ufw":
            status = fw["status"]
            sc = GREEN if status.lower() == "active" else RED
            print(f"  UFW  {sc}{BOLD}{status}{RESET}")
            rules = fw["rules"]
            if rules:
                print(f"  Rules ({len(rules)}):")
                for rule in rules:
                    print(f"    {DIM}{rule}{RESET}")
        elif fw_type == "iptables":
            policy = fw["policy_input"]
            in_rules = fw["input_rules"]
            fwd_rules = fw["forward_rules"]
            chains = fw["custom_chains"]
            pc = GREEN if policy == "DROP" else (YELLOW if policy == "ACCEPT" else RED)
            print(
                f"  iptables  INPUT policy: {pc}{BOLD}{policy}{RESET}  │  "
                f"{in_rules} INPUT rules  │  {fwd_rules} FORWARD rules  │  {chains} custom chains"
            )
        else:
            print(f"  {YELLOW}No firewall detected{RESET}")

    # ── SECURITY ─────────────────────────────────────────────────────────
    if all_sec or "security" in selected_sections:
        sec = r["security"]
        print(_hdr("SECURITY"))
        permit_root = sec["sec_permit_root"]
        pass_auth = sec["sec_pass_auth"]
        pubkey = sec["sec_pubkey_auth"]
        ssh_port = sec["sec_ssh_port"]
        fail2ban = sec["sec_fail2ban"]
        root_keys = sec["sec_root_keys"]
        unattended = sec["sec_unattended"]
        sudo_users = sec["sec_sudo_users"]

        pr_col = GREEN if permit_root in ("no", "prohibit-password") else RED
        pa_col = GREEN if pass_auth == "no" else RED
        fb_col = GREEN if fail2ban == "active" else YELLOW
        un_col = GREEN if unattended != "0" else YELLOW

        print(f"  SSH port     {BOLD}{ssh_port}{RESET}")
        print(
            f"  PermitRoot   {pr_col}{BOLD}{permit_root}{RESET}  │  "
            f"PasswordAuth {pa_col}{BOLD}{pass_auth}{RESET}  │  "
            f"PubkeyAuth {GREEN if pubkey != 'no' else RED}{pubkey}{RESET}"
        )
        print(
            f"  Root keys    {root_keys}  │  "
            f"fail2ban {fb_col}{fail2ban}{RESET}  │  "
            f"unattended-upgrades {un_col}{'yes' if unattended != '0' else 'no'}{RESET}"
        )
        if sudo_users:
            print(f"  Sudo users:  {DIM}{sudo_users}{RESET}")

    # ── PROCESSES ────────────────────────────────────────────────────────
    if all_sec or "processes" in selected_sections:
        procs = r["processes"]
        cpu_top = procs["top_cpu"]
        mem_top = procs["top_mem"]
        if cpu_top or mem_top:
            print(_hdr("TOP PROCESSES"))
            if cpu_top:
                print(f"  {BOLD}CPU%:{RESET}")
                for process_entry in cpu_top:
                    print(
                        f"    {process_entry['cpu']:>6}%  {process_entry['mem']:>6}% MEM  "
                        f"{DIM}{process_entry['cmd'][:50]}{RESET}  (pid {process_entry['pid']})"
                    )
            if mem_top:
                print(f"  {BOLD}MEM%:{RESET}")
                for process_entry in mem_top:
                    print(
                        f"    {process_entry['mem']:>6}%  {process_entry['cpu']:>6}% CPU  "
                        f"{DIM}{process_entry['cmd'][:50]}{RESET}  (pid {process_entry['pid']})"
                    )


# ---------------------------------------------------------------------------
# Cluster-wide summary
# ---------------------------------------------------------------------------
def print_cluster_summary(results: list[AuditReport]) -> None:
    print(f"\n\n{BOLD}{'═' * W}{RESET}")
    print(f"{BOLD}{'  CLUSTER FULL AUDIT — SUMMARY':^{W}}{RESET}")
    print(f"{BOLD}{'═' * W}{RESET}")

    ok = [r for r in results if not r["error"]]
    err = [r for r in results if r["error"]]
    total = len(results)

    # Connectivity
    print(
        f"\n  {BOLD}Connectivity:{RESET}  "
        f"{GREEN}{len(ok)}{RESET}/{total} UP  "
        f"{RED if err else DIM}{len(err)} unreachable{RESET}"
    )
    if err:
        for r in err:
            error_msg = r["error"] or ""
            print(f"    {RED}✗  {r['alias']:<12}  {error_msg[:60]}{RESET}")

    # OS / kernel matrix
    print(f"\n  {BOLD}OS / Kernel:{RESET}")
    os_counter: dict[str, list[str]] = {}
    for r in ok:
        os_ = r["system"].get("os", "?")
        os_counter.setdefault(os_, []).append(r["alias"])
    for os_, nodes in os_counter.items():
        print(f"    {DIM}{os_:<45}{RESET}  {', '.join(nodes)}")

    # Hardware overview
    print(f"\n  {BOLD}Hardware overview:{RESET}")
    print(
        f"  {'Node':<12}  {'CPU cores':>9}  {'RAM GB':>7}  {'RAM%':>5}  {'Disk (root)':>12}  {'GPU'}"
    )
    print(f"  {_sep()}")
    for r in ok:
        hw = r["hardware"]
        cores = hw.get("cpu_cores", "?")
        ram_tot = _as_float(hw.get("ram_total_gb", 0.0))
        ram_pct = _as_float(hw.get("ram_used_pct", 0.0))
        ram_col = GREEN if ram_pct < 60 else (YELLOW if ram_pct < 80 else RED)
        # root partition
        root_part = next(
            (
                p
                for p in r["disk"]["partitions"]
                if p["mountpoint"] in ("/", "/boot") or p["mountpoint"] == "/"
            ),
            None,
        )
        if root_part:
            rk_sz = _as_int(root_part["size_kb"])
            rk_us = _as_int(root_part["used_kb"])
            rk_pct = round(rk_us / rk_sz * 100, 0) if rk_sz else 0
            disk_col = GREEN if rk_pct < 70 else (YELLOW if rk_pct < 85 else RED)
            disk_str = f"{disk_col}{int(rk_us / 1024 / 1024)}/{int(rk_sz / 1024 / 1024)} GB{RESET}"
        else:
            disk_str = DIM + "N/A" + RESET
        gpus = r["gpu"]
        gpu_str = (
            f"{MAG}{', '.join(g['gpu_name'].strip() for g in gpus)}{RESET}"
            if gpus
            else f"{DIM}none{RESET}"
        )
        print(
            f"  {r['alias']:<12}  {cores:>9}  {ram_tot:>7.1f}  "
            f"{ram_col}{ram_pct:>5.1f}%{RESET}  {disk_str:>20}  {gpu_str}"
        )

    # Docker summary
    docker_nodes = [r for r in ok if r["docker"]["present"]]
    if docker_nodes:
        print(f"\n  {BOLD}Docker containers:{RESET}")
        total_running = sum(len(r["docker"]["containers_running"]) for r in docker_nodes)
        total_stopped = sum(len(r["docker"]["containers_stopped"]) for r in docker_nodes)
        print(
            f"  {GREEN}{total_running} running{RESET}  {YELLOW}{total_stopped} stopped{RESET}  "
            f"across {len(docker_nodes)} nodes"
        )
        for r in docker_nodes:
            running = r["docker"]["containers_running"]
            stopped = r["docker"]["containers_stopped"]
            if running:
                names = [c["name"] for c in running]
                print(f"  {GREEN}  {r['alias']:<12}{RESET}  ▶ {', '.join(names)}")
            if stopped:
                names = [c["name"] for c in stopped]
                print(f"  {YELLOW}  {r['alias']:<12}{RESET}  ■ {', '.join(names)}")

    # Network / vSwitch summary
    print(f"\n  {BOLD}Network / vSwitch:{RESET}")
    for r in ok:
        priv = r["network"]["private_ips"]
        vids = r["network"]["vlan_ids"]
        if priv or vids:
            priv_str = f"{GREEN}{', '.join(priv)}{RESET}"
            vlan_str = f"  VLAN: {CYAN}{', '.join(vids)}{RESET}" if vids else ""
            print(f"    {GREEN}✓{RESET}  {r['alias']:<12}  {priv_str}{vlan_str}")
        else:
            print(f"    {YELLOW}⚠{RESET}  {r['alias']:<12}  no private IP")

    # Security audit
    print(f"\n  {BOLD}Security quick-scan:{RESET}")
    sec_issues: list[tuple[str, str]] = []
    for r in ok:
        sec = r["security"]
        alias = r["alias"]
        permit = sec["sec_permit_root"]
        passw = sec["sec_pass_auth"]
        if permit not in ("no", "prohibit-password"):
            sec_issues.append((alias, f"PermitRootLogin={permit}"))
        if passw not in ("no", "not-set"):
            sec_issues.append((alias, f"PasswordAuthentication={passw}"))
    if sec_issues:
        print(f"  {RED}{BOLD}Issues found:{RESET}")
        for alias, issue in sec_issues:
            print(f"    {RED}⚠  {alias:<12}  {issue}{RESET}")
    else:
        print(f"    {GREEN}✓  No critical SSH misconfigurations detected{RESET}")

    # Failed services
    all_failed = [(r["alias"], f["unit"]) for r in ok for f in r["services"]["failed"]]
    if all_failed:
        print(f"\n  {RED}{BOLD}Failed systemd units:{RESET}")
        for alias, unit in all_failed:
            print(f"    {RED}✗  {alias:<12}  {unit}{RESET}")

    # High resource usage warnings
    warnings: list[tuple[str, str]] = []
    for r in ok:
        hw = r["hardware"]
        ram_pct = _as_float(hw.get("ram_used_pct", 0.0))
        if ram_pct > 85:
            warnings.append((r["alias"], f"RAM usage {ram_pct:.0f}%"))
        for p in r["disk"]["partitions"]:
            pct_str = p["pct"].rstrip("%")
            try:
                pct_val = float(pct_str)
            except ValueError:
                pct_val = 0
            if pct_val > 80:
                warnings.append((r["alias"], f"Disk {p['mountpoint']} {pct_val:.0f}%"))
        for g in r["gpu"]:
            mem_tot = _as_int(g["gpu_mem_total"])
            mem_used = _as_int(g["gpu_mem_used"])
            if mem_tot and mem_used / mem_tot > 0.90:
                pct = round(mem_used / mem_tot * 100, 1)
                warnings.append((r["alias"], f"VRAM {pct:.0f}%"))
            try:
                temp = _as_float(g["gpu_temp"])
                if temp > 80:
                    warnings.append((r["alias"], f"GPU temp {temp:.0f}°C"))
            except (ValueError, TypeError):
                pass
    if warnings:
        print(f"\n  {YELLOW}{BOLD}Resource warnings:{RESET}")
        for alias, msg in warnings:
            print(f"    {YELLOW}⚠  {alias:<12}  {msg}{RESET}")
    else:
        print(f"\n    {GREEN}✓  No resource overload detected{RESET}")

    print(f"\n{BOLD}{'═' * W}{RESET}")
    print(f"{DIM}  Audit completed {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}{RESET}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
VALID_SECTIONS = {
    "system",
    "hardware",
    "gpu",
    "disk",
    "network",
    "docker",
    "services",
    "firewall",
    "security",
    "processes",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Full-spectrum read-only cluster audit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python subprojects/cluster-full-audit/audit_full.py
  python subprojects/cluster-full-audit/audit_full.py --node hz.113
  python subprojects/cluster-full-audit/audit_full.py --section gpu --section docker
  python subprojects/cluster-full-audit/audit_full.py --json /tmp/audit.json
  python subprojects/cluster-full-audit/audit_full.py --json -
""",
    )
    parser.add_argument("--workers", type=int, default=6, help="Parallel SSH workers (default: 6)")
    parser.add_argument(
        "--node", type=str, default=None, help="Audit only one node (alias, e.g. hz.113)"
    )
    parser.add_argument(
        "--section",
        action="append",
        dest="sections",
        default=None,
        choices=sorted(VALID_SECTIONS),
        help="Show only these sections (can be repeated). Default: all",
    )
    parser.add_argument(
        "--json",
        metavar="FILE",
        default=None,
        help="Also write full JSON to FILE (use '-' for stdout)",
    )
    parser.add_argument("--no-summary", action="store_true", help="Skip the cluster-wide summary")
    args = parser.parse_args()

    targets = [(a, ip) for a, ip in CLUSTER if args.node is None or a == args.node]
    if not targets:
        print(f"{RED}Node '{args.node}' not found in cluster.{RESET}")
        sys.exit(1)

    print(f"\n{BOLD}{'═' * W}{RESET}")
    print(f"{BOLD}{'  CLUSTER FULL AUDIT':^{W}}{RESET}")
    print(
        f"{BOLD}  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}  │  "
        f"{len(targets)} nodes  │  workers={args.workers}{RESET}"
    )
    print(f"{BOLD}{'═' * W}{RESET}\n")

    results: list[AuditReport | None] = [None] * len(targets)
    alias_index = {a: i for i, (a, _) in enumerate(targets)}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(audit_node, a, ip): a for a, ip in targets}
        for fut in as_completed(futures):
            alias = futures[fut]
            r = fut.result()
            results[alias_index[alias]] = r
            if r["error"]:
                print(f"  {RED}[ERR]{RESET} {alias}  — {r['error'][:60]}")
            else:
                gpus = r["gpu"]
                ctrs = len(r["docker"]["containers_running"])
                ram = _as_float(r["hardware"].get("ram_used_pct", 0.0))
                gpu_tag = f"  {MAG}GPU:{len(gpus)}{RESET}" if gpus else ""
                print(
                    f"  {GREEN}[ OK]{RESET} {alias:<12}{gpu_tag}  "
                    f"RAM {GREEN if ram < 80 else RED}{ram:.0f}%{RESET}  "
                    f"containers: {ctrs}"
                )

    final_results = [r for r in results if r is not None]

    for r in final_results:
        print_node_report(r, sections=args.sections)

    if not args.no_summary:
        print_cluster_summary(final_results)

    if args.json:
        # Strip ANSI from JSON export
        import re as _re

        _ansi = _re.compile(r"\x1b\[[0-9;]*m")

        def _clean(obj: object) -> object:
            if isinstance(obj, str):
                return _ansi.sub("", obj)
            if isinstance(obj, dict):
                cleaned_dict: dict[str, object] = {}
                for key, value in cast(dict[object, object], obj).items():
                    cleaned_dict[str(key)] = _clean(value)
                return cleaned_dict
            if isinstance(obj, list):
                return [_clean(item) for item in cast(list[object], obj)]
            return obj

        payload: dict[str, object] = {
            "audit_ts": datetime.now(UTC).isoformat(),
            "nodes": [_clean(r) for r in final_results],
        }
        json_str = json.dumps(payload, indent=2, ensure_ascii=False)
        if args.json == "-":
            print(json_str)
        else:
            with open(args.json, "w", encoding="utf-8") as fh:
                fh.write(json_str)
            print(f"\n{GREEN}JSON written → {args.json}{RESET}")


if __name__ == "__main__":
    main()
