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
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import TypedDict, cast

SystemInfo = dict[str, str]
HardwareValue = str | float | bool
HardwareInfo = dict[str, HardwareValue]
SecurityInfo = dict[str, str]

GPU_FIELD_MAP = {
    "GPU_NAME": "gpu_name",
    "GPU_UUID": "gpu_uuid",
    "GPU_DRIVER": "gpu_driver",
    "GPU_MEM_TOTAL": "gpu_mem_total",
    "GPU_MEM_USED": "gpu_mem_used",
    "GPU_MEM_FREE": "gpu_mem_free",
    "GPU_UTIL": "gpu_util",
    "GPU_MEM_UTIL": "gpu_mem_util",
    "GPU_TEMP": "gpu_temp",
    "GPU_POWER_DRAW": "gpu_power_draw",
    "GPU_POWER_LIMIT": "gpu_power_limit",
    "GPU_FAN": "gpu_fan",
    "GPU_SM_CLOCK": "gpu_sm_clock",
    "GPU_GR_CLOCK": "gpu_gr_clock",
    "GPU_COMPUTE_CAP": "gpu_compute_cap",
}
SECTION_HEADERS = {
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
}
HARDWARE_KEYS = (
    "CPU_MODEL",
    "CPU_PHYSICAL",
    "CPU_CORES",
    "RAM_TOTAL_KB",
    "RAM_FREE_KB",
    "RAM_BUFFERS_KB",
    "RAM_CACHED_KB",
    "SWAP_TOTAL_KB",
    "SWAP_FREE_KB",
)
SYSTEM_KEYS = (
    "HOSTNAME",
    "KERNEL",
    "ARCH",
    "OS",
    "UPTIME_SEC",
    "UPTIME_HUMAN",
    "LOAD",
    "LOGGED_USERS",
    "DATE_UTC",
)
SECURITY_KEYS = (
    "SEC_PERMIT_ROOT",
    "SEC_PASS_AUTH",
    "SEC_PUBKEY_AUTH",
    "SEC_SSH_PORT",
    "SEC_FAIL2BAN",
    "SEC_ROOT_KEYS",
    "SEC_SUDO_USERS",
    "SEC_UNATTENDED",
)
DISK_PARTITION_FIELD_COUNT = 7
BLOCK_DEVICE_MIN_PARTS = 5
PROCESS_FIELD_COUNT = 6
NETWORK_INTERFACE_MIN_PARTS = 3
NETWORK_INTERFACE_ADDRS_INDEX = 3
CONTAINER_MIN_PARTS = 4
SERVICES_PROC_INDEX = 2
KEY_SERVICE_PARTS = 3
DOCKER_EXTRA_FIELD_INDEX = 4
BLOCK_DEVICE_MODEL_INDEX = 5
GREEN_THRESHOLD = 60
YELLOW_THRESHOLD = 80
GPU_TEMP_GREEN_THRESHOLD = 70
GPU_TEMP_YELLOW_THRESHOLD = 82
PORTS_TRUNCATE_THRESHOLD = 40
PORTS_TRUNCATE_LENGTH = 37
MAX_PORT_LINES = 20
DISK_WARN_THRESHOLD = 80
RAM_WARN_THRESHOLD = 85
VRAM_WARN_THRESHOLD = 0.90
BLOCK_DEVICE_ROTATIONAL_FLAG = "1"
OK_RAM_THRESHOLD = 80
JSON_INDENT = 2
SKIP_FILESYSTEMS = (
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
    field_name = GPU_FIELD_MAP.get(key)
    if field_name is not None:
        cast(dict[str, str], gpu)[field_name] = value


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
echo "CPU_MODEL=$(\
    grep -m1 'model name' /proc/cpuinfo 2>/dev/null \
    | cut -d: -f2 \
    | xargs || echo unknown\
)"
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
    nvidia-smi \
        --query-gpu=name,uuid,driver_version,memory.total,memory.used,memory.free,\
utilization.gpu,utilization.memory,temperature.gpu,power.draw,power.limit,\
fan.speed,clocks.sm,clocks.gr,compute_cap \
        --format=csv,noheader,nounits 2>/dev/null \
    | while IFS=',' read -r \
        name uuid drv mem_tot mem_used mem_free util_gpu util_mem \
        temp pwr_draw pwr_lim fan sm_clk gr_clk cc; do
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
df -P -x tmpfs -x devtmpfs -x squashfs 2>/dev/null \
    | tail -n +2 \
    | while read fs size used avail pct mp; do
    echo "DF|$fs|$size|$used|$avail|$pct|$mp"
done
# Disk I/O scheduler & block devices
lsblk -d -o NAME,SIZE,ROTA,TYPE,MODEL 2>/dev/null \
    | tail -n +2 \
    | while read name size rota type model; do
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
echo "DNS_RESOLV=$(\
    grep '^nameserver' /etc/resolv.conf 2>/dev/null \
    | awk '{print $2}' \
    | tr '\n' ',' \
    | sed 's/,$//'\
)"

###  DOCKER  ###
echo "=== DOCKER ==="
if command -v docker &>/dev/null; then
    echo "DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo error)"
    echo "DOCKER_COMPOSE=$(\
        docker compose version 2>/dev/null \
        | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' \
        | head -1 || echo N/A\
    )"
    # Running containers: ID|Name|Image|Status|Ports|CPUPerc|MemUsage|MemPerc|RestartCount
    docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}' 2>/dev/null \
        | while IFS='|' read name img status ports; do
        echo "CONTAINER_RUN|$name|$img|$status|$ports"
    done
    # Stats (non-blocking snapshot)
    docker stats --no-stream \
        --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}' 2>/dev/null \
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
systemctl list-units --state=failed --no-legend --no-pager 2>/dev/null \
    | while read unit load active sub desc; do
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
    echo "FW_POLICY_INPUT=$(\
        iptables -L INPUT --line-numbers -n 2>/dev/null \
        | head -1 \
        | grep -oE 'policy [A-Z]+' \
        | cut -d' ' -f2 || echo unknown\
    )"
    echo "FW_INPUT_RULES=$(iptables -L INPUT -n 2>/dev/null | tail -n +3 | wc -l)"
    echo "FW_FORWARD_RULES=$(iptables -L FORWARD -n 2>/dev/null | tail -n +3 | wc -l)"
    echo "FW_CUSTOM_CHAINS=$(\
        iptables -L -n 2>/dev/null \
        | grep '^Chain ' \
        | grep -vE 'INPUT|OUTPUT|FORWARD' \
        | wc -l\
    )"
