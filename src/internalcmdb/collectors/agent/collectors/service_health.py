"""Collector: service_health — TCP/HTTP probes for known services. Tier: 1min."""

from __future__ import annotations

import socket
import subprocess
from typing import Any

# Default probes — can be overridden by agent config
DEFAULT_PROBES: list[dict[str, Any]] = [
    {"name": "postgresql", "host": "127.0.0.1", "port": 5432, "kind": "tcp"},
    {"name": "redis", "host": "127.0.0.1", "port": 6379, "kind": "tcp"},
    {"name": "traefik-http", "host": "127.0.0.1", "port": 80, "kind": "tcp"},
    {"name": "traefik-https", "host": "127.0.0.1", "port": 443, "kind": "tcp"},
    {"name": "node-exporter", "host": "127.0.0.1", "port": 9100, "kind": "tcp"},
    {"name": "docker-api", "host": "127.0.0.1", "port": 2375, "kind": "tcp"},
]


def _check_tcp(host: str, port: int, timeout: float = 2.0) -> str:
    """Return 'healthy' if TCP connect succeeds, else error string."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "healthy"
    except TimeoutError:
        return "timeout"
    except ConnectionRefusedError:
        return "connection_refused"
    except OSError as exc:
        return str(exc)


def _check_http(url: str, timeout: float = 3.0) -> str:
    """Return 'healthy' if HTTP GET returns 2xx."""
    try:
        result = subprocess.run(
            ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        code = result.stdout.strip()
        if code.startswith("2"):
            return "healthy"
        return f"http_{code}"
    except FileNotFoundError, subprocess.TimeoutExpired:
        return "error"


def collect(probes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run service health probes and return results."""
    targets = probes or DEFAULT_PROBES
    results = []
    for probe in targets:
        kind = probe.get("kind", "tcp")
        if kind == "tcp":
            status = _check_tcp(probe["host"], probe["port"])
        elif kind == "http":
            status = _check_http(probe.get("url", f"http://{probe['host']}:{probe['port']}/"))
        else:
            status = "unsupported_kind"
        results.append(
            {
                "name": probe["name"],
                "host": probe.get("host"),
                "port": probe.get("port"),
                "kind": kind,
                "status": status,
            }
        )
    healthy = sum(1 for r in results if r["status"] == "healthy")
    return {
        "probes": results,
        "total": len(results),
        "healthy": healthy,
        "unhealthy": len(results) - healthy,
    }
