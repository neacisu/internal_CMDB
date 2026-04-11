"""Collector: gpu_state — nvidia-smi metrics. Tier: 30s."""

from __future__ import annotations

import csv
import io
import subprocess
from typing import Any


def collect() -> dict[str, Any]:
    """Query nvidia-smi for GPU metrics."""
    fields = (
        "index,name,memory.total,memory.used,memory.free,"
        "utilization.gpu,utilization.memory,"
        "temperature.gpu,power.draw,power.limit"
    )
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                f"--query-gpu={fields}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return {"gpus": [], "error": result.stderr.strip()}

        reader = csv.reader(io.StringIO(result.stdout.strip()))
        gpus: list[dict[str, Any]] = []
        for row in reader:
            if len(row) < 10:  # noqa: PLR2004
                continue
            gpus.append(
                {
                    "index": int(row[0].strip()),
                    "name": row[1].strip(),
                    "memory_total_mb": int(row[2].strip()),
                    "memory_used_mb": int(row[3].strip()),
                    "memory_free_mb": int(row[4].strip()),
                    "utilization_gpu_pct": float(row[5].strip()),
                    "utilization_memory_pct": float(row[6].strip()),
                    "temperature_celsius": float(row[7].strip()),
                    "power_draw_watts": float(row[8].strip()),
                    "power_limit_watts": float(row[9].strip()),
                }
            )
        return {"gpus": gpus, "total": len(gpus)}
    except FileNotFoundError:
        return {"gpus": [], "error": "nvidia-smi not found"}
    except subprocess.TimeoutExpired:
        return {"gpus": [], "error": "timeout"}
