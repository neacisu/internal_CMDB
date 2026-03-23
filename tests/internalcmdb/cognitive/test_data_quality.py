"""Unit tests for data quality freshness helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from internalcmdb.cognitive.data_quality import (
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