else
    echo "FW_TYPE=none"
fi

###  SECURITY  ###
echo "=== SECURITY ==="
echo "SEC_PERMIT_ROOT=$(grep -E '^PermitRootLogin' /etc/ssh/sshd_config 2>/dev/null \
    | awk '{print $2}' || echo not-set)"
echo "SEC_PASS_AUTH=$(grep -E '^PasswordAuthentication' /etc/ssh/sshd_config 2>/dev/null \
    | awk '{print $2}' || echo not-set)"
echo "SEC_PUBKEY_AUTH=$(grep -E '^PubkeyAuthentication' /etc/ssh/sshd_config 2>/dev/null \
    | awk '{print $2}' || echo not-set)"
echo "SEC_SSH_PORT=$(grep -E '^Port ' /etc/ssh/sshd_config 2>/dev/null \
    | awk '{print $2}' || echo 22)"
echo "SEC_FAIL2BAN=$(systemctl is-active fail2ban 2>/dev/null || echo inactive)"
echo "SEC_ROOT_KEYS=$(cat /root/.ssh/authorized_keys 2>/dev/null | grep -c 'ssh-' || echo 0)"
echo "SEC_SUDO_USERS=$(\
    getent group sudo 2>/dev/null | cut -d: -f4 \
    || getent group wheel 2>/dev/null | cut -d: -f4 \
    || echo unknown\
)"
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


def _parse_prefixed_assignment(target: dict[str, str], line: str, keys: tuple[str, ...]) -> bool:
    for key in keys:
        if line.startswith(f"{key}="):
            target[key.lower()] = line.split("=", 1)[1]
            return True
    return False


def _parse_prefixed_assignment_hardware(
    target: HardwareInfo, line: str, keys: tuple[str, ...]
) -> bool:
    for key in keys:
        if line.startswith(f"{key}="):
            target[key.lower()] = line.split("=", 1)[1]
            return True
    return False


def _parse_docker_scalar_line(report: AuditReport, line: str) -> bool:
    scalar_prefixes = (
        "DOCKER_PRESENT=",
        "DOCKER_VERSION=",
        "DOCKER_COMPOSE=",
        "DOCKER_IMAGES=",
        "DOCKER_VOLUMES=",
        "DOCKER_NETWORKS=",
    )
    for prefix in scalar_prefixes:
        if line.startswith(prefix):
            _set_docker_scalar(report, prefix, line.split("=", 1)[1])
            return True
    return False


def _set_docker_scalar(report: AuditReport, prefix: str, value: str) -> None:
    if prefix == "DOCKER_PRESENT=":
        report["docker"]["present"] = False
    elif prefix == "DOCKER_VERSION=":
        report["docker"]["version"] = value
    elif prefix == "DOCKER_COMPOSE=":
        report["docker"]["compose_version"] = value
    elif prefix == "DOCKER_IMAGES=":
        report["docker"]["images"] = int(value or 0)
    elif prefix == "DOCKER_VOLUMES=":
        report["docker"]["volumes"] = int(value or 0)
    elif prefix == "DOCKER_NETWORKS=":
        report["docker"]["networks"] = int(value or 0)


def _parse_gpu_line(report: AuditReport, line: str, gpu_current: GpuInfo | None) -> GpuInfo | None:
    if line.startswith("GPU_COUNT="):
        report["hardware"]["gpu_count"] = line.split("=", 1)[1]
        return gpu_current
    if line == "GPU_ENTRY_END":
        if gpu_current is not None:
            report["gpu"].append(gpu_current)
        return None
    if line.startswith("GPU_PRESENT="):
        report["hardware"]["gpu_present"] = False
        return gpu_current
    for key in GPU_FIELD_MAP:
        if line.startswith(f"{key}="):
            if gpu_current is None:
                gpu_current = _empty_gpu_info()
            _set_gpu_field(gpu_current, key, line.split("=", 1)[1])
            return gpu_current
    return gpu_current


