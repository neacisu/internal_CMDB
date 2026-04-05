from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_full import (
    GPU_FIELD_MAP,
    HARDWARE_KEYS,
    SYSTEM_KEYS,
    _as_float,
    _as_int,
    _empty_gpu_info,
    _empty_report,
    _kb_to_gb,
    _parse_disk_line,
    _parse_network_line,
    _parse_prefixed_assignment,
    _set_gpu_field,
)


# ---------------------------------------------------------------------------
# _as_int  /  _as_float
# ---------------------------------------------------------------------------


def test_as_int_from_string() -> None:
    assert _as_int("42") == 42


def test_as_int_from_float() -> None:
    assert _as_int(3.9) == 3


def test_as_int_invalid_returns_zero() -> None:
    assert _as_int("not-a-number") == 0


def test_as_int_none_returns_zero() -> None:
    assert _as_int(None) == 0  # type: ignore[arg-type]


def test_as_float_from_string() -> None:
    assert _as_float("3.14") == pytest.approx(3.14)


def test_as_float_from_int() -> None:
    assert _as_float(5) == 5.0


def test_as_float_invalid_returns_zero() -> None:
    assert _as_float("nan-value") == 0.0


# ---------------------------------------------------------------------------
# _kb_to_gb
# ---------------------------------------------------------------------------


def test_kb_to_gb_basic() -> None:
    assert _kb_to_gb("1048576") == pytest.approx(1.0)


def test_kb_to_gb_invalid_returns_zero() -> None:
    assert _kb_to_gb("") == 0.0
    assert _kb_to_gb("abc") == 0.0


def test_kb_to_gb_zero() -> None:
    assert _kb_to_gb("0") == 0.0


# ---------------------------------------------------------------------------
# _parse_prefixed_assignment
# ---------------------------------------------------------------------------


def test_parse_prefixed_assignment_matches_key() -> None:
    target: dict[str, str] = {}
    result = _parse_prefixed_assignment(target, "HOSTNAME=myserver", SYSTEM_KEYS)
    assert result is True
    assert target["hostname"] == "myserver"


def test_parse_prefixed_assignment_no_match() -> None:
    target: dict[str, str] = {}
    result = _parse_prefixed_assignment(target, "UNKNOWN=value", SYSTEM_KEYS)
    assert result is False
    assert target == {}


def test_parse_prefixed_assignment_hardware_keys() -> None:
    target: dict[str, str] = {}
    result = _parse_prefixed_assignment(target, "CPU_MODEL=Intel Core i9", HARDWARE_KEYS)
    assert result is True
    assert target["cpu_model"] == "Intel Core i9"


# ---------------------------------------------------------------------------
# _empty_report structure
# ---------------------------------------------------------------------------


def test_empty_report_structure() -> None:
    r = _empty_report("hz.62", "1.2.3.4")
    assert r["alias"] == "hz.62"
    assert r["pub_ip"] == "1.2.3.4"
    assert r["error"] is None
    assert "system" in r
    assert "hardware" in r
    assert "gpu" in r
    assert "disk" in r
    assert "network" in r
    assert "docker" in r
    assert "services" in r
    assert "firewall" in r
    assert "security" in r
    assert "processes" in r


def test_empty_report_with_error() -> None:
    r = _empty_report("hz.99", "9.9.9.9", "timeout")
    assert r["error"] == "timeout"


def test_empty_report_docker_present_default() -> None:
    r = _empty_report("n", "1.1.1.1")
    assert r["docker"]["present"] is True


def test_empty_report_docker_present_false() -> None:
    r = _empty_report("n", "1.1.1.1", docker_present=False)
    assert r["docker"]["present"] is False


# ---------------------------------------------------------------------------
# _empty_gpu_info
# ---------------------------------------------------------------------------


def test_empty_gpu_info_has_all_fields() -> None:
    gpu = _empty_gpu_info()
    for field in GPU_FIELD_MAP.values():
        assert field in gpu


def test_empty_gpu_info_numeric_defaults_are_zero_string() -> None:
    gpu = _empty_gpu_info()
    assert gpu["gpu_mem_total"] == "0"
    assert gpu["gpu_util"] == "0"


