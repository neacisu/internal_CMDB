"""Collector: journal_errors — systemd journal errors grouped by unit/severity. Tier: 5min."""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from typing import Any


_MAX_GROUPS = 200
_MAX_JOURNAL_LINES = 50_000


def collect(since: str = "5 minutes ago") -> dict[str, Any]:
    """Query journalctl for recent errors and aggregate by unit + severity."""
    try:
        result = subprocess.run(
            [
                "journalctl",
                "--since", since,
                "-p", "err",
                "-o", "json",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode != 0:
            return {"groups": [], "total_errors": 0, "error": result.stderr.strip()}

        counts: dict[tuple[str, str], int] = defaultdict(int)
        total = 0
        lines_processed = 0

        severity_map = {
            "0": "emerg", "1": "alert", "2": "crit",
            "3": "err", "4": "warning", "5": "notice",
            "6": "info", "7": "debug",
        }

        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            lines_processed += 1
            if lines_processed > _MAX_JOURNAL_LINES:
                break
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            unit = entry.get("_SYSTEMD_UNIT", entry.get("SYSLOG_IDENTIFIER", "unknown"))
            priority = entry.get("PRIORITY", "3")
            severity = severity_map.get(str(priority), f"priority_{priority}")
            counts[(unit, severity)] += 1
            total += 1

        groups = [
            {"unit": unit, "severity": sev, "count": cnt}
            for (unit, sev), cnt in sorted(counts.items(), key=lambda x: -x[1])
        ]
        truncated = len(groups) > _MAX_GROUPS
        if truncated:
            groups = groups[:_MAX_GROUPS]

        return {"groups": groups, "total_errors": total, "truncated": truncated}

    except FileNotFoundError:
        return {"groups": [], "total_errors": 0, "error": "journalctl not found"}
    except subprocess.TimeoutExpired:
        return {"groups": [], "total_errors": 0, "error": "timeout"}
