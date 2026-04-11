"""Collector: llm_endpoint_health — LLM endpoint response time, status, errors. Tier: 30s."""

from __future__ import annotations

import contextlib
import time
from typing import Any

import httpx

DEFAULT_ENDPOINTS: list[dict[str, Any]] = [
    {"name": "vllm-primary", "url": "http://127.0.0.1:8000/health"},
]


def _check_endpoint(name: str, url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Health-check a single LLM endpoint."""
    start = time.monotonic()
    try:
        resp = httpx.get(url, timeout=timeout)
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)

        body: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            body = resp.json()

        return {
            "name": name,
            "url": url,
            "status_code": resp.status_code,
            "response_time_ms": elapsed_ms,
            "healthy": 200 <= resp.status_code < 300,  # noqa: PLR2004
            "model_loaded": body.get("model", body.get("model_id")),
        }
    except httpx.ConnectError:
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "name": name,
            "url": url,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "healthy": False,
            "error": "connection_refused",
        }
    except httpx.TimeoutException:
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "name": name,
            "url": url,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "healthy": False,
            "error": "timeout",
        }
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "name": name,
            "url": url,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "healthy": False,
            "error": f"unexpected: {exc}",
        }


def collect(endpoints: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Health-check all configured LLM endpoints."""
    targets = endpoints or DEFAULT_ENDPOINTS
    results = []
    for ep in targets:
        name = ep.get("name", "unknown")
        url = ep.get("url", "")
        if not url:
            results.append({"name": name, "url": "", "healthy": False, "error": "missing url"})
            continue
        results.append(_check_endpoint(name, url))
    healthy = sum(1 for r in results if r.get("healthy"))
    return {
        "endpoints": results,
        "total": len(results),
        "healthy": healthy,
        "unhealthy": len(results) - healthy,
    }
