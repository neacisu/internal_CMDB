from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_trust_surface import (
    DEFAULT_ENDPOINTS,
    DEFAULT_HOSTS,
    RESULT_TYPE,
    HostTrustResult,
    _SSHDIR_PARTS_FULL,
    _SSHDIR_PARTS_PARTIAL,
    parse_remote,
)


# ---------------------------------------------------------------------------
# parse_remote — structură de bază
# ---------------------------------------------------------------------------


def test_parse_remote_empty_string() -> None:
    result = parse_remote("")
    assert result["host"] == ""
    assert result["sshd"] == []
    assert result["ssh_dirs"] == []
    assert result["secret_paths"] == []
    assert result["certs"] == []


def test_parse_remote_extracts_host() -> None:
    raw = "HOST=myserver\n=== SSHD ===\n=== END ==="
    result = parse_remote(raw)
    assert result["host"] == "myserver"


def test_parse_remote_sshd_section() -> None:
    raw = "\n".join(
        [
            "HOST=testnode",
            "=== SSHD ===",
            "permitrootlogin no",
            "passwordauthentication no",
            "pubkeyauthentication yes",
            "port 22",
            "=== SSH_KEYS ===",
            "=== END ===",
        ]
    )
    result = parse_remote(raw)
    assert "permitrootlogin no" in result["sshd"]
    assert "passwordauthentication no" in result["sshd"]
    assert "port 22" in result["sshd"]


def test_parse_remote_sshdir_full_format() -> None:
    # Formatul real din script: SSHDIR|<dir>|<perms>|<count>
    # stat -c '%A|%U|%G' produce "drwx------|root|root" deci split("|", 3) dă:
    # [0]=SSHDIR [1]=/root/.ssh [2]=drwx------ [3]=root|authorized_keys_lines=3
    raw = "\n".join(
        [
            "HOST=node",
            "=== SSH_KEYS ===",
            "SSHDIR|/root/.ssh|drwx------|root|authorized_keys_lines=3",
            "=== END ===",
        ]
    )
    result = parse_remote(raw)
    assert len(result["ssh_dirs"]) == 1
    entry = result["ssh_dirs"][0]
    assert entry["path"] == "/root/.ssh"
    assert entry["perms"] == "drwx------"
    # count preia tot restul după al 3-lea pipe
    assert "authorized_keys_lines=3" in entry["count"]


def test_parse_remote_sshdir_partial_format() -> None:
    """Câmpul count este absent → fallback la valoarea implicită."""
    raw = "\n".join(
        [
            "HOST=node",
            "=== SSH_KEYS ===",
            "SSHDIR|/home/user/.ssh|drwx------",
            "=== END ===",
        ]
    )
    result = parse_remote(raw)
    assert len(result["ssh_dirs"]) == 1
    assert result["ssh_dirs"][0]["count"] == "authorized_keys_lines=unknown"


def test_parse_remote_secret_paths() -> None:
    raw = "\n".join(
        [
            "HOST=node",
            "=== SECRET_PATHS ===",
            "SECRETPATH|/etc/ssl/private/cert.key|-rw------|root",
            "=== END ===",
        ]
    )
    result = parse_remote(raw)
    assert len(result["secret_paths"]) == 1
    assert result["secret_paths"][0]["path"] == "/etc/ssl/private/cert.key"
    assert result["secret_paths"][0]["perms"] == "-rw------|root"


def test_parse_remote_certs() -> None:
    raw = "\n".join(
        [
            "HOST=node",
            "=== CERTS ===",
            "CERT|/etc/letsencrypt/live/example.com/cert.pem|subject=...|issuer=...|notAfter=...",
            "=== END ===",
        ]
    )
    result = parse_remote(raw)
    assert len(result["certs"]) == 1
    assert result["certs"][0]["path"] == "/etc/letsencrypt/live/example.com/cert.pem"


