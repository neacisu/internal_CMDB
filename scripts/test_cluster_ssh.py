#!/usr/bin/env python3
"""Compatibility launcher for the cluster SSH checker subproject."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = (
        Path(__file__).resolve().parents[1]
        / "subprojects"
        / "cluster-ssh-checker"
        / "test_cluster_ssh.py"
    )
    runpy.run_path(str(target), run_name="__main__")
