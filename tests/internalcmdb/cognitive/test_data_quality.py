"""Unit tests for data quality freshness helpers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from internalcmdb.cognitive.data_quality import (
    DataQualityReport,
    DataQualityScorer,
    _classify_host_freshness,
    _normalize_host_last_seen,
)


def test_normalize_missing_last_seen() -> None:
    assert _normalize_host_last_seen(None) is None
    assert _normalize_host_last_seen("") is None


def test_normalize_invalid_iso_string() -> None:
    assert _normalize_host_last_seen("not-a-timestamp") is None


def test_normalize_datetime_passthrough() -> None:
    dt = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    assert _normalize_host_last_seen(dt) is dt


@pytest.mark.parametrize(
    ("hours_offset", "expected_fresh"),
    [
        (1, True),
        (23, True),
        (24, True),
        (25, False),
    ],
)
def test_classify_freshness_window(hours_offset: int, expected_fresh: bool) -> None:
    now = datetime.now(tz=UTC)
    last = now - timedelta(hours=hours_offset)
    host = {"host_code": "edge-host", "last_seen_at": last.isoformat()}
    is_fresh, code = _classify_host_freshness(host, now)
    assert code == "edge-host"
    assert is_fresh is expected_fresh


# ---------------------------------------------------------------------------
# DataQualityScorer — no-session (fallback) path
# ---------------------------------------------------------------------------


def test_scorer_no_session_score_returns_report() -> None:
    """score() with no DB session uses all fallback data and returns a valid report."""
    scorer = DataQualityScorer()
    report = asyncio.run(scorer.score())

    assert isinstance(report, DataQualityReport)
    assert 0.0 <= report.completeness <= 1.0
    assert 0.0 <= report.freshness <= 1.0
    assert 0.0 <= report.accuracy <= 1.0
    assert 0.0 <= report.consistency <= 1.0
    assert 0.0 <= report.overall <= 1.0
    assert isinstance(report.issues, list)
    assert isinstance(report.details, dict)
    assert report.scored_at  # ISO timestamp


def test_scorer_no_session_report_weighted_average() -> None:
    """overall must equal the weighted sum of the four dimensions."""
    scorer = DataQualityScorer()
    report = asyncio.run(scorer.score())

    expected = (
        report.completeness * 0.25
        + report.freshness * 0.30
        + report.accuracy * 0.25
        + report.consistency * 0.20
    )
    assert report.overall == pytest.approx(expected, abs=1e-4)


def test_scorer_no_session_host_count_populated() -> None:
    scorer = DataQualityScorer()
    report = asyncio.run(scorer.score())
    assert report.host_count >= 0


# ---------------------------------------------------------------------------
# _fetch_sample_facts — no-session fallback
# ---------------------------------------------------------------------------


def test_fetch_sample_facts_no_session_returns_fallback() -> None:
    """Without a session, _fetch_sample_facts returns the built-in fallback list."""
    scorer = DataQualityScorer()
    facts = scorer._fetch_sample_facts()
    assert isinstance(facts, list)
    assert len(facts) >= 1
    assert "fact_key" in facts[0]


# ---------------------------------------------------------------------------
# _fetch_cross_references — no-session fallback
# ---------------------------------------------------------------------------


def test_fetch_cross_references_no_session_returns_fallback() -> None:
    """Without a session, _fetch_cross_references returns the built-in fallback list."""
    scorer = DataQualityScorer()
    refs = scorer._fetch_cross_references()
    assert isinstance(refs, list)
    assert len(refs) >= 1
    assert "source_table" in refs[0]
    assert "resolves" in refs[0]


# ---------------------------------------------------------------------------
# _score_accuracy — fact verification logic
# ---------------------------------------------------------------------------


def test_score_accuracy_all_verified() -> None:
    scorer = DataQualityScorer()
    scorer._fetch_sample_facts = lambda: [  # type: ignore[method-assign]
        {"entity_id": "h1", "fact_key": "os.kernel", "verified": True},
        {"entity_id": "h2", "fact_key": "disk.total", "verified": True},
    ]
    score, issues, details = scorer._score_accuracy()
    assert score == pytest.approx(1.0, abs=1e-4)
    assert issues == []
    assert details["verified"] == 2


def test_score_accuracy_none_verified() -> None:
    scorer = DataQualityScorer()
    scorer._fetch_sample_facts = lambda: [  # type: ignore[method-assign]
        {"entity_id": "h1", "fact_key": "ip", "verified": False, "expected": "x", "observed": "y"},
    ]
    score, _issues, _details = scorer._score_accuracy()
    assert score == pytest.approx(0.0, abs=1e-4)
    assert len(_issues) == 1
    assert "Accuracy" in _issues[0]


def test_score_accuracy_empty_facts_perfect_score() -> None:
    """Zero facts to validate → score defaults to 1.0 (no evidence of inaccuracy)."""
    scorer = DataQualityScorer()
    scorer._fetch_sample_facts = lambda: []  # type: ignore[method-assign]
    score, _issues, details = scorer._score_accuracy()
    assert score == pytest.approx(1.0, abs=1e-4)
    assert details["facts_checked"] == 0


# ---------------------------------------------------------------------------
# _score_consistency — cross-reference validation logic
# ---------------------------------------------------------------------------


def test_score_consistency_all_resolve() -> None:
    scorer = DataQualityScorer()
    scorer._fetch_cross_references = lambda: [  # type: ignore[method-assign]
        {"source_table": "t1", "source_id": "s1",
         "target_table": "t2", "target_id": "t1", "resolves": True},
        {"source_table": "t1", "source_id": "s2",
         "target_table": "t2", "target_id": "t2", "resolves": True},
    ]
    score, issues, details = scorer._score_consistency()
    assert score == pytest.approx(1.0, abs=1e-4)
    assert issues == []
    assert details["valid"] == 2


def test_score_consistency_broken_ref_lowers_score() -> None:
    scorer = DataQualityScorer()
    scorer._fetch_cross_references = lambda: [  # type: ignore[method-assign]
        {"source_table": "t1", "source_id": "s1",
         "target_table": "t2", "target_id": "t1", "resolves": True},
        {"source_table": "t1", "source_id": "s2",
         "target_table": "t2", "target_id": "NULL", "resolves": False},
    ]
    score, issues, details = scorer._score_consistency()
    assert score == pytest.approx(0.5, abs=1e-4)
    assert len(issues) == 1
    assert "Consistency" in issues[0]
    assert details["broken"][0]["target_id"] == "NULL"


def test_score_consistency_empty_refs_perfect_score() -> None:
    """Zero cross-refs → score defaults to 1.0 (nothing broken)."""
    scorer = DataQualityScorer()
    scorer._fetch_cross_references = lambda: []  # type: ignore[method-assign]
    score, _issues, details = scorer._score_consistency()
    assert score == pytest.approx(1.0, abs=1e-4)
    assert details["references_checked"] == 0


# ---------------------------------------------------------------------------
# _query_service_instance_refs / _query_agent_refs — assert guard + execute
# ---------------------------------------------------------------------------


def _make_mock_session_for_refs(rows: list[dict]) -> MagicMock:
    """Build an async session mock that returns the given rows on execute."""
    session = AsyncMock()

    mock_result = MagicMock()
    mock_rows = []
    for row in rows:
        r = MagicMock()
        r._mapping = row
        mock_rows.append(r)
    mock_result.fetchall.return_value = mock_rows
    session.execute = AsyncMock(return_value=mock_result)
    return session


def test_query_service_instance_refs_appends_rows() -> None:
    """_query_service_instance_refs appends one entry per returned row."""
    session = _make_mock_session_for_refs([
        {"source_id": "si-001", "target_id": "host-001", "resolves": True},
        {"source_id": "si-002", "target_id": None, "resolves": False},
    ])
    scorer = DataQualityScorer(session=session)
    refs: list = []

    async def _run():
        from sqlalchemy import text as sa_text  # noqa: PLC0415
        await scorer._query_service_instance_refs(sa_text, refs)

    asyncio.run(_run())
    assert len(refs) == 2
    assert refs[0]["source_table"] == "shared_infrastructure.service_instance"
    assert refs[0]["resolves"] is True
    assert refs[1]["target_id"] == "NULL"
    assert refs[1]["resolves"] is False


def test_query_agent_refs_appends_rows() -> None:
    """_query_agent_refs appends one entry per returned row."""
    session = _make_mock_session_for_refs([
        {"source_id": "agent-001", "target_id": "host-001", "resolves": True},
    ])
    scorer = DataQualityScorer(session=session)
    refs: list = []

    async def _run():
        from sqlalchemy import text as sa_text  # noqa: PLC0415
        await scorer._query_agent_refs(sa_text, refs)

    asyncio.run(_run())
    assert len(refs) == 1
    assert refs[0]["source_table"] == "discovery.collector_agent"
    assert refs[0]["resolves"] is True


def test_query_service_instance_refs_none_session_raises() -> None:
    """The assert guard fires when _session is None (contract enforcement)."""
    scorer = DataQualityScorer(session=None)
    refs: list = []

    async def _run():
        from sqlalchemy import text as sa_text  # noqa: PLC0415
        await scorer._query_service_instance_refs(sa_text, refs)

    with pytest.raises(AssertionError):
        asyncio.run(_run())


def test_query_agent_refs_none_session_raises() -> None:
    """The assert guard fires when _session is None (contract enforcement)."""
    scorer = DataQualityScorer(session=None)
    refs: list = []

    async def _run():
        from sqlalchemy import text as sa_text  # noqa: PLC0415
        await scorer._query_agent_refs(sa_text, refs)

    with pytest.raises(AssertionError):
        asyncio.run(_run())