def _parse_disk_line(report: AuditReport, line: str) -> None:
    if line.startswith("DF|"):
        parts = line.split("|")
        if len(parts) >= DISK_PARTITION_FIELD_COUNT:
            report["disk"]["partitions"].append(
                {
                    "fs": parts[1],
                    "size_kb": parts[2],
                    "used_kb": parts[3],
                    "avail_kb": parts[4],
                    "pct": parts[5],
                    "mountpoint": parts[6],
                }
            )
        return
    if line.startswith("BLK|"):
        parts = line.split("|", 5)
        if len(parts) >= BLOCK_DEVICE_MIN_PARTS:
            report["disk"]["block_devs"].append(
                {
                    "name": parts[1],
                    "size": parts[2],
                    "rotational": parts[3] == BLOCK_DEVICE_ROTATIONAL_FLAG,
                    "type": parts[4],
                    "model": (
                        parts[BLOCK_DEVICE_MODEL_INDEX]
                        if len(parts) > BLOCK_DEVICE_MODEL_INDEX
                        else ""
                    ),
                }
            )


def _parse_network_line(report: AuditReport, line: str) -> None:
    if line.startswith("IFACE|"):
        parts = line.split("|", 3)
        if len(parts) >= NETWORK_INTERFACE_MIN_PARTS:
            report["network"]["interfaces"].append(
                {
                    "name": parts[1],
                    "state": parts[2],
                    "addrs": parts[NETWORK_INTERFACE_ADDRS_INDEX].split()
                    if len(parts) > NETWORK_INTERFACE_ADDRS_INDEX
                    else [],
                }
            )
        return
    if line.startswith("VLANID|"):
        report["network"]["vlan_ids"].append(line[7:].strip())
    elif line.startswith("ROUTE|"):
        report["network"]["routes"].append(line[6:].strip())
    elif line.startswith("DNS_RESOLV="):
        report["network"]["dns"] = line.split("=", 1)[1]


def _parse_docker_line(report: AuditReport, line: str) -> None:
    if _parse_docker_scalar_line(report, line):
        return

    if line.startswith("CONTAINER_RUN|"):
        parts = line.split("|", 4)
        if len(parts) >= CONTAINER_MIN_PARTS:
            ports = parts[DOCKER_EXTRA_FIELD_INDEX] if len(parts) > DOCKER_EXTRA_FIELD_INDEX else ""
            report["docker"]["containers_running"].append(
                {
                    "name": parts[1],
                    "image": parts[2],
                    "status": parts[3],
                    "ports": ports,
                }
            )
        return
    if line.startswith("CONTAINER_STAT|"):
        parts = line.split("|", 4)
        if len(parts) >= CONTAINER_MIN_PARTS:
            mem_pct = (
                parts[DOCKER_EXTRA_FIELD_INDEX] if len(parts) > DOCKER_EXTRA_FIELD_INDEX else ""
            )
            report["docker"]["containers_stats"][parts[1]] = {
                "cpu": parts[2],
                "mem": parts[3],
                "mem_pct": mem_pct,
            }
        return
    if line.startswith("CONTAINER_STOP|"):
        parts = line.split("|", 3)
        if len(parts) >= NETWORK_INTERFACE_MIN_PARTS:
            report["docker"]["containers_stopped"].append(
                {
                    "name": parts[1],
                    "image": parts[2],
                    "status": parts[NETWORK_INTERFACE_ADDRS_INDEX]
                    if len(parts) > NETWORK_INTERFACE_ADDRS_INDEX
                    else "",
                }
            )
        return
    if line.startswith("DOCKER_DF|"):
        parts = line.split("|", 3)
        if len(parts) >= NETWORK_INTERFACE_MIN_PARTS:
            report["docker"]["df"].append(
                {
                    "type": parts[1],
                    "size": parts[2],
                    "reclaimable": parts[NETWORK_INTERFACE_ADDRS_INDEX]
                    if len(parts) > NETWORK_INTERFACE_ADDRS_INDEX
                    else "",
                }
            )


def _parse_services_line(report: AuditReport, line: str) -> None:
    if line.startswith("PORT_TCP|"):
        parts = line.split("|", 2)
        proc = parts[SERVICES_PROC_INDEX] if len(parts) > SERVICES_PROC_INDEX else ""
        report["services"]["ports_tcp"].append({"local": parts[1], "proc": proc})
    elif line.startswith("PORT_UDP|"):
        parts = line.split("|", 2)
        proc = parts[SERVICES_PROC_INDEX] if len(parts) > SERVICES_PROC_INDEX else ""
        report["services"]["ports_udp"].append({"local": parts[1], "proc": proc})
    elif line.startswith("SVC_FAILED|"):
        parts = line.split("|", 2)
        sub = parts[SERVICES_PROC_INDEX] if len(parts) > SERVICES_PROC_INDEX else ""
        report["services"]["failed"].append({"unit": parts[1], "sub": sub})
    elif line.startswith("SVC_KEY|"):
        parts = line.split("|", 2)
        if len(parts) >= KEY_SERVICE_PARTS:
            report["services"]["key_services"][parts[1]] = parts[2]


def _parse_firewall_line(report: AuditReport, line: str) -> None:
    if line.startswith("FW_TYPE="):
        report["firewall"]["type"] = line.split("=", 1)[1]
    elif line.startswith("FW_STATUS="):
        report["firewall"]["status"] = line.split("=", 1)[1]
    elif line.startswith("FW_RULE|"):
        report["firewall"]["rules"].append(line[8:].strip())
    elif line.startswith("FW_POLICY_INPUT="):
        report["firewall"]["policy_input"] = line.split("=", 1)[1]
    elif line.startswith("FW_INPUT_RULES="):
        report["firewall"]["input_rules"] = int(line.split("=", 1)[1] or 0)
    elif line.startswith("FW_CUSTOM_CHAINS="):
        report["firewall"]["custom_chains"] = int(line.split("=", 1)[1] or 0)
    elif line.startswith("FW_FORWARD_RULES="):
        report["firewall"]["forward_rules"] = int(line.split("=", 1)[1] or 0)