def test_parse_remote_multiple_sections() -> None:
    raw = "\n".join(
        [
            "HOST=multinode",
            "=== SSHD ===",
            "permitrootlogin prohibit-password",
            "=== SSH_KEYS ===",
            "SSHDIR|/root/.ssh|drwx------|root|authorized_keys_lines=1",
            "=== SECRET_PATHS ===",
            "SECRETPATH|/etc/ssl/private/server.pem|-rw-r--r--|root",
            "=== CERTS ===",
            "CERT|/etc/letsencrypt/live/ex.com/fullchain.pem|subject=CN=ex.com|enddate=...",
            "=== END ===",
        ]
    )
    result = parse_remote(raw)
    assert result["host"] == "multinode"
    assert len(result["sshd"]) == 1
    assert len(result["ssh_dirs"]) == 1
    assert len(result["secret_paths"]) == 1
    assert len(result["certs"]) == 1


# ---------------------------------------------------------------------------
# HostTrustResult dataclass
# ---------------------------------------------------------------------------


def test_host_trust_result_ok() -> None:
    r = HostTrustResult(
        alias="orchestrator",
        ok=True,
        error=None,
        data={"host": "orch", "sshd": ["permitrootlogin no"]},
    )
    assert r.ok is True
    assert r.error is None
    assert "sshd" in r.data


def test_host_trust_result_failure() -> None:
    r = HostTrustResult(alias="hz.62", ok=False, error="timeout", data={})
    assert r.ok is False
    assert r.error == "timeout"
    assert r.data == {}


# ---------------------------------------------------------------------------
# Constante
# ---------------------------------------------------------------------------


def test_result_type_constant() -> None:
    assert RESULT_TYPE == "trust_surface"


def test_default_hosts_contains_cluster_nodes() -> None:
    assert "orchestrator" in DEFAULT_HOSTS
    assert "hz.62" in DEFAULT_HOSTS
    assert len(DEFAULT_HOSTS) >= 5


def test_default_endpoints_non_empty() -> None:
    assert len(DEFAULT_ENDPOINTS) > 0
    for ep in DEFAULT_ENDPOINTS:
        assert ":" in ep, f"Endpoint lipsit de port: {ep}"


def test_sshdir_parts_constants() -> None:
    assert _SSHDIR_PARTS_FULL == 4
    assert _SSHDIR_PARTS_PARTIAL == 3


# ---------------------------------------------------------------------------
# audit_host (mock SSH / local runner)
# ---------------------------------------------------------------------------


def test_audit_host_returns_error_on_timeout() -> None:
    import subprocess

    from audit_trust_surface import audit_host

    with (
        patch("audit_trust_surface.is_local_host", return_value=False),
        patch(
            "audit_trust_surface.ssh",
            side_effect=subprocess.TimeoutExpired(cmd="ssh", timeout=35),
        ),
    ):
        result = audit_host("hz.62")
    assert result.ok is False
    assert result.error == "timeout"


def test_audit_host_returns_error_on_nonzero_exit() -> None:
    from audit_trust_surface import audit_host

    with (
        patch("audit_trust_surface.is_local_host", return_value=False),
        patch("audit_trust_surface.ssh", return_value=(1, "", "permission denied")),
    ):
        result = audit_host("hz.113")
    assert result.ok is False
    assert "permission denied" in (result.error or "")


def test_audit_host_succeeds_with_valid_output() -> None:
    from audit_trust_surface import audit_host

    fake_output = "\n".join(
        [
            "HOST=hz113",
            "=== SSHD ===",
            "permitrootlogin no",
            "=== SSH_KEYS ===",
            "=== SECRET_PATHS ===",
            "=== CERTS ===",
            "=== END ===",
        ]
    )
    with (
        patch("audit_trust_surface.is_local_host", return_value=False),
        patch("audit_trust_surface.ssh", return_value=(0, fake_output, "")),
    ):
        result = audit_host("hz.113")
    assert result.ok is True
    assert result.data["host"] == "hz113"
    assert "permitrootlogin no" in result.data["sshd"]
