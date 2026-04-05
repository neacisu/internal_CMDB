from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_runtime_posture import (
    DEFAULT_HOSTS,
    RESULT_TYPE,
    HostAuditResult,
    _apply_section_line,
    _parse_docker_state_line,
    _parse_kv_preamble,
    _parse_record_line,
    parse_output,
)


# ---------------------------------------------------------------------------
# _parse_kv_preamble
# ---------------------------------------------------------------------------


def test_parse_kv_preamble_host() -> None:
    data: dict = {}
    assert _parse_kv_preamble("HOST=myserver", data) is True
    assert data["host"] == "myserver"


def test_parse_kv_preamble_date_utc() -> None:
    data: dict = {}
    assert _parse_kv_preamble("DATE_UTC=2024-06-15T10:00:00Z", data) is True
    assert data["date_utc"] == "2024-06-15T10:00:00Z"


def test_parse_kv_preamble_os() -> None:
    data: dict = {}
    assert _parse_kv_preamble("OS=Ubuntu 22.04 LTS", data) is True
    assert data["os"] == "Ubuntu 22.04 LTS"


def test_parse_kv_preamble_kernel() -> None:
    data: dict = {}
    assert _parse_kv_preamble("KERNEL=5.15.0-generic", data) is True
    assert data["kernel"] == "5.15.0-generic"


def test_parse_kv_preamble_no_match() -> None:
    data: dict = {}
    assert _parse_kv_preamble("RANDOM=value", data) is False
    assert data == {}


# ---------------------------------------------------------------------------
# _parse_docker_state_line
# ---------------------------------------------------------------------------


def test_parse_docker_state_present_yes() -> None:
    data: dict = {}
    assert _parse_docker_state_line("DOCKER_PRESENT=yes", data) is True
    assert data["docker_present"] is True


def test_parse_docker_state_present_no() -> None:
    data: dict = {}
    assert _parse_docker_state_line("DOCKER_PRESENT=no", data) is True
    assert data["docker_present"] is False


def test_parse_docker_state_server_version() -> None:
    data: dict = {}
    assert _parse_docker_state_line("SERVER=24.0.5", data) is True
    assert data["docker_server"] == "24.0.5"


def test_parse_docker_state_no_match() -> None:
    data: dict = {}
    assert _parse_docker_state_line("CONTAINER|foo|bar|running", data) is False


# ---------------------------------------------------------------------------
# _parse_record_line
# ---------------------------------------------------------------------------


def test_parse_record_line_path_present() -> None:
    data: dict = {"paths": [], "containers": [], "containers_all": [], "images": []}
    line = "PATH|/mnt/HC_Volume_105014654|present|drwxr-xr-x|root|root"
    assert _parse_record_line(line, data) is True
    assert len(data["paths"]) == 1
    assert data["paths"][0]["path"] == "/mnt/HC_Volume_105014654"
    assert data["paths"][0]["state"] == "present"


def test_parse_record_line_path_missing() -> None:
    data: dict = {"paths": [], "containers": [], "containers_all": [], "images": []}
    line = "PATH|/some/missing/path|missing|-"
    assert _parse_record_line(line, data) is True
    assert data["paths"][0]["state"] == "missing"


def test_parse_record_line_container() -> None:
    data: dict = {"paths": [], "containers": [], "containers_all": [], "images": []}
    line = "CONTAINER|internalcmdb|ghcr.io/org/app:latest|Up 2 hours"
    assert _parse_record_line(line, data) is True
    assert len(data["containers"]) == 1
    assert data["containers"][0]["name"] == "internalcmdb"


def test_parse_record_line_image() -> None:
    data: dict = {"paths": [], "containers": [], "containers_all": [], "images": []}
    line = "IMAGE|ghcr.io/org/app:latest|abc123"
    assert _parse_record_line(line, data) is True
    assert len(data["images"]) == 1
    assert data["images"][0]["id"] == "abc123"


def test_parse_record_line_no_match() -> None:
    data: dict = {"paths": [], "containers": [], "containers_all": [], "images": []}
    assert _parse_record_line("RANDOM line with no prefix", data) is False


