"""Tests for internalcmdb.workers.registry."""

from __future__ import annotations

from internalcmdb.workers.registry import BASE, SCRIPTS, ScriptDef


def test_scripts_registry_nonempty() -> None:
    assert len(SCRIPTS) >= 10
    assert "ssh_connectivity_check" in SCRIPTS
    assert "taxonomy_seed" in SCRIPTS


def test_script_def_fields() -> None:
    s = SCRIPTS["ssh_connectivity_check"]
    assert isinstance(s, ScriptDef)
    assert s.category == "discovery"
    assert (BASE / s.script_path).name == "test_cluster_ssh.py"


def test_destructive_flag() -> None:
    assert SCRIPTS["cleanup_stale_services"].is_destructive is True
