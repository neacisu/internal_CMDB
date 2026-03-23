"""Collector: vllm_metrics — GPU util, VRAM, queue depth, tokens/s, latency. Tier: 30s."""

from __future__ import annotations

import re
from typing import Any

import httpx

VLLM_METRICS_URL = "http://127.0.0.1:8000/metrics"

_GAUGE_PATTERNS: dict[str, str] = {
    "gpu_utilization_pct": r"^vllm:gpu_cache_usage_perc\s+(\S+)",
    "num_requests_running": r"^vllm:num_requests_running\s+(\S+)",
    "num_requests_waiting": r"^vllm:num_requests_waiting\s+(\S+)",
}

_HISTOGRAM_SUM_PATTERNS: dict[str, str] = {
    "e2e_latency_sum": r"^vllm:e2e_request_latency_seconds_sum\s+(\S+)",
    "e2e_latency_count": r"^vllm:e2e_request_latency_seconds_count\s+(\S+)",
    "tokens_total": r"^vllm:generation_tokens_total\s+(\S+)",
}

_QUANTILE_RE = re.compile(
    r'^vllm:e2e_request_latency_seconds_bucket\{le="([^"]+)"\}\s+(\S+)'
)


def _parse_prometheus(text: str) -> dict[str, Any]:
    """Extract key vLLM metrics from Prometheus exposition format."""
    metrics: dict[str, Any] = {}

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        for key, pattern in {**_GAUGE_PATTERNS, **_HISTOGRAM_SUM_PATTERNS}.items():
            m = re.match(pattern, line)
            if m:
                metrics[key] = float(m.group(1))
                break

    latency_sum = metrics.get("e2e_latency_sum", 0.0)
    latency_count = metrics.get("e2e_latency_count", 0.0)
    if latency_count > 0:
        metrics["latency_avg_seconds"] = round(latency_sum / latency_count, 6)

    queue_depth = int(
        metrics.get("num_requests_running", 0) + metrics.get("num_requests_waiting", 0)
    )
    metrics["request_queue_depth"] = queue_depth

    return metrics


_MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MiB guard against runaway /metrics


def collect(url: str | None = None) -> dict[str, Any]:
    """Query vLLM /metrics endpoint and return parsed metrics."""
    target = url or VLLM_METRICS_URL
    try:
        resp = httpx.get(target, timeout=5)
        if resp.status_code != 200:  # noqa: PLR2004
            return {"error": f"HTTP {resp.status_code}", "url": target}
        if len(resp.content) > _MAX_RESPONSE_BYTES:
            return {"error": "response_too_large", "url": target,
                    "bytes": len(resp.content)}
        return _parse_prometheus(resp.text)
    except httpx.ConnectError:
        return {"error": "connection_refused", "url": target}
    except httpx.TimeoutException:
        return {"error": "timeout", "url": target}
    except Exception as exc:
        return {"error": f"unexpected: {exc}", "url": target}
