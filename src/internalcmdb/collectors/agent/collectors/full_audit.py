"""Collector: full_audit — comprehensive system audit. Tier: 1d.

Combines all other collectors into a single comprehensive snapshot.
"""

from __future__ import annotations

from typing import Any

from . import (
    disk_state,
    docker_state,
    gpu_state,
    heartbeat,
    network_state,
    process_inventory,
    security_posture,
    service_health,
    system_vitals,
    systemd_state,
    trust_surface_lite,
)


def collect() -> dict[str, Any]:
    """Return a full audit combining all collector outputs."""
    return {
        "heartbeat": heartbeat.collect(),
        "system_vitals": system_vitals.collect(),
        "docker_state": docker_state.collect(),
        "gpu_state": gpu_state.collect(),
        "service_health": service_health.collect(),
        "network_state": network_state.collect(),
        "disk_state": disk_state.collect(),
        "process_inventory": process_inventory.collect(),
        "systemd_state": systemd_state.collect(),
        "trust_surface_lite": trust_surface_lite.collect(),
        "security_posture": security_posture.collect(),
    }
