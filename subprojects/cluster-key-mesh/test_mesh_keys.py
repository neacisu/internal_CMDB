"""Unit tests for mesh_keys.py pure-logic helpers.

Covers:
  - HZ_215 / HZ_223 constants: cluster and gateway aliases are consistent.
  - SSH option constants: individual strings and composed lists.
  - _merge_authorized_keys: idempotent dedup, ordering, edge cases.
  - _download_and_parse_authorized_keys: local-file parsing (no real SSH).
  - install_keys_on_storagebox: dry-run fast path.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from mesh_keys import (
    HZ_215,
    HZ_223,
    PROXIED_NODES,
    CLUSTER,
    _OPT_BATCH_MODE,
    _OPT_LOG_LEVEL,
    _OPT_STRICT_HOST_KEY_CHECKING,
    _OPT_USER_KNOWN_HOSTS_FILE,
    _SSH_OPTS,
    _SSH_STORAGEBOX_OPTS,
    _download_and_parse_authorized_keys,
    _merge_authorized_keys,
    install_keys_on_storagebox,
    DistributeResult,
    SSH_KEY_MIN_PARTS,
)


# ---------------------------------------------------------------------------
# Gateway alias constants
# ---------------------------------------------------------------------------


class TestGatewayAliasConstants:
    """HZ_215 and HZ_223 must be consistent with CLUSTER and PROXIED_NODES."""

    def test_hz_215_in_cluster(self) -> None:
        cluster_aliases = [alias for alias, _ in CLUSTER]
        assert HZ_215 in cluster_aliases, "HZ_215 must appear as a CLUSTER entry"

    def test_hz_223_in_cluster(self) -> None:
        cluster_aliases = [alias for alias, _ in CLUSTER]
        assert HZ_223 in cluster_aliases, "HZ_223 must appear as a CLUSTER entry"

    def test_hz_215_is_gateway_for_expected_lxcs(self) -> None:
        """neanelu-prod, neanelu-staging, llm-guard, wapp-pro-app all use hz.215."""
        hz215_hosted = [alias for alias, _, gw in PROXIED_NODES if gw == HZ_215]
        assert "neanelu-prod" in hz215_hosted
        assert "neanelu-staging" in hz215_hosted
        assert "llm-guard" in hz215_hosted
        assert "wapp-pro-app" in hz215_hosted

    def test_hz_223_is_gateway_for_expected_lxcs(self) -> None:
        """neanelu-ci, staging-cerniq, prod-cerniq all use hz.223."""
        hz223_hosted = [alias for alias, _, gw in PROXIED_NODES if gw == HZ_223]
        assert "neanelu-ci" in hz223_hosted
        assert "staging-cerniq" in hz223_hosted
        assert "prod-cerniq" in hz223_hosted

    def test_no_raw_hz215_string_in_proxied_nodes(self) -> None:
        """All hz.215 references in PROXIED_NODES must come from the HZ_215 constant
        (i.e. the constant value and the raw string must be equal)."""
        for _, _, gw in PROXIED_NODES:
            if gw == "hz.215":
                assert gw is HZ_215 or gw == HZ_215

    def test_hz_215_value(self) -> None:
        assert HZ_215 == "hz.215"

    def test_hz_223_value(self) -> None:
        assert HZ_223 == "hz.223"


# ---------------------------------------------------------------------------
# SSH option constants
# ---------------------------------------------------------------------------


class TestSshOptionConstants:
    def test_batch_mode_value(self) -> None:
        assert _OPT_BATCH_MODE == "BatchMode=yes"

    def test_strict_host_key_checking_value(self) -> None:
        assert _OPT_STRICT_HOST_KEY_CHECKING == "StrictHostKeyChecking=accept-new"

    def test_user_known_hosts_file_value(self) -> None:
        assert _OPT_USER_KNOWN_HOSTS_FILE == "UserKnownHostsFile=/dev/null"

    def test_log_level_value(self) -> None:
        assert _OPT_LOG_LEVEL == "LogLevel=ERROR"

    def test_ssh_opts_contains_all_four(self) -> None:
        opts_str = " ".join(_SSH_OPTS)
        assert _OPT_BATCH_MODE in opts_str
        assert _OPT_STRICT_HOST_KEY_CHECKING in opts_str
        assert _OPT_USER_KNOWN_HOSTS_FILE in opts_str
        assert _OPT_LOG_LEVEL in opts_str

    def test_ssh_opts_contains_connect_timeout(self) -> None:
        assert "ConnectTimeout=8" in " ".join(_SSH_OPTS)

    def test_storagebox_opts_contains_all_four(self) -> None:
        opts_str = " ".join(_SSH_STORAGEBOX_OPTS)
        assert _OPT_BATCH_MODE in opts_str
        assert _OPT_STRICT_HOST_KEY_CHECKING in opts_str
        assert _OPT_USER_KNOWN_HOSTS_FILE in opts_str
        assert _OPT_LOG_LEVEL in opts_str

    def test_storagebox_opts_no_connect_timeout(self) -> None:
        """Storage-box opts must NOT inject ConnectTimeout (transport profile differs)."""
        assert "ConnectTimeout" not in " ".join(_SSH_STORAGEBOX_OPTS)

    def test_opts_list_structure_pairs(self) -> None:
        """Every option flag must be a '-o' / 'Key=Value' pair."""
        for i in range(0, len(_SSH_STORAGEBOX_OPTS) - 1, 2):
            assert _SSH_STORAGEBOX_OPTS[i] == "-o"
            assert "=" in _SSH_STORAGEBOX_OPTS[i + 1]


# ---------------------------------------------------------------------------
# _merge_authorized_keys
# ---------------------------------------------------------------------------

_KEY_A = "ssh-ed25519 AAAA...bodyA comment-a"
_KEY_B = "ssh-ed25519 AAAA...bodyB comment-b"
_KEY_C = "ssh-rsa BBBB...bodyC comment-c"


class TestMergeAuthorizedKeys:
    def test_empty_existing_all_added(self) -> None:
        merged, added, skipped = _merge_authorized_keys(
            [_KEY_A, _KEY_B], existing_lines=[], existing_bodies=set()
        )
        assert added == 2
        assert skipped == 0
        assert _KEY_A in merged
        assert _KEY_B in merged

    def test_existing_keys_skipped(self) -> None:
        body_a = _KEY_A.split()[1]
        merged, added, skipped = _merge_authorized_keys(
            [_KEY_A],
            existing_lines=[_KEY_A],
            existing_bodies={body_a},
        )
        assert added == 0
        assert skipped == 1
        assert merged.count(_KEY_A) == 1  # no duplicate

    def test_partial_overlap(self) -> None:
        body_a = _KEY_A.split()[1]
        merged, added, skipped = _merge_authorized_keys(
            [_KEY_A, _KEY_B],
            existing_lines=[_KEY_A],
            existing_bodies={body_a},
        )
        assert added == 1
        assert skipped == 1
        assert _KEY_B in merged

    def test_malformed_key_ignored(self) -> None:
        """Keys with fewer than SSH_KEY_MIN_PARTS parts are silently skipped."""
        merged, added, skipped = _merge_authorized_keys(
            ["not-a-valid-key"],
            existing_lines=[],
            existing_bodies=set(),
        )
        assert added == 0
        assert skipped == 0
        assert merged == []

    def test_preserves_existing_order(self) -> None:
        merged, _, _ = _merge_authorized_keys(
            [_KEY_C],
            existing_lines=[_KEY_A, _KEY_B],
            existing_bodies={_KEY_A.split()[1], _KEY_B.split()[1]},
        )
        assert merged[0] == _KEY_A
        assert merged[1] == _KEY_B
        assert merged[2] == _KEY_C

    def test_no_duplicate_on_second_merge(self) -> None:
        """Calling merge twice must not add the same key twice."""
        bodies: set[str] = set()
        merged, _, _ = _merge_authorized_keys([_KEY_A], [], bodies)
        # Simulate a second run with the same input
        merged2, added2, skipped2 = _merge_authorized_keys([_KEY_A], merged, bodies)
        assert added2 == 0
        assert skipped2 == 1
        assert merged2.count(_KEY_A) == 1

    def test_empty_all_keys_returns_existing(self) -> None:
        existing = [_KEY_A, _KEY_B]
        body_a = _KEY_A.split()[1]
        body_b = _KEY_B.split()[1]
        merged, added, skipped = _merge_authorized_keys(
            [], existing_lines=existing, existing_bodies={body_a, body_b}
        )
        assert added == 0
        assert skipped == 0
        assert merged == existing


# ---------------------------------------------------------------------------
# _download_and_parse_authorized_keys (local file parsing — no real SSH)
# ---------------------------------------------------------------------------


class TestDownloadAndParseAuthorizedKeys:
    def _run_parse(self, content: str) -> tuple[list[str], set[str]]:
        """Write content to a temp file and call the parsing branch directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            local_ak = os.path.join(tmpdir, "authorized_keys")
            with open(local_ak, "w", encoding="utf-8") as fh:
                fh.write(content)

            # Patch subprocess.run so the 'download' is a no-op (file already exists).
            with patch("mesh_keys.subprocess.run", return_value=MagicMock(returncode=0)):
                lines, bodies = _download_and_parse_authorized_keys("fake-alias", local_ak)
        return lines, bodies

    def test_parses_valid_keys(self) -> None:
        content = f"{_KEY_A}\n{_KEY_B}\n"
        lines, bodies = self._run_parse(content)
        assert _KEY_A in lines
        assert _KEY_B in lines
        assert _KEY_A.split()[1] in bodies
        assert _KEY_B.split()[1] in bodies

    def test_skips_blank_lines(self) -> None:
        content = f"{_KEY_A}\n\n   \n{_KEY_B}\n"
        lines, _ = self._run_parse(content)
        assert len(lines) == 2

    def test_malformed_lines_included_in_lines_but_not_bodies(self) -> None:
        """Non-blank lines are always appended to existing_lines.
        Lines with >= SSH_KEY_MIN_PARTS words have parts[1] tracked in bodies
        (including comment lines) — the merge step's own len(parts) guard
        prevents treating those bodies as valid keys during distribution."""
        content = "# this is a comment\n" + _KEY_A + "\n"
        lines, bodies = self._run_parse(content)
        # Both the comment and the real key line are preserved.
        assert "# this is a comment" in lines
        assert _KEY_A in lines
        # The comment's second word ('this') AND the real key body are tracked.
        assert _KEY_A.split()[1] in bodies
        assert "this" in bodies

    def test_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_ak = os.path.join(tmpdir, "authorized_keys")
            # Do NOT create the file — simulate download failure.
            with patch("mesh_keys.subprocess.run", return_value=MagicMock(returncode=1)):
                lines, bodies = _download_and_parse_authorized_keys("fake-alias", local_ak)
        assert lines == []
        assert bodies == set()


# ---------------------------------------------------------------------------
# install_keys_on_storagebox — dry-run fast path
# ---------------------------------------------------------------------------


class TestInstallKeysOnStorageboxDryRun:
    def test_dry_run_counts_all_keys_as_added(self) -> None:
        keys = [_KEY_A, _KEY_B, _KEY_C]
        result = install_keys_on_storagebox("hz.main-sb", keys, dry_run=True)
        assert isinstance(result, DistributeResult)
        assert result.added == 3
        assert result.skipped == 0
        assert result.errors == []

    def test_dry_run_empty_keys(self) -> None:
        result = install_keys_on_storagebox("hz.sbx1", [], dry_run=True)
        assert result.added == 0

    def test_dry_run_does_not_call_subprocess(self) -> None:
        """No subprocess must be spawned in dry-run mode."""
        with patch("mesh_keys.subprocess.run") as mock_run:
            install_keys_on_storagebox("hz.main-sb", [_KEY_A], dry_run=True)
        mock_run.assert_not_called()
