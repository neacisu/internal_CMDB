from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_cluster import (
    SUMMARY_ERROR,
    SUMMARY_MISSING,
    SUMMARY_OK,
    _append_section_line,
    _build_summary,
    _classify_result,
    _collect_private_subnets,
    _detect_section,
    _empty_result,
    _group_results,
    _parse_metadata_line,
    _update_netplan,
    parse_output,
)


# ---------------------------------------------------------------------------
# _empty_result
# ---------------------------------------------------------------------------


def test_empty_result_structure() -> None:
    r = _empty_result("hz.62", "1.2.3.4")
    assert r["alias"] == "hz.62"
    assert r["pub_ip"] == "1.2.3.4"
    assert r["error"] is None
    assert r["interfaces"] == []
    assert r["private_ips"] == []
    assert r["vlan_ids"] == []
    assert r["routes"] == []
    assert r["netplan"] == {}


def test_empty_result_with_error() -> None:
    r = _empty_result("hz.99", "9.9.9.9", "connection refused")
    assert r["error"] == "connection refused"
    assert r["alias"] == "hz.99"


# ---------------------------------------------------------------------------
# _detect_section
# ---------------------------------------------------------------------------


def test_detect_section_known_markers() -> None:
    assert _detect_section("--- INTERFACES ---") == "iface"
    assert _detect_section("--- VLANS ---") == "vlans"
    assert _detect_section("--- VLAN IDS ---") == "vlan_ids"
    assert _detect_section("--- ROUTES ---") == "routes"
    assert _detect_section("--- NETPLAN ---") == "netplan"
    assert _detect_section("--- PRIVATE IPS ---") == "private"
    assert _detect_section("--- END ---") is None


def test_detect_section_unknown_line() -> None:
    # Linie care nu e un marker de secțiune → întoarce KeyError absent = None implicit dict.get
    result = _detect_section("some random line")
    # _detect_section foloseşte .get() → None pentru linie necunoscută
    assert result is None


# ---------------------------------------------------------------------------
# _parse_metadata_line
# ---------------------------------------------------------------------------


def test_parse_metadata_line_hostname() -> None:
    r = _empty_result("a", "1.1.1.1")
    assert _parse_metadata_line(r, "HOSTNAME=myserver") is True
    assert r["hostname"] == "myserver"


def test_parse_metadata_line_kernel() -> None:
    r = _empty_result("a", "1.1.1.1")
    assert _parse_metadata_line(r, "KERNEL=5.15.0-generic") is True
    assert r["kernel"] == "5.15.0-generic"


def test_parse_metadata_line_os() -> None:
    r = _empty_result("a", "1.1.1.1")
    assert _parse_metadata_line(r, "OS=Ubuntu 22.04 LTS") is True
    assert r["os"] == "Ubuntu 22.04 LTS"


def test_parse_metadata_line_no_match() -> None:
    r = _empty_result("a", "1.1.1.1")
    assert _parse_metadata_line(r, "RANDOM=value") is False


# ---------------------------------------------------------------------------
# _append_section_line
# ---------------------------------------------------------------------------


def test_append_section_line_iface() -> None:
    r = _empty_result("a", "1.1.1.1")
    _append_section_line("iface", "eth0 UP 192.168.1.1/24", r)
    assert r["interfaces"] == ["eth0 UP 192.168.1.1/24"]


def test_append_section_line_vlans_skips_none() -> None:
    r = _empty_result("a", "1.1.1.1")
    _append_section_line("vlans", "(none)", r)
    assert r["vlans"] == []


def test_append_section_line_private_skips_none() -> None:
    r = _empty_result("a", "1.1.1.1")
    _append_section_line("private", "(none)", r)
    assert r["private_ips"] == []


def test_append_section_line_private_adds_ip() -> None:
    r = _empty_result("a", "1.1.1.1")
    _append_section_line("private", "10.0.0.5/24", r)
    assert r["private_ips"] == ["10.0.0.5/24"]


def test_append_section_line_routes() -> None:
    r = _empty_result("a", "1.1.1.1")
    _append_section_line("routes", "default via 10.0.0.1 dev eth0", r)
    assert r["routes"] == ["default via 10.0.0.1 dev eth0"]


def test_append_section_line_vlan_ids_skips_no_vlan_text() -> None:
    r = _empty_result("a", "1.1.1.1")
    _append_section_line("vlan_ids", "(no vlan ids found)", r)
    assert r["vlan_ids"] == []


# ---------------------------------------------------------------------------
# _update_netplan
# ---------------------------------------------------------------------------


