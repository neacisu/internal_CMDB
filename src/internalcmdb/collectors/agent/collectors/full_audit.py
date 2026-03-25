"""Collector: full_audit — comprehensive system audit. Tier: 1d.

Combines all other collectors into a single comprehensive snapshot.
"""

from __future__ import annotations

import logging
from typing import Any

from . import (
    certificate_state,
    container_resources,
    disk_state,
    docker_state,
    full_hardware,
    gpu_state,
    heartbeat,
    journal_errors,
    llm_endpoint_health,
    network_latency,
    network_state,
    process_inventory,
    security_posture,
    service_health,
    system_vitals,
    systemd_state,
    trust_surface_lite,
    vllm_metrics,
)

logger = logging.getLogger(__name__)

_ALL_COLLECTORS: dict[str, Any] = {
    "heartbeat": heartbeat,
    "system_vitals": system_vitals,
    "docker_state": docker_state,
    "container_resources": container_resources,
    "gpu_state": gpu_state,
    "vllm_metrics": vllm_metrics,
    "llm_endpoint_health": llm_endpoint_health,
    "service_health": service_health,
    "network_state": network_state,
    "network_latency": network_latency,
    "disk_state": disk_state,
    "process_inventory": process_inventory,
    "systemd_state": systemd_state,
    "journal_errors": journal_errors,
    "trust_surface_lite": trust_surface_lite,
    "certificate_state": certificate_state,
    "security_posture": security_posture,
    "full_hardware": full_hardware,
}


def collect() -> dict[str, Any]:
    """Return a full audit combining all collector outputs."""
    result: dict[str, Any] = {}
    for name, module in _ALL_COLLECTORS.items():
        try:
            result[name] = module.collect()
        except Exception:
            logger.warning("Collector %s failed during full audit", name, exc_info=True)
            result[name] = {"error": f"{name} collection failed"}
    return result
