"""Collector: journal_errors — systemd journal errors grouped by unit/severity. Tier: 5min."""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from typing import Any

_MAX_GROUPS = 200
_MAX_JOURNAL_LINES = 50_000

_SEVERITY_MAP: dict[str, str] = {
    "0": "emerg",
    "1": "alert",
    "2": "crit",
    "3": "err",
    "4": "warning",
    "5": "notice",
    "6": "info",
    "7": "debug",
}


def _run_journalctl(since: str) -> subprocess.CompletedProcess[str] | None:
    """Run journalctl and return the CompletedProcess, or None on binary-not-found/timeout."""
    try:
        return subprocess.run(
            ["journalctl", "--since", since, "-p", "err", "-o", "json", "--no-pager"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def _parse_journal_lines(stdout: str) -> tuple[dict[tuple[str, str], int], int]:
    """Parse journalctl JSON output; return (counts_by_unit_severity, total)."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    total = 0
    lines_processed = 0
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        lines_processed += 1
        if lines_processed > _MAX_JOURNAL_LINES:
            break
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        unit: str = entry.get("_SYSTEMD_UNIT", entry.get("SYSLOG_IDENTIFIER", "unknown"))
        priority: str = str(entry.get("PRIORITY", "3"))
        severity: str = _SEVERITY_MAP.get(priority, f"priority_{priority}")
        counts[(unit, severity)] += 1
        total += 1
    return counts, total


def _build_groups(
    counts: dict[tuple[str, str], int],
    total: int,
) -> dict[str, Any]:
    """Convert counts dict to sorted groups list and return the final result payload."""
    groups = [
        {"unit": unit, "severity": sev, "count": cnt}
        for (unit, sev), cnt in sorted(counts.items(), key=lambda x: -x[1])
    ]
    truncated = len(groups) > _MAX_GROUPS
    return {
        "groups": groups[:_MAX_GROUPS] if truncated else groups,
        "total_errors": total,
        "truncated": truncated,
    }


def collect(since: str = "5 minutes ago") -> dict[str, Any]:
    """Query journalctl for recent errors and aggregate by unit + severity."""
    proc = _run_journalctl(since)
    if proc is None:
        # FileNotFoundError or TimeoutExpired — return appropriate error
        return {"groups": [], "total_errors": 0, "error": "journalctl unavailable or timed out"}
    if proc.returncode != 0:
        return {"groups": [], "total_errors": 0, "error": proc.stderr.strip()}

    counts, total = _parse_journal_lines(proc.stdout)
    return _build_groups(counts, total)