def test_update_netplan_file_start() -> None:
    content: dict[str, list[str]] = {}
    result = _update_netplan("FILE:/etc/netplan/00-installer.yaml", None, content)
    assert result == "/etc/netplan/00-installer.yaml"
    assert content["/etc/netplan/00-installer.yaml"] == []


def test_update_netplan_endfile() -> None:
    content: dict[str, list[str]] = {"/etc/netplan/cfg.yaml": []}
    result = _update_netplan("ENDFILE", "/etc/netplan/cfg.yaml", content)
    assert result is None


def test_update_netplan_appends_line() -> None:
    content: dict[str, list[str]] = {"/etc/netplan/cfg.yaml": []}
    _update_netplan("  version: 2", "/etc/netplan/cfg.yaml", content)
    assert "  version: 2" in content["/etc/netplan/cfg.yaml"]


# ---------------------------------------------------------------------------
# parse_output (integrare)
# ---------------------------------------------------------------------------


def test_parse_output_full_sample() -> None:
    raw = "\n".join(
        [
            "HOSTNAME=testnode",
            "KERNEL=5.15.0",
            "OS=Ubuntu 22.04",
            "--- INTERFACES ---",
            "eth0 UP 1.2.3.4/24",
            "--- VLANS ---",
            "(none)",
            "--- VLAN IDS ---",
            "(no vlan ids found)",
            "--- ROUTES ---",
            "default via 1.2.3.1 dev eth0",
            "--- NETPLAN ---",
            "FILE:/etc/netplan/00.yaml",
            "  version: 2",
            "ENDFILE",
            "--- PRIVATE IPS ---",
            "10.10.0.5/24",
            "--- END ---",
        ]
    )
    r = parse_output("hz.62", "1.2.3.4", raw)
    assert r["hostname"] == "testnode"
    assert r["kernel"] == "5.15.0"
    assert r["os"] == "Ubuntu 22.04"
    assert r["interfaces"] == ["eth0 UP 1.2.3.4/24"]
    assert r["vlans"] == []
    assert r["vlan_ids"] == []
    assert r["routes"] == ["default via 1.2.3.1 dev eth0"]
    assert r["private_ips"] == ["10.10.0.5/24"]
    assert "/etc/netplan/00.yaml" in r["netplan"]


# ---------------------------------------------------------------------------
# _classify_result
# ---------------------------------------------------------------------------


def test_classify_result_error() -> None:
    r = _empty_result("a", "1.1.1.1", "some error")
    assert _classify_result(r) == SUMMARY_ERROR


def test_classify_result_ok_with_private_ips() -> None:
    r = _empty_result("a", "1.1.1.1")
    r["private_ips"] = ["10.0.0.1/24"]
    assert _classify_result(r) == SUMMARY_OK


def test_classify_result_ok_with_vlan_ids() -> None:
    r = _empty_result("a", "1.1.1.1")
    r["vlan_ids"] = ["4000"]
    assert _classify_result(r) == SUMMARY_OK


def test_classify_result_missing() -> None:
    r = _empty_result("a", "1.1.1.1")
    assert _classify_result(r) == SUMMARY_MISSING


# ---------------------------------------------------------------------------
# _collect_private_subnets
# ---------------------------------------------------------------------------


def test_collect_private_subnets_groups_correctly() -> None:
    r1 = _empty_result("a", "1.1.1.1")
    r1["private_ips"] = ["10.0.0.5/24", "10.0.0.6/24"]
    r2 = _empty_result("b", "2.2.2.2")
    r2["private_ips"] = ["10.1.2.3/24"]
    subnets = _collect_private_subnets([r1, r2])
    assert "10.0.0.x" in subnets
    assert "10.1.2.x" in subnets


def test_collect_private_subnets_empty() -> None:
    r = _empty_result("a", "1.1.1.1")
    assert _collect_private_subnets([r]) == []


# ---------------------------------------------------------------------------
# _group_results / _build_summary
# ---------------------------------------------------------------------------


def test_group_results_segregates_correctly() -> None:
    ok_r = _empty_result("ok-node", "1.1.1.1")
    ok_r["private_ips"] = ["10.0.0.1/24"]
    err_r = _empty_result("err-node", "2.2.2.2", "timeout")
    miss_r = _empty_result("miss-node", "3.3.3.3")

    has_vswitch, no_vswitch, errors = _group_results([ok_r, err_r, miss_r])
    assert any(alias == "ok-node" for alias, _, _ in has_vswitch)
    assert "miss-node" in no_vswitch
    assert "err-node" in errors


def test_build_summary_keys() -> None:
    r = _empty_result("n", "1.2.3.4")
    summary = _build_summary([r])
    assert "vswitch" in summary
    assert "no_vswitch" in summary
    assert "errors" in summary
    assert "private_subnets" in summary
    assert "vlan_ids" in summary
