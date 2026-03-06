"""Health and readiness checks for service-level validation."""

from __future__ import annotations


def health_check() -> dict[str, str]:
    """Return a basic health payload used by tests and runtime probes."""
    return {"status": "ok"}