# ---------------------------------------------------------------------------
# _set_gpu_field
# ---------------------------------------------------------------------------


def test_set_gpu_field_sets_known_field() -> None:
    gpu = _empty_gpu_info()
    _set_gpu_field(gpu, "GPU_NAME", "NVIDIA A100")
    assert gpu["gpu_name"] == "NVIDIA A100"


def test_set_gpu_field_ignores_unknown_field() -> None:
    gpu = _empty_gpu_info()
    _set_gpu_field(gpu, "GPU_UNKNOWN_FIELD", "value")
    assert "gpu_unknown_field" not in gpu


# ---------------------------------------------------------------------------
# _parse_disk_line
# ---------------------------------------------------------------------------


def test_parse_disk_line_df_entry() -> None:
    r = _empty_report("n", "1.1.1.1")
    line = "DF|ext4|102400|51200|51200|50%|/"
    _parse_disk_line(r, line)
    parts = r["disk"]["partitions"]
    assert len(parts) == 1
    assert parts[0]["fs"] == "ext4"
    assert parts[0]["mountpoint"] == "/"
    assert parts[0]["pct"] == "50%"


def test_parse_disk_line_blk_entry() -> None:
    r = _empty_report("n", "1.1.1.1")
    line = "BLK|sda|500G|0|disk|Samsung SSD"
    _parse_disk_line(r, line)
    devs = r["disk"]["block_devs"]
    assert len(devs) == 1
    assert devs[0]["name"] == "sda"
    assert devs[0]["rotational"] is False
    assert devs[0]["model"] == "Samsung SSD"


def test_parse_disk_line_blk_rotational_true() -> None:
    r = _empty_report("n", "1.1.1.1")
    line = "BLK|hda|1T|1|disk|WD HDD"
    _parse_disk_line(r, line)
    assert r["disk"]["block_devs"][0]["rotational"] is True


def test_parse_disk_line_insufficient_parts_ignored() -> None:
    r = _empty_report("n", "1.1.1.1")
    _parse_disk_line(r, "DF|ext4|1024")
    assert r["disk"]["partitions"] == []


# ---------------------------------------------------------------------------
# _parse_network_line
# ---------------------------------------------------------------------------


def test_parse_network_line_iface() -> None:
    r = _empty_report("n", "1.1.1.1")
    _parse_network_line(r, "IFACE|eth0|UP|192.168.1.1/24 10.0.0.1/8")
    ifaces = r["network"]["interfaces"]
    assert len(ifaces) == 1
    assert ifaces[0]["name"] == "eth0"
    assert ifaces[0]["state"] == "UP"
    assert "192.168.1.1/24" in ifaces[0]["addrs"]


def test_parse_network_line_vlanid() -> None:
    r = _empty_report("n", "1.1.1.1")
    _parse_network_line(r, "VLANID|4000")
    assert r["network"]["vlan_ids"] == ["4000"]


def test_parse_network_line_route() -> None:
    r = _empty_report("n", "1.1.1.1")
    _parse_network_line(r, "ROUTE|default via 10.0.0.1")
    assert r["network"]["routes"] == ["default via 10.0.0.1"]


def test_parse_network_line_dns() -> None:
    r = _empty_report("n", "1.1.1.1")
    _parse_network_line(r, "DNS_RESOLV=8.8.8.8")
    assert r["network"]["dns"] == "8.8.8.8"


# ---------------------------------------------------------------------------
# _parse_metadata_line (system section)
# ---------------------------------------------------------------------------


def test_parse_metadata_line_matches_hostname() -> None:
    r = _empty_report("n", "1.1.1.1")
    consumed = _parse_prefixed_assignment(r["system"], "HOSTNAME=testhost", SYSTEM_KEYS)
    assert consumed is True
    assert r["system"]["hostname"] == "testhost"


def test_parse_metadata_line_matches_kernel() -> None:
    r = _empty_report("n", "1.1.1.1")
    consumed = _parse_prefixed_assignment(r["system"], "KERNEL=5.15.0-generic", SYSTEM_KEYS)
    assert consumed is True
    assert r["system"]["kernel"] == "5.15.0-generic"
