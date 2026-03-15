"""Schedule tier definitions — maps interval codes to seconds and default collectors."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScheduleTier:
    """A named collection interval with its default collector set."""

    code: str
    interval_seconds: int
    collectors: list[str] = field(default_factory=list)


TIERS: dict[str, ScheduleTier] = {
    t.code: t
    for t in [
        ScheduleTier(
            code="5s",
            interval_seconds=5,
            collectors=["heartbeat"],
        ),
        ScheduleTier(
            code="10s",
            interval_seconds=10,
            collectors=["system_vitals"],
        ),
        ScheduleTier(
            code="15s",
            interval_seconds=15,
            collectors=["docker_state"],
        ),
        ScheduleTier(
            code="30s",
            interval_seconds=30,
            collectors=["gpu_state"],
        ),
        ScheduleTier(
            code="1min",
            interval_seconds=60,
            collectors=["service_health"],
        ),
        ScheduleTier(
            code="5min",
            interval_seconds=300,
            collectors=["network_state", "disk_state"],
        ),
        ScheduleTier(
            code="30min",
            interval_seconds=1800,
            collectors=["process_inventory", "systemd_state"],
        ),
        ScheduleTier(
            code="1h",
            interval_seconds=3600,
            collectors=["trust_surface_lite"],
        ),
        ScheduleTier(
            code="3h",
            interval_seconds=10800,
            collectors=["security_posture"],
        ),
        ScheduleTier(
            code="12h",
            interval_seconds=43200,
            collectors=["full_hardware"],
        ),
        ScheduleTier(
            code="1d",
            interval_seconds=86400,
            collectors=["full_audit"],
        ),
    ]
}

ALL_TIER_CODES: list[str] = list(TIERS.keys())

DEFAULT_AGENT_CONFIG = {
    "tiers": {code: tier.interval_seconds for code, tier in TIERS.items()},
    "enabled_collectors": [c for t in TIERS.values() for c in t.collectors],
}
