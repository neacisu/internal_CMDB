"""ShellCheck and structural validation tests for bash deploy scripts.

These tests verify that:
  1. shellcheck passes cleanly (severity <= 1, i.e. only style hints allowed)
  2. Key structural invariants hold (SSH argument patterns, required functions)
  3. All HOST_SSH and HOST_CONFIG keys are in sync with each other
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parents[3] / "scripts"
DEPLOY_AGENT = SCRIPTS_DIR / "deploy_agent.sh"
DISTRIBUTE_CONFIGS = SCRIPTS_DIR / "distribute_configs.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_shellcheck(script: Path, severity: str = "warning") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["shellcheck", f"--severity={severity}", "--format=json", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# deploy_agent.sh
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck not installed")
def test_deploy_agent_passes_shellcheck():
    result = _run_shellcheck(DEPLOY_AGENT)
    assert result.returncode == 0, (
        f"shellcheck found issues in {DEPLOY_AGENT.name}:\n{result.stdout}"
    )


def test_deploy_agent_verify_api_reachable_function_exists():
    content = DEPLOY_AGENT.read_text()
    assert "verify_api_reachable()" in content, (
        "verify_api_reachable() must exist (SC2034 fix: api_url must be used)"
    )


def test_deploy_agent_api_url_is_used_in_function_call():
    content = DEPLOY_AGENT.read_text()
    assert 'verify_api_reachable "$api_url"' in content, (
        "api_url must be passed to verify_api_reachable to satisfy SC2034"
    )


def test_deploy_agent_no_double_quoted_ssh_shell_strings_with_dollar_vars():
    """SC2029: ssh host \"... $var ...\" pattern must not appear after our fix."""
    content = DEPLOY_AGENT.read_text()
    # Pattern: ssh <expr> "<literal>...$VARIABLE..." — the problematic form
    # We check for the specific vars that were flagged: $REMOTE_AGENT_DIR, $py_bin, $host_code
    sc2029_patterns = [
        r'ssh\s+"\$ssh_host"\s+"[^"]*\$REMOTE_AGENT_DIR',
        r'ssh\s+"\$ssh_host"\s+"[^"]*\$REMOTE_CONFIG_DIR',
        r'ssh\s+"\$ssh_host"\s+"[^"]*\$py_bin',
        r'ssh\s+"\$ssh_host"\s+"[^"]*\$host_code',
    ]
    for pattern in sc2029_patterns:
        assert not re.search(pattern, content), (
            f"SC2029 pattern still present: {pattern}"
        )


def test_deploy_agent_uses_heredoc_for_remote_install():
    content = DEPLOY_AGENT.read_text()
    assert "bash -s --" in content, (
        "Remote httpx install must use 'bash -s -- $py_bin' heredoc pattern"
    )
    assert "<< 'REMOTE_INSTALL'" in content, (
        "Single-quoted heredoc delimiter required to avoid SC2087"
    )


def test_deploy_agent_echo_runs_locally_not_in_ssh():
    content = DEPLOY_AGENT.read_text()
    # The echo for agent running status must NOT be inside an ssh "..." string
    assert 'echo "  ✓ Agent running on ${host_code}"' in content, (
        "Agent status echo must run locally (not inside an SSH shell string)"
    )


def test_deploy_agent_host_ssh_and_host_config_keys_match():
    content = DEPLOY_AGENT.read_text()
    # Extract HOST_SSH keys
    ssh_block = re.search(r"declare -A HOST_SSH=\((.+?)\)", content, re.DOTALL)
    cfg_block = re.search(r"declare -A HOST_CONFIG=\((.+?)\)", content, re.DOTALL)
    assert ssh_block and cfg_block, "HOST_SSH and HOST_CONFIG must both be declared"

    def _extract_keys(block: str) -> set[str]:
        return set(re.findall(r"\[(\S+?)\]", block))

    ssh_keys = _extract_keys(ssh_block.group(1))
    cfg_keys = _extract_keys(cfg_block.group(1))
    assert ssh_keys == cfg_keys, (
        f"HOST_SSH and HOST_CONFIG key sets diverged.\n"
        f"  Only in SSH : {ssh_keys - cfg_keys}\n"
        f"  Only in CFG : {cfg_keys - ssh_keys}"
    )


def test_deploy_agent_hz118_lxc_entries_present():
    content = DEPLOY_AGENT.read_text()
    for expected in [
        "lxc-hz118-traktors",
        "lxc-hz118-tecdocnode",
        "lxc-hz118-tecdocmysql",
        "lxc-hz118-mediserver2",
    ]:
        assert expected in content, f"Missing hz.118 LXC entry: {expected}"


# ---------------------------------------------------------------------------
# distribute_configs.sh
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck not installed")
def test_distribute_configs_passes_shellcheck():
    result = _run_shellcheck(DISTRIBUTE_CONFIGS)
    assert result.returncode == 0, (
        f"shellcheck found issues in {DISTRIBUTE_CONFIGS.name}:\n{result.stdout}"
    )


def test_distribute_configs_sha256sum_uses_arg_form():
    content = DISTRIBUTE_CONFIGS.read_text()
    # Old pattern: ssh host "sha256sum $REMOTE_CONFIG ..."
    assert 'sha256sum -- "$REMOTE_CONFIG"' in content, (
        "sha256sum must use arg form 'sha256sum -- \"$REMOTE_CONFIG\"' to avoid SC2029"
    )
    # Old shell-string form must not appear
    assert '"sha256sum $REMOTE_CONFIG' not in content


def test_distribute_configs_awk_runs_locally():
    content = DISTRIBUTE_CONFIGS.read_text()
    # awk should appear AFTER the ssh command (i.e., local pipe), not inside quotes
    ssh_sha_line = next(
        (ln for ln in content.splitlines() if "sha256sum" in ln and "ssh" in ln), None
    )
    assert ssh_sha_line is not None
    # The awk call must be outside the ssh invocation
    assert "awk" not in ssh_sha_line, (
        "awk must run locally (piped on client side), not inside the ssh command"
    )


def test_distribute_configs_cp_backup_uses_arg_form():
    content = DISTRIBUTE_CONFIGS.read_text()
    assert 'cp -- "$REMOTE_CONFIG" "${REMOTE_CONFIG}.bak"' in content, (
        "cp backup must use arg form to avoid SC2029"
    )
    assert '"cp $REMOTE_CONFIG' not in content