def _parse_process_line(report: AuditReport, line: str) -> None:
    target = None
    if line.startswith("PROC_CPU|"):
        target = report["processes"]["top_cpu"]
    elif line.startswith("PROC_MEM|"):
        target = report["processes"]["top_mem"]
    if target is None:
        return
    parts = line.split("|", 5)
    if len(parts) >= PROCESS_FIELD_COUNT:
        target.append(
            {
                "user": parts[1],
                "pid": parts[2],
                "cpu": parts[3],
                "mem": parts[4],
                "cmd": parts[5],
            }
        )


def _handle_netplan_line(
    report: AuditReport,
    line: str,
    netplan_file: str | None,
    netplan_buf: list[str],
) -> tuple[str | None, list[str], bool]:
    if line.startswith("NETPLAN_FILE:"):
        return line[13:], [], True
    if line == "NETPLAN_END":
        if netplan_file:
            report["network"]["netplan"][netplan_file] = "\n".join(netplan_buf)
        return None, [], True
    if netplan_file is not None:
        netplan_buf.append(line)
        return netplan_file, netplan_buf, True
    return netplan_file, netplan_buf, False


def _apply_section_line(
    report: AuditReport,
    section: str,
    line: str,
    gpu_current: GpuInfo | None,
) -> GpuInfo | None:
    section_handlers = {
        "disk": _parse_disk_line,
        "network": _parse_network_line,
        "docker": _parse_docker_line,
        "services": _parse_services_line,
        "firewall": _parse_firewall_line,
        "processes": _parse_process_line,
    }
    if section == "system":
        _parse_prefixed_assignment(report["system"], line, SYSTEM_KEYS)
        return gpu_current
    if section == "hardware":
        _parse_prefixed_assignment_hardware(report["hardware"], line, HARDWARE_KEYS)
        return gpu_current
    if section == "security":
        _parse_prefixed_assignment(report["security"], line, SECURITY_KEYS)
        return gpu_current
    if section == "gpu":
        return _parse_gpu_line(report, line, gpu_current)

    handler = section_handlers.get(section)
    if handler is not None:
        handler(report, line)
    return gpu_current


def parse_output(alias: str, pub_ip: str, raw: str) -> AuditReport:
    r = _empty_report(alias, pub_ip)

    section = ""
    gpu_current: GpuInfo | None = None
    netplan_file: str | None = None
    netplan_buf: list[str] = []

    for raw_line in raw.splitlines():
        line = raw_line.rstrip()

        if line in SECTION_HEADERS:
            section = line.strip("= ").lower()
            continue

        netplan_file, netplan_buf, netplan_handled = _handle_netplan_line(
            r, line, netplan_file, netplan_buf
        )
        if netplan_handled:
            continue

        if line.startswith("--- ") and line.endswith(" ---"):
            continue

        gpu_current = _apply_section_line(r, section, line, gpu_current)

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
    color = GREEN if pct < GREEN_THRESHOLD else (YELLOW if pct < YELLOW_THRESHOLD else RED)
    return f"{color}{'█' * filled}{'░' * (width - filled)}{RESET} {pct:5.1f}%"


W = 72  # report width


def _hdr(title: str, color: str = CYAN) -> str:
    return f"\n{color}{'─' * W}{RESET}\n{color}{BOLD}  {title}{RESET}"


def _sep() -> str:
    return f"{DIM}{'─' * W}{RESET}"


def _should_print(all_sections: bool, selected_sections: list[str], name: str) -> bool:
    return all_sections or name in selected_sections


def _print_node_intro(report: AuditReport) -> None:
    alias = report["alias"]
    pub_ip = report["pub_ip"]
    sys_ = report["system"]
    print(f"{BOLD}{CYAN}  {alias}  ({pub_ip}){RESET}")
    print(
        f"{DIM}  {sys_.get('os', '?')}  │  Kernel {sys_.get('kernel', '?')}  │  "
        f"{sys_.get('arch', '?')}  │  Up {sys_.get('uptime_human', '?')}  │  "
        f"Load {sys_.get('load', '?')}{RESET}"
    )


def _print_hardware_section(report: AuditReport) -> None:
    hw = report["hardware"]
    print(_hdr("HARDWARE"))
    ram_used = _as_float(hw.get("ram_used_pct", 0.0))
    swap_tot = _as_float(hw.get("swap_total_gb", 0.0))
    swap_used = _as_float(hw.get("swap_used_gb", 0.0))
    ram_used_gb = _as_float(hw.get("ram_used_gb", 0.0))
    ram_total_gb = _as_float(hw.get("ram_total_gb", 0.0))
    print(
        f"  CPU  {BOLD}{hw.get('cpu_model', '?')}{RESET}  "
        f"[{hw.get('cpu_cores', '?')} cores · {hw.get('cpu_physical', '?')} socket(s)]"
    )
    print(f"  RAM  {_bar(ram_used)}  {ram_used_gb:.2f} / {ram_total_gb:.2f} GB")
    if swap_tot:
        swap_pct = round(swap_used / swap_tot * 100, 1)
        print(f"  SWAP {_bar(swap_pct)}  {swap_used:.2f} / {swap_tot:.2f} GB")
    else:
        print(f"  SWAP {YELLOW}none{RESET}")

    block_devices = report["disk"]["block_devs"]
    if not block_devices:
        return
    print("\n  Block Devices:")
    for block_device in block_devices:
        rotation = "HDD" if block_device["rotational"] else "SSD/NVMe"
        model = block_device["model"].strip()
        print(
            f"    {DIM}{block_device['name']:<12}{RESET}  "
            f"{block_device['size']:<8}  {rotation:<10}  {model}"
        )


