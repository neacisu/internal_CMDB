"""Tests for the heartbeat collector module."""

from __future__ import annotations

from typing import Any

from internalcmdb.collectors.agent.collectors import heartbeat


class TestHeartbeatCollector:
    def test_collect_returns_dict(self) -> None:
        result = heartbeat.collect()
        assert isinstance(result, dict)

    def test_collect_has_expected_keys(self) -> None:
        result = heartbeat.collect()
        assert "uptime_seconds" in result
        assert "load_avg" in result
        assert "memory_pct" in result

    def test_uptime_is_positive(self) -> None:
        result = heartbeat.collect()
        assert result["uptime_seconds"] > 0

    def test_load_avg_is_list(self) -> None:
        result = heartbeat.collect()
        load_avg: list[Any] = result["load_avg"]
        assert isinstance(load_avg, list)
        assert len(load_avg) == 3
