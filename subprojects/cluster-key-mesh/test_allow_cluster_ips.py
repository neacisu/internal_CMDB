from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from allow_cluster_ips import (
    ADD_MARKER,
    CLUSTER,
    ERROR_MARKER,
    SKIP_MARKER,
    allow_iptables,
    allow_ufw,
    detect_firewall,
    process_node,
)


# ---------------------------------------------------------------------------
# detect_firewall
# ---------------------------------------------------------------------------


def test_detect_firewall_returns_ufw_when_active() -> None:
    with patch("allow_cluster_ips.ssh", return_value=(0, "Status: active", "")):
        result = detect_firewall("hz.62")
    assert result == "ufw"


def test_detect_firewall_returns_iptables_when_ufw_not_active() -> None:
    # "disabled" nu conține "active" ca substring, spre deosebire de "inactive"
    with patch("allow_cluster_ips.ssh", return_value=(0, "Status: disabled", "")):
        result = detect_firewall("hz.62")
    assert result == "iptables"


def test_detect_firewall_returns_iptables_when_ssh_fails() -> None:
    with patch("allow_cluster_ips.ssh", return_value=(1, "", "command not found")):
        result = detect_firewall("hz.113")
    assert result == "iptables"


def test_detect_firewall_returns_iptables_on_empty_output() -> None:
    with patch("allow_cluster_ips.ssh", return_value=(0, "", "")):
        result = detect_firewall("hz.118")
    assert result == "iptables"


# ---------------------------------------------------------------------------
# allow_ufw
# ---------------------------------------------------------------------------


def test_allow_ufw_skips_existing_rule() -> None:
    # Simulăm că regula există deja
    with patch("allow_cluster_ips.ssh", return_value=(0, "EXISTS", "")):
        logs = allow_ufw("hz.62", ["10.0.0.1"])
    assert len(logs) == 1
    assert SKIP_MARKER in logs[0]
    assert "10.0.0.1" in logs[0]


def test_allow_ufw_adds_missing_rule() -> None:
    # Prima apelare check → MISSING, a doua apelare → succes
    responses = [(0, "MISSING", ""), (0, "UFW_OK", "")]
    with patch("allow_cluster_ips.ssh", side_effect=responses):
        logs = allow_ufw("hz.62", ["10.0.0.2"])
    assert len(logs) == 1
    assert ADD_MARKER in logs[0]
    assert "10.0.0.2" in logs[0]


def test_allow_ufw_records_error_on_failure() -> None:
    responses = [(0, "MISSING", ""), (1, "", "permission denied")]
    with patch("allow_cluster_ips.ssh", side_effect=responses):
        logs = allow_ufw("hz.62", ["10.0.0.3"])
    assert len(logs) == 1
    assert ERROR_MARKER in logs[0]


def test_allow_ufw_multiple_ips() -> None:
    ips = ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
    # Toate există deja
    with patch("allow_cluster_ips.ssh", return_value=(0, "EXISTS", "")):
        logs = allow_ufw("hz.62", ips)
    assert len(logs) == 3
    assert all(SKIP_MARKER in log for log in logs)


# ---------------------------------------------------------------------------
# allow_iptables
# ---------------------------------------------------------------------------


def test_allow_iptables_skips_existing_rule() -> None:
    # rc_check == 0 → regula există deja pentru ambele chain-uri
    with patch("allow_cluster_ips.ssh", return_value=(0, "", "")):
        logs = allow_iptables("hz.62", ["10.0.0.1"])
    # 2 chain-uri (INPUT + OUTPUT) → 2 SKIP-uri
    assert len(logs) == 2
    assert all(SKIP_MARKER in log for log in logs)


def test_allow_iptables_adds_when_missing() -> None:
    # rc_check != 0 → regulă lipsă; insert succes
    responses = [(1, "", ""), (0, "", "")]  # check miss + insert ok, pentru INPUT
    responses += [(1, "", ""), (0, "", "")]  # check miss + insert ok, pentru OUTPUT
    with patch("allow_cluster_ips.ssh", side_effect=responses):
        logs = allow_iptables("hz.62", ["10.0.0.4"])
    assert len(logs) == 2
    assert all(ADD_MARKER in log for log in logs)


def test_allow_iptables_records_error_on_insert_failure() -> None:
    responses = [(1, "", ""), (1, "", "iptables error")]  # check miss + insert fail
    responses += [(1, "", ""), (0, "", "")]  # OUTPUT ok
    with patch("allow_cluster_ips.ssh", side_effect=responses):
        logs = allow_iptables("hz.62", ["10.0.0.5"])
    error_logs = [log for log in logs if ERROR_MARKER in log]
    assert len(error_logs) >= 1


# ---------------------------------------------------------------------------
# process_node
# ---------------------------------------------------------------------------


def test_process_node_uses_ufw_when_active() -> None:
    with (
        patch("allow_cluster_ips.detect_firewall", return_value="ufw"),
        patch("allow_cluster_ips.allow_ufw", return_value=["  [SKIP] 10.0.0.1 already in ufw"]),
    ):
        alias, fw, logs = process_node("hz.62", ["10.0.0.1"])
    assert alias == "hz.62"
    assert fw == "ufw"
    assert len(logs) == 1


def test_process_node_uses_iptables_when_not_ufw() -> None:
    with (
        patch("allow_cluster_ips.detect_firewall", return_value="iptables"),
        patch(
            "allow_cluster_ips.allow_iptables",
            return_value=["  [ADD ] iptables -I INPUT 1 -s 10.0.0.1 -j ACCEPT"],
        ),
    ):
        alias, fw, logs = process_node("hz.113", ["10.0.0.1"])
    assert fw == "iptables"
    assert ADD_MARKER in logs[0]


# ---------------------------------------------------------------------------
# CLUSTER constant
# ---------------------------------------------------------------------------


def test_cluster_has_expected_nodes() -> None:
    aliases = [a for a, _ in CLUSTER]
    assert "hz.62" in aliases
    assert "hz.113" in aliases
    assert len(CLUSTER) == 9


def test_cluster_ips_are_valid_format() -> None:
    import re

    ip_pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    for alias, ip in CLUSTER:
        assert ip_pattern.match(ip), f"IP invalid pentru {alias}: {ip}"