def _format_gpu_temp(temp: float) -> str:
    temp_color = (
        GREEN
        if temp < GPU_TEMP_GREEN_THRESHOLD
        else (YELLOW if temp < GPU_TEMP_YELLOW_THRESHOLD else RED)
    )
    return f"{temp_color}{temp:.0f}°C{RESET}"


def _print_gpu_section(report: AuditReport) -> None:
    gpus = report["gpu"]
    hw = report["hardware"]
    if not gpus:
        if hw.get("gpu_count", "0") == "0":
            print(f"\n  {DIM}[ No GPU ]{RESET}")
        return

    print(_hdr("GPU", MAG))
    for index, gpu in enumerate(gpus):
        mem_tot = _as_int(gpu["gpu_mem_total"])
        mem_used = _as_int(gpu["gpu_mem_used"])
        mem_pct = round(mem_used / mem_tot * 100, 1) if mem_tot else 0
        util_gpu = _as_float(gpu["gpu_util"])
        try:
            temp_str = _format_gpu_temp(_as_float(gpu["gpu_temp"]))
        except (ValueError, TypeError):
            temp_str = gpu["gpu_temp"]
        print(f"\n  GPU[{index}]  {BOLD}{MAG}{gpu['gpu_name']}{RESET}")
        print(
            f"  Driver {gpu['gpu_driver']}  │  Compute {gpu['gpu_compute_cap']}  │  Temp {temp_str}"
        )
        print(f"  UTIL   {_bar(util_gpu)}")
        print(f"  VRAM   {_bar(mem_pct)}  {mem_used} / {mem_tot} MiB")
        fan = gpu["gpu_fan"] or "N/A"
        print(
            f"  Power  {gpu['gpu_power_draw']} W  /  {gpu['gpu_power_limit']} W limit  │  "
            f"Fan {fan}%  │  Clocks GR:{gpu['gpu_gr_clock']} SM:{gpu['gpu_sm_clock']} MHz"
        )


def _print_disk_section(report: AuditReport) -> None:
    parts = [
        partition
        for partition in report["disk"]["partitions"]
        if partition["fs"] not in SKIP_FILESYSTEMS
        and not partition["mountpoint"].startswith(
            ("/sys", "/proc", "/dev", "/var/lib/docker/rootfs", "/run/", "/snap/")
        )
    ]
    if not parts:
        return
    print(_hdr("DISK"))
    for partition in parts:
        pct_str = partition["pct"].rstrip("%")
        try:
            pct_val = float(pct_str)
        except ValueError:
            pct_val = 0
        size_gb = round(_as_int(partition["size_kb"]) / 1024 / 1024, 1)
        used_gb = round(_as_int(partition["used_kb"]) / 1024 / 1024, 1)
        print(
            f"  {_bar(pct_val)}  {partition['mountpoint']:<20}  {used_gb:.1f}/{size_gb:.1f} GB  "
            f"{DIM}{partition['fs']}{RESET}"
        )


def _print_network_section(report: AuditReport) -> None:
    print(_hdr("NETWORK"))
    for iface in report["network"]["interfaces"]:
        state = iface["state"]
        color = GREEN if state == "UP" else (YELLOW if state == "UNKNOWN" else RED)
        addrs = "  ".join(iface["addrs"]) or "(no IP)"
        print(f"  {color}{iface['name']:<22}{RESET}  {color}{state:<10}{RESET}  {addrs}")

    private_ips = report["network"]["private_ips"]
    if private_ips:
        print(f"\n  {GREEN}{BOLD}Private IPs (vSwitch):{RESET}  {', '.join(private_ips)}")
    else:
        print(f"\n  {YELLOW}⚠  No private IPs — vSwitch not configured{RESET}")

    vlan_ids = report["network"]["vlan_ids"]
    if vlan_ids:
        print(f"  {CYAN}VLAN IDs:{RESET}  {', '.join(vlan_ids)}")

    dns = report["network"]["dns"]
    if dns:
        print(f"  DNS: {DIM}{dns}{RESET}")

    default_routes = [route for route in report["network"]["routes"] if route.startswith("default")]
    if default_routes:
        print(f"  Default routes: {DIM}{' | '.join(default_routes)}{RESET}")

    netplan = report["network"]["netplan"]
    if netplan:
        netplan_files = ", ".join(path.split("/")[-1] for path in netplan)
        print(f"\n  Netplan files: {DIM}{netplan_files}{RESET}")


def _truncate_ports(ports: str) -> str:
    if len(ports) > PORTS_TRUNCATE_THRESHOLD:
        return ports[:PORTS_TRUNCATE_LENGTH] + "..."
    return ports


