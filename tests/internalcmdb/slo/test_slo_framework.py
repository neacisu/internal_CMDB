"""Tests for internalcmdb.slo.framework — async DB paths with mocks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from internalcmdb.slo.framework import SLOFramework


@pytest.fixture
def mock_session() -> AsyncMock:
    s = AsyncMock()
    s.commit = AsyncMock()
    s.execute = AsyncMock()
    return s


@pytest.mark.asyncio
async def test_define_slo_invalid_target(mock_session: AsyncMock) -> None:
    fw = SLOFramework(mock_session)
    with pytest.raises(ValueError, match="SLO target"):
        await fw.define_slo("svc", "availability", 0.0)
    with pytest.raises(ValueError, match="SLO target"):
        await fw.define_slo("svc", "availability", 1.5)


@pytest.mark.asyncio
async def test_define_slo_invalid_window(mock_session: AsyncMock) -> None:
    fw = SLOFramework(mock_session)
    with pytest.raises(ValueError, match="window_days"):
        await fw.define_slo("svc", "availability", 0.99, window_days=0)
    with pytest.raises(ValueError, match="window_days"):
        await fw.define_slo("svc", "availability", 0.99, window_days=400)


@pytest.mark.asyncio
async def test_define_slo_success(mock_session: AsyncMock) -> None:
    fw = SLOFramework(mock_session)
    out = await fw.define_slo("api", "latency", 0.995, window_days=7)
    assert out["service_id"] == "api"
    assert out["sli_type"] == "latency"
    assert out["target"] == 0.995
    assert out["window_days"] == 7
    assert "slo_id" in out
    mock_session.execute.assert_awaited()
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_current_budget_not_found(mock_session: AsyncMock) -> None:
    fw = SLOFramework(mock_session)
    res = MagicMock()
    res.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=res)

    r = await fw.current_budget("missing")
    assert r["error"] == "SLO not found"


@pytest.mark.asyncio
async def test_current_budget_ok(mock_session: AsyncMock) -> None:
    fw = SLOFramework(mock_session)
    slo_mapping = {
        "target": 0.999,
        "window_days": 30,
    }
    slo_row = MagicMock()
    slo_row._mapping = slo_mapping

    meas_row = MagicMock()
    meas_row.good = 1000
    meas_row.total = 1000

    exec_results = [
        MagicMock(fetchone=MagicMock(return_value=slo_row)),
        MagicMock(fetchone=MagicMock(return_value=meas_row)),
    ]
    mock_session.execute = AsyncMock(side_effect=exec_results)

    r = await fw.current_budget("slo-1")
    assert "burn_rate" in r
    assert r.get("status") in {"ok", "exhausted", "fast_burn", "slow_burn"}