# ---------------------------------------------------------------------------
# _apply_section_line
# ---------------------------------------------------------------------------


def test_apply_section_line_systemd_timer() -> None:
    data: dict = {"systemd_timers": [], "systemd_units": [], "indicators": []}
    cron_data: dict = {}
    _apply_section_line("backup.timer", "=== SYSTEMD_TIMERS ===", data, cron_data, "")
    assert "backup.timer" in data["systemd_timers"]


def test_apply_section_line_systemd_unit() -> None:
    data: dict = {"systemd_timers": [], "systemd_units": [], "indicators": []}
    cron_data: dict = {}
    _apply_section_line("postgres.service", "=== SYSTEMD_UNITS ===", data, cron_data, "")
    assert "postgres.service" in data["systemd_units"]


def test_apply_section_line_cron_entry() -> None:
    data: dict = {"systemd_timers": [], "systemd_units": [], "indicators": []}
    cron_data: dict = {"/etc/crontab": []}
    _apply_section_line("0 2 * * * pg_dump", "=== CRON ===", data, cron_data, "/etc/crontab")
    assert "0 2 * * * pg_dump" in cron_data["/etc/crontab"]


def test_apply_section_line_indicator() -> None:
    data: dict = {"systemd_timers": [], "systemd_units": [], "indicators": []}
    cron_data: dict = {}
    _apply_section_line("ollama serve", "=== INDICATORS ===", data, cron_data, "")
    assert "ollama serve" in data["indicators"]


# ---------------------------------------------------------------------------
# parse_output (integrare)
# ---------------------------------------------------------------------------


def test_parse_output_full_sample() -> None:
    raw = "\n".join(
        [
            "HOST=testnode",
            "DATE_UTC=2024-06-15T10:00:00Z",
            "OS=Ubuntu 22.04",
            "KERNEL=5.15.0",
            "=== PATHS ===",
            "PATH|/mnt/HC_Volume_105014654|present|drwxr-xr-x|root|root",
            "PATH|/etc/traefik|missing|-",
            "=== DOCKER ===",
            "DOCKER_PRESENT=yes",
            "SERVER=24.0.5",
            "CONTAINER|myapp|myimage:latest|Up 3 hours",
            "IMAGE|myimage:latest|sha256abc",
            "=== SYSTEMD_TIMERS ===",
            "backup.timer  active",
            "=== INDICATORS ===",
            "ollama serve running",
            "=== END ===",
        ]
    )
    result = parse_output(raw)
    assert result["host"] == "testnode"
    assert result["kernel"] == "5.15.0"
    assert result["docker_present"] is True
    assert result["docker_server"] == "24.0.5"
    assert len(result["paths"]) == 2
    assert len(result["containers"]) == 1
    assert result["containers"][0]["name"] == "myapp"
    assert len(result["images"]) == 1
    assert "backup.timer  active" in result["systemd_timers"]
    assert "ollama serve running" in result["indicators"]


def test_parse_output_empty_raw() -> None:
    result = parse_output("")
    assert result["host"] == ""
    assert result["containers"] == []
    assert result["paths"] == []


# ---------------------------------------------------------------------------
# HostAuditResult dataclass
# ---------------------------------------------------------------------------


def test_host_audit_result_ok() -> None:
    r = HostAuditResult(alias="orchestrator", ok=True, error=None, data={"host": "orch"})
    assert r.ok is True
    assert r.error is None
    assert r.data["host"] == "orch"


def test_host_audit_result_failure() -> None:
    r = HostAuditResult(alias="hz.62", ok=False, error="timeout", data={})
    assert r.ok is False
    assert r.error == "timeout"


# ---------------------------------------------------------------------------
# DEFAULT_HOSTS / RESULT_TYPE constants
# ---------------------------------------------------------------------------


def test_default_hosts_non_empty() -> None:
    assert len(DEFAULT_HOSTS) > 0
    assert "orchestrator" in DEFAULT_HOSTS


def test_result_type_constant() -> None:
    assert RESULT_TYPE == "runtime_posture"
