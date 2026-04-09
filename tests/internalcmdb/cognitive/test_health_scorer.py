"""Tests for cognitive.health_scorer."""

from __future__ import annotations

import pytest

from internalcmdb.cognitive.health_scorer import FleetHealthScore, HealthScore, HealthScorer

_PERFECT = {
    "host_id": "h1",
    "cpu_usage_pct": 10.0,
    "memory_usage_pct": 20.0,
    "disk_usage_pct": 30.0,
    "services_total": 5,
    "services_healthy": 5,
}
_CRITICAL = {
    "host_id": "h2",
    "cpu_usage_pct": 99.0,
    "memory_usage_pct": 98.0,
    "disk_usage_pct": 97.0,
    "services_total": 10,
    "services_healthy": 1,
}


def test_score_host_returns_health_score():
    r = HealthScorer().score_host(_PERFECT)
    assert isinstance(r, HealthScore)
    assert r.entity_id == "h1"
    assert r.score > 0


def test_score_host_high_utilisation_low_score():
    r = HealthScorer().score_host(_CRITICAL)
    assert r.score < 40


def test_score_host_healthy_classification():
    assert HealthScorer().score_host(_PERFECT).breakdown["status"] == "healthy"


def test_score_host_critical_classification():
    assert HealthScorer().score_host(_CRITICAL).breakdown["status"] == "critical"


def test_score_host_missing_cpu_penalised():
    host = {
        "host_id": "h3",
        "cpu_usage_pct": None,
        "memory_usage_pct": 20.0,
        "disk_usage_pct": 30.0,
        "services_total": 5,
        "services_healthy": 5,
    }
    r = HealthScorer().score_host(host)
    assert "missing_metrics" in r.breakdown
    assert "cpu_usage_pct" in r.breakdown["missing_metrics"]


def test_score_host_all_metrics_missing():
    r = HealthScorer().score_host({"host_id": "h4"})
    assert r.score >= 0
    assert len(r.breakdown.get("missing_metrics", [])) == 3


def test_score_host_fallback_entity_id():
    host = {
        "entity_id": "ent-999",
        "cpu_usage_pct": 10.0,
        "memory_usage_pct": 10.0,
        "disk_usage_pct": 10.0,
        "services_total": 0,
        "services_healthy": 0,
    }
    assert HealthScorer().score_host(host).entity_id == "ent-999"


def test_score_host_gpu_capable_with_metrics():
    host = {**_PERFECT, "is_gpu_capable": True, "gpu_usage_pct": 50.0}
    assert "gpu_health" in HealthScorer().score_host(host).breakdown


def test_score_host_gpu_capable_no_metrics():
    host = {**_PERFECT, "is_gpu_capable": True}
    assert "gpu_health_note" in HealthScorer().score_host(host).breakdown


def test_score_host_invalid_numeric():
    host = {
        "host_id": "h5",
        "cpu_usage_pct": "bad",
        "memory_usage_pct": float("nan"),
        "disk_usage_pct": float("inf"),
        "services_total": 3,
        "services_healthy": 2,
    }
    assert HealthScorer().score_host(host).score >= 0


def test_score_host_no_services_full_service_score():
    host = {
        "host_id": "h6",
        "cpu_usage_pct": 20.0,
        "memory_usage_pct": 20.0,
        "disk_usage_pct": 20.0,
        "services_total": 0,
        "services_healthy": 0,
    }
    assert HealthScorer().score_host(host).breakdown["service_health"] == 25


def test_score_fleet_empty():
    r = HealthScorer().score_fleet([])
    assert isinstance(r, FleetHealthScore)
    assert r.total_hosts == 0
    assert r.average_score == pytest.approx(0.0)  # pyright: ignore[reportUnknownMemberType]


def test_score_fleet_counts():
    r = HealthScorer().score_fleet([_PERFECT, _CRITICAL])
    assert r.total_hosts == 2
    assert r.healthy_count + r.warning_count + r.critical_count == 2


def test_score_fleet_min_max():
    r = HealthScorer().score_fleet([_PERFECT, _CRITICAL])
    assert r.min_score <= r.max_score


def test_utilisation_subscore_zero():
    assert HealthScorer._utilisation_subscore(0.0) == 25


def test_utilisation_subscore_100():
    assert HealthScorer._utilisation_subscore(100.0) == 0


def test_service_subscore_full():
    assert HealthScorer._service_subscore(10, 10) == 25


def test_service_subscore_none():
    assert HealthScorer._service_subscore(10, 0) == 0


def test_service_subscore_no_services():
    assert HealthScorer._service_subscore(0, 0) == 25


def test_status_label_healthy():
    assert HealthScorer._status_label(81) == "healthy"


def test_status_label_warning():
    assert HealthScorer._status_label(70) == "warning"


def test_status_label_critical():
    assert HealthScorer._status_label(59) == "critical"


def test_safe_metric_none():
    missing: list[str] = []
    val = HealthScorer._safe_metric(None, "cpu", missing)
    assert val == pytest.approx(0.0)  # pyright: ignore[reportUnknownMemberType]
    assert "cpu" in missing


def test_safe_metric_valid():
    missing: list[str] = []
    assert HealthScorer._safe_metric(42.5, "cpu", missing) == pytest.approx(42.5)  # pyright: ignore[reportUnknownMemberType]
    assert missing == []


def test_safe_metric_nan():
    missing: list[str] = []
    val = HealthScorer._safe_metric(float("nan"), "cpu", missing)
    assert val == pytest.approx(0.0)  # pyright: ignore[reportUnknownMemberType]
    assert "cpu" in missing
