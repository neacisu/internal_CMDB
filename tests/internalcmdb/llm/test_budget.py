"""Tests for llm.budget — TokenBudgetManager."""
from __future__ import annotations
import asyncio
import pytest
from internalcmdb.llm.budget import TokenBudgetManager


@pytest.fixture
def mgr():
    return TokenBudgetManager()


@pytest.mark.asyncio
async def test_check_budget_within_limit(mgr):
    assert await mgr.check_budget("agent-audit", 1000) is True


@pytest.mark.asyncio
async def test_check_budget_exceeds_limit(mgr):
    # agent-audit has 200_000 limit; fill it
    await mgr.record_usage("agent-audit", 199_001)
    assert await mgr.check_budget("agent-audit", 1000) is False


@pytest.mark.asyncio
async def test_check_budget_exactly_at_limit(mgr):
    await mgr.record_usage("agent-audit", 199_000)
    assert await mgr.check_budget("agent-audit", 1000) is True


@pytest.mark.asyncio
async def test_check_budget_unknown_caller_uses_default(mgr):
    assert await mgr.check_budget("unknown-caller", 50_000) is True


@pytest.mark.asyncio
async def test_check_budget_does_not_record(mgr):
    await mgr.check_budget("agent-audit", 5000)
    stats = await mgr.get_usage_stats()
    assert stats["callers"].get("agent-audit", {}).get("used", 0) == 0


@pytest.mark.asyncio
async def test_record_usage_increments(mgr):
    await mgr.record_usage("cognitive-query", 3000)
    await mgr.record_usage("cognitive-query", 2000)
    stats = await mgr.get_usage_stats()
    assert stats["callers"]["cognitive-query"]["used"] == 5000


@pytest.mark.asyncio
async def test_get_usage_stats_structure(mgr):
    await mgr.record_usage("agent-audit", 10_000)
    stats = await mgr.get_usage_stats()
    assert "timestamp" in stats
    assert "callers" in stats
    caller_stat = stats["callers"]["agent-audit"]
    assert "used" in caller_stat
    assert "limit" in caller_stat
    assert "remaining" in caller_stat
    assert "utilization_pct" in caller_stat


@pytest.mark.asyncio
async def test_get_usage_stats_remaining(mgr):
    await mgr.record_usage("cognitive-query", 10_000)
    stats = await mgr.get_usage_stats()
    stat = stats["callers"]["cognitive-query"]
    assert stat["remaining"] == stat["limit"] - stat["used"]


@pytest.mark.asyncio
async def test_spike_detection_logs_warning(mgr, caplog):
    import logging
    caplog.set_level(logging.WARNING, logger="internalcmdb.llm.budget")
    for _ in range(5):
        await mgr.record_usage("cognitive-query", 100)
    await mgr.record_usage("cognitive-query", 5000)
    assert any("SPIKE" in r.message or "spike" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_custom_budget_per_caller(mgr):
    assert await mgr.check_budget("report-generator", 299_000) is True


@pytest.mark.asyncio
async def test_concurrent_usage_is_safe(mgr):
    tasks = [mgr.record_usage("agent-audit", 1000) for _ in range(50)]
    await asyncio.gather(*tasks)
    stats = await mgr.get_usage_stats()
    assert stats["callers"]["agent-audit"]["used"] == 50_000
