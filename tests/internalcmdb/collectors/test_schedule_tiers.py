"""Tests for schedule_tiers module."""

from __future__ import annotations

from internalcmdb.collectors.schedule_tiers import (
    ALL_TIER_CODES,
    DEFAULT_AGENT_CONFIG,
    TIERS,
    ScheduleTier,
)


class TestScheduleTiers:
    def test_all_tiers_defined(self) -> None:
        assert len(TIERS) == 11

    def test_tier_codes_match(self) -> None:
        for code, tier in TIERS.items():
            assert tier.code == code

    def test_intervals_are_ascending(self) -> None:
        intervals = [t.interval_seconds for t in TIERS.values()]
        assert intervals == sorted(intervals)

    def test_all_tier_codes_list(self) -> None:
        assert list(TIERS.keys()) == ALL_TIER_CODES

    def test_default_agent_config_has_tiers(self) -> None:
        assert "tiers" in DEFAULT_AGENT_CONFIG
        assert "enabled_collectors" in DEFAULT_AGENT_CONFIG
        assert len(DEFAULT_AGENT_CONFIG["enabled_collectors"]) == 13

    def test_tier_is_frozen(self) -> None:
        tier = ScheduleTier(code="test", interval_seconds=1, collectors=["a"])
        assert tier.code == "test"

    def test_5s_tier_has_heartbeat(self) -> None:
        assert "heartbeat" in TIERS["5s"].collectors

    def test_1d_tier_has_full_audit(self) -> None:
        assert "full_audit" in TIERS["1d"].collectors

    def test_5min_tier_has_two_collectors(self) -> None:
        assert len(TIERS["5min"].collectors) == 2
        assert "network_state" in TIERS["5min"].collectors
        assert "disk_state" in TIERS["5min"].collectors