def _print_docker_section(report: AuditReport) -> None:
    docker = report["docker"]
    if not docker["present"]:
        print(f"\n  {DIM}[ Docker not present ]{RESET}")
        return

    print(_hdr("DOCKER"))
    version = docker["version"] or "?"
    compose_version = docker["compose_version"] or "?"
    print(
        f"  Docker {BOLD}{version}{RESET}  Compose {compose_version}  │  "
        f"Images {docker['images']}  Volumes {docker['volumes']}  Networks {docker['networks']}"
    )

    df_lines = docker["df"]
    if df_lines:
        df_summary = ", ".join(f"{entry['type']} {entry['size']}" for entry in df_lines)
        print(f"  {DIM}Disk usage: {df_summary}{RESET}")

    running = docker["containers_running"]
    stats = docker["containers_stats"]
    if running:
        print(f"\n  {GREEN}{BOLD}Running containers ({len(running)}):{RESET}")
        for container in running:
            container_stats = stats.get(container["name"])
            cpu = container_stats["cpu"] if container_stats else "?"
            mem = container_stats["mem"] if container_stats else "?"
            mem_pct = container_stats["mem_pct"] if container_stats else "?"
            ports = _truncate_ports(container["ports"])
            name = container["name"]
            print(
                f"    {GREEN}▶{RESET}  {BOLD}{name:<28}{RESET}  cpu {CYAN}{cpu:>6}{RESET}  "
                f"mem {CYAN}{mem_pct:>6}{RESET} ({mem})"
            )
            print(f"       {DIM}image: {container['image']}{RESET}")
            if ports:
                print(f"       {DIM}ports: {ports}{RESET}")
    else:
        print(f"\n  {YELLOW}No running containers{RESET}")

    stopped = docker["containers_stopped"]
    if not stopped:
        return
    print(f"\n  {YELLOW}Stopped containers ({len(stopped)}):{RESET}")
    for stopped_container in stopped:
        print(
            f"    {YELLOW}■{RESET}  {stopped_container['name']:<28}  "
            f"{DIM}{stopped_container['status']}{RESET}"
        )


def _print_services_section(report: AuditReport) -> None:
    services = report["services"]
    print(_hdr("SERVICES & PORTS"))

    key_services = services["key_services"]
    if key_services:
        active = [name for name, state in key_services.items() if state == "active"]
        inactive = [name for name, state in key_services.items() if state != "active"]
        if active:
            print(f"  Running: {GREEN}{', '.join(active)}{RESET}")
        if inactive:
            print(f"  Inactive: {DIM}{', '.join(inactive)}{RESET}")

    failed = services["failed"]
    if failed:
        print(f"  {RED}{BOLD}Failed units ({len(failed)}):{RESET}")
        for failed_service in failed:
            print(f"    {RED}✗  {failed_service['unit']}{RESET}")

    tcp_ports = services["ports_tcp"]
    if not tcp_ports:
        return
    print(f"\n  Listening TCP ports ({len(tcp_ports)}):")
    for tcp_port in tcp_ports[:MAX_PORT_LINES]:
        print(f"    {DIM}{tcp_port['local']:<28}{RESET}  {tcp_port['proc']}")
    if len(tcp_ports) > MAX_PORT_LINES:
        remaining = len(tcp_ports) - MAX_PORT_LINES
        print(f"    {DIM}... and {remaining} more{RESET}")


def _print_firewall_section(report: AuditReport) -> None:
    firewall = report["firewall"]
    print(_hdr("FIREWALL"))
    if firewall["type"] == "ufw":
        status = firewall["status"]
        color = GREEN if status.lower() == "active" else RED
        print(f"  UFW  {color}{BOLD}{status}{RESET}")
        rules = firewall["rules"]
        if rules:
            print(f"  Rules ({len(rules)}):")
            for rule in rules:
                print(f"    {DIM}{rule}{RESET}")
        return
    if firewall["type"] == "iptables":
        policy = firewall["policy_input"]
        color = GREEN if policy == "DROP" else (YELLOW if policy == "ACCEPT" else RED)
        print(
            f"  iptables  INPUT policy: {color}{BOLD}{policy}{RESET}  │  "
            f"{firewall['input_rules']} INPUT rules  │  "
            f"{firewall['forward_rules']} FORWARD rules  │  "
            f"{firewall['custom_chains']} custom chains"
        )
        return
    print(f"  {YELLOW}No firewall detected{RESET}")


def _print_security_section(report: AuditReport) -> None:
    security = report["security"]
    permit_root = security["sec_permit_root"]
    pass_auth = security["sec_pass_auth"]
    pubkey = security["sec_pubkey_auth"]
    fail2ban = security["sec_fail2ban"]
    unattended = security["sec_unattended"]

    permit_color = GREEN if permit_root in ("no", "prohibit-password") else RED
    password_color = GREEN if pass_auth == "no" else RED
    fail2ban_color = GREEN if fail2ban == "active" else YELLOW
    unattended_color = GREEN if unattended != "0" else YELLOW

    print(_hdr("SECURITY"))
    print(f"  SSH port     {BOLD}{security['sec_ssh_port']}{RESET}")
    print(
        f"  PermitRoot   {permit_color}{BOLD}{permit_root}{RESET}  │  "
        f"PasswordAuth {password_color}{BOLD}{pass_auth}{RESET}  │  "
        f"PubkeyAuth {GREEN if pubkey != 'no' else RED}{pubkey}{RESET}"
    )
    print(
        f"  Root keys    {security['sec_root_keys']}  │  "
        f"fail2ban {fail2ban_color}{fail2ban}{RESET}  │  "
        f"unattended-upgrades {unattended_color}{'yes' if unattended != '0' else 'no'}{RESET}"
    )
    if security["sec_sudo_users"]:
        print(f"  Sudo users:  {DIM}{security['sec_sudo_users']}{RESET}")


def _print_processes_section(report: AuditReport) -> None:
    cpu_top = report["processes"]["top_cpu"]
    mem_top = report["processes"]["top_mem"]
    if not cpu_top and not mem_top:
        return
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


def _print_connectivity_summary(ok: list[AuditReport], err: list[AuditReport], total: int) -> None:
    print(
        f"\n  {BOLD}Connectivity:{RESET}  {GREEN}{len(ok)}{RESET}/{total} UP  "
        f"{RED if err else DIM}{len(err)} unreachable{RESET}"
    )
    for report in err:
        error_msg = report["error"] or ""
        print(f"    {RED}✗  {report['alias']:<12}  {error_msg[:60]}{RESET}")


def _print_os_summary(ok: list[AuditReport]) -> None:
    print(f"\n  {BOLD}OS / Kernel:{RESET}")
    os_counter: dict[str, list[str]] = {}
    for report in ok:
        os_name = report["system"].get("os", "?")
        os_counter.setdefault(os_name, []).append(report["alias"])
    for os_name, nodes in os_counter.items():
        print(f"    {DIM}{os_name:<45}{RESET}  {', '.join(nodes)}")


def _root_disk_usage(report: AuditReport) -> str:
    root_part = next(
        (
            partition
            for partition in report["disk"]["partitions"]
            if partition["mountpoint"] in ("/", "/boot") or partition["mountpoint"] == "/"
        ),
        None,
    )
    if root_part is None:
        return DIM + "N/A" + RESET
    size_kb = _as_int(root_part["size_kb"])
    used_kb = _as_int(root_part["used_kb"])
    used_pct = round(used_kb / size_kb * 100, 0) if size_kb else 0
    color = (
        GREEN
        if used_pct < GPU_TEMP_GREEN_THRESHOLD
        else (YELLOW if used_pct < RAM_WARN_THRESHOLD else RED)
    )
    used_gb = int(used_kb / 1024 / 1024)
    size_gb = int(size_kb / 1024 / 1024)
    return f"{color}{used_gb}/{size_gb} GB{RESET}"


def _print_hardware_summary(ok: list[AuditReport]) -> None:
    print(f"\n  {BOLD}Hardware overview:{RESET}")
    print(
        f"  {'Node':<12}  {'CPU cores':>9}  {'RAM GB':>7}  "
        f"{'RAM%':>5}  {'Disk (root)':>12}  {'GPU'}"
    )
    print(f"  {_sep()}")
    for report in ok:
        hw = report["hardware"]
        ram_pct = _as_float(hw.get("ram_used_pct", 0.0))
        ram_color = (
            GREEN if ram_pct < GREEN_THRESHOLD else (YELLOW if ram_pct < YELLOW_THRESHOLD else RED)
        )
        gpu_names = ", ".join(gpu["gpu_name"].strip() for gpu in report["gpu"])
        gpu_str = f"{MAG}{gpu_names}{RESET}" if gpu_names else f"{DIM}none{RESET}"
        ram_total_gb = _as_float(hw.get("ram_total_gb", 0.0))
        print(
            f"  {report['alias']:<12}  {hw.get('cpu_cores', '?'):>9}  {ram_total_gb:>7.1f}  "
            f"{ram_color}{ram_pct:>5.1f}%{RESET}  {_root_disk_usage(report):>20}  {gpu_str}"
        )


def _print_docker_summary(ok: list[AuditReport]) -> None:
    docker_nodes = [report for report in ok if report["docker"]["present"]]
    if not docker_nodes:
        return
    print(f"\n  {BOLD}Docker containers:{RESET}")
    total_running = sum(len(report["docker"]["containers_running"]) for report in docker_nodes)
    total_stopped = sum(len(report["docker"]["containers_stopped"]) for report in docker_nodes)
    print(
        f"  {GREEN}{total_running} running{RESET}  {YELLOW}{total_stopped} stopped{RESET}  "
        f"across {len(docker_nodes)} nodes"
    )
    for report in docker_nodes:
        running_names = [container["name"] for container in report["docker"]["containers_running"]]
        stopped_names = [container["name"] for container in report["docker"]["containers_stopped"]]
        if running_names:
            print(f"  {GREEN}  {report['alias']:<12}{RESET}  ▶ {', '.join(running_names)}")
        if stopped_names:
            print(f"  {YELLOW}  {report['alias']:<12}{RESET}  ■ {', '.join(stopped_names)}")


def _print_network_summary(ok: list[AuditReport]) -> None:
    print(f"\n  {BOLD}Network / vSwitch:{RESET}")
    for report in ok:
        private_ips = report["network"]["private_ips"]
        vlan_ids = report["network"]["vlan_ids"]
        if private_ips or vlan_ids:
            private_str = f"{GREEN}{', '.join(private_ips)}{RESET}"
            vlan_str = f"  VLAN: {CYAN}{', '.join(vlan_ids)}{RESET}" if vlan_ids else ""
            print(f"    {GREEN}✓{RESET}  {report['alias']:<12}  {private_str}{vlan_str}")
        else:
            print(f"    {YELLOW}⚠{RESET}  {report['alias']:<12}  no private IP")


def _collect_security_issues(ok: list[AuditReport]) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    for report in ok:
        permit = report["security"]["sec_permit_root"]
        pass_auth = report["security"]["sec_pass_auth"]
        if permit not in ("no", "prohibit-password"):
            issues.append((report["alias"], f"PermitRootLogin={permit}"))
        if pass_auth not in ("no", "not-set"):
            issues.append((report["alias"], f"PasswordAuthentication={pass_auth}"))
    return issues


def _print_security_summary(ok: list[AuditReport]) -> None:
    print(f"\n  {BOLD}Security quick-scan:{RESET}")
    issues = _collect_security_issues(ok)
    if not issues:
        print(f"    {GREEN}✓  No critical SSH misconfigurations detected{RESET}")
        return
    print(f"  {RED}{BOLD}Issues found:{RESET}")
    for alias, issue in issues:
        print(f"    {RED}⚠  {alias:<12}  {issue}{RESET}")


def _print_failed_services_summary(ok: list[AuditReport]) -> None:
    failed_units = [
        (report["alias"], item["unit"]) for report in ok for item in report["services"]["failed"]
    ]
    if not failed_units:
        return
    print(f"\n  {RED}{BOLD}Failed systemd units:{RESET}")
    for alias, unit in failed_units:
        print(f"    {RED}✗  {alias:<12}  {unit}{RESET}")


def _collect_resource_warnings(ok: list[AuditReport]) -> list[tuple[str, str]]:
    warnings: list[tuple[str, str]] = []
    for report in ok:
        ram_pct = _as_float(report["hardware"].get("ram_used_pct", 0.0))
        if ram_pct > RAM_WARN_THRESHOLD:
            warnings.append((report["alias"], f"RAM usage {ram_pct:.0f}%"))
        for partition in report["disk"]["partitions"]:
            try:
                pct_val = float(partition["pct"].rstrip("%"))
            except ValueError:
                pct_val = 0
            if pct_val > DISK_WARN_THRESHOLD:
                warnings.append((report["alias"], f"Disk {partition['mountpoint']} {pct_val:.0f}%"))
        for gpu in report["gpu"]:
            mem_tot = _as_int(gpu["gpu_mem_total"])
            mem_used = _as_int(gpu["gpu_mem_used"])
            if mem_tot and mem_used / mem_tot > VRAM_WARN_THRESHOLD:
                pct = round(mem_used / mem_tot * 100, 1)
                warnings.append((report["alias"], f"VRAM {pct:.0f}%"))
            temp = _as_float(gpu["gpu_temp"])
            if temp > YELLOW_THRESHOLD:
                warnings.append((report["alias"], f"GPU temp {temp:.0f}°C"))
    return warnings


def _print_resource_warnings_summary(ok: list[AuditReport]) -> None:
    warnings = _collect_resource_warnings(ok)
    if not warnings:
        print(f"\n    {GREEN}✓  No resource overload detected{RESET}")
        return
    print(f"\n  {YELLOW}{BOLD}Resource warnings:{RESET}")
    for alias, message in warnings:
        print(f"    {YELLOW}⚠  {alias:<12}  {message}{RESET}")


def _build_parser() -> argparse.ArgumentParser:
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
    return parser


def _export_json(args: argparse.Namespace, final_results: list[AuditReport]) -> None:
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")

    def _clean(obj: object) -> object:
        if isinstance(obj, str):
            return ansi_pattern.sub("", obj)
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
        "nodes": [_clean(result) for result in final_results],
    }
    json_str = json.dumps(payload, indent=JSON_INDENT, ensure_ascii=False)
    if args.json == "-":
        print(json_str)
        return
    with open(args.json, "w", encoding="utf-8") as fh:
        fh.write(json_str)
    print(f"\n{GREEN}JSON written → {args.json}{RESET}")


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

    _print_node_intro(r)
    if _should_print(all_sec, selected_sections, "hardware"):
        _print_hardware_section(r)
    if _should_print(all_sec, selected_sections, "gpu"):
        _print_gpu_section(r)
    if _should_print(all_sec, selected_sections, "disk"):
        _print_disk_section(r)
    if _should_print(all_sec, selected_sections, "network"):
        _print_network_section(r)
    if _should_print(all_sec, selected_sections, "docker"):
        _print_docker_section(r)
    if _should_print(all_sec, selected_sections, "services"):
        _print_services_section(r)
    if _should_print(all_sec, selected_sections, "firewall"):
        _print_firewall_section(r)
    if _should_print(all_sec, selected_sections, "security"):
        _print_security_section(r)
    if _should_print(all_sec, selected_sections, "processes"):
        _print_processes_section(r)


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

    _print_connectivity_summary(ok, err, total)
    _print_os_summary(ok)
    _print_hardware_summary(ok)
    _print_docker_summary(ok)
    _print_network_summary(ok)
    _print_security_summary(ok)
    _print_failed_services_summary(ok)
    _print_resource_warnings_summary(ok)

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
    parser = _build_parser()
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
                ram_color = GREEN if ram < OK_RAM_THRESHOLD else RED
                print(
                    f"  {GREEN}[ OK]{RESET} {alias:<12}{gpu_tag}  "
                    f"RAM {ram_color}{ram:.0f}%{RESET}  "
                    f"containers: {ctrs}"
                )

    final_results = [r for r in results if r is not None]

    for r in final_results:
        print_node_report(r, sections=args.sections)

    if not args.no_summary:
        print_cluster_summary(final_results)

    if args.json:
        _export_json(args, final_results)


if __name__ == "__main__":
    main()
