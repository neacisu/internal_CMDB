"""Tests for the cognitive router (async get_async_session, RBAC bypassed in dev mode)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.routers.cognitive import (
    _label_file_source,
    _label_insight,
    _parse_container_counts,
    _parse_cpu_pct,
    _parse_mem_pct,
    _parse_root_disk_pct,
    _source_label,
)
from internalcmdb.api.routers.cognitive import (
    router as cognitive_router,
)


def _approx(expected: float, *, rel: float | None = None, abs_tol: float | None = None) -> Any:
    """Typed wrapper for pytest.approx — centralises the single Pylance stub gap."""
    return pytest.approx(expected, rel=rel, abs=abs_tol)  # pyright: ignore[reportUnknownMemberType]


async def _empty_session():
    """Async session mock returning empty results for all queries."""
    session = AsyncMock()
    empty_result = MagicMock()
    empty_result.fetchall.return_value = []
    empty_result.fetchone.return_value = None
    empty_result.rowcount = 0
    session.execute = AsyncMock(return_value=empty_result)
    session.commit = AsyncMock()
    yield session


def _make_app(session_factory: Callable[..., Any] | None = None) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_async_session] = session_factory or _empty_session
    app.include_router(cognitive_router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# POST /cognitive/query
# ---------------------------------------------------------------------------


def test_cognitive_query_returns_answer() -> None:
    """POST /query returns a response with an 'answer' field (engine may be unavailable)."""
    client = TestClient(_make_app())
    r = client.post(
        "/api/v1/cognitive/query",
        json={"question": "How many hosts are online?", "top_k": 5},
    )

    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0


def test_cognitive_query_calls_engine() -> None:
    """POST /query returns an NLQueryResponse structure regardless of engine state."""
    client = TestClient(_make_app())
    r = client.post(
        "/api/v1/cognitive/query",
        json={"question": "What is the fleet status?"},
    )

    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "sources" in data
    assert "confidence" in data
    assert isinstance(data["sources"], list)


def test_cognitive_query_invalid_empty_question() -> None:
    """Returns 422 for an empty question (min_length=1 validation)."""
    client = TestClient(_make_app())
    r = client.post("/api/v1/cognitive/query", json={"question": ""})

    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /cognitive/insights
# ---------------------------------------------------------------------------


def test_cognitive_insights_empty() -> None:
    """Returns an empty list when no active insights exist."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/insights")

    assert r.status_code == 200
    assert r.json() == []


def test_cognitive_insights_invalid_status() -> None:
    """Returns 422 for an invalid status filter value."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/insights", params={"status": "invalid_status"})

    assert r.status_code == 422


def test_cognitive_insights_valid_statuses() -> None:
    """Accepts acknowledged and dismissed as valid status values."""
    client = TestClient(_make_app())
    for status in ("active", "acknowledged", "dismissed"):
        r = client.get("/api/v1/cognitive/insights", params={"status": status})
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# GET /cognitive/reports
# ---------------------------------------------------------------------------


def test_cognitive_reports_empty() -> None:
    """Returns an empty list when no reports have been generated."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/reports")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /cognitive/drift/results
# ---------------------------------------------------------------------------


def test_cognitive_drift_empty() -> None:
    """Returns an empty list when no drift results are stored."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/drift/results")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /cognitive/self-heal/playbooks
# ---------------------------------------------------------------------------


def test_cognitive_playbooks_returns_list() -> None:
    """Returns a list of playbooks (empty when DB has no active playbooks)."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/self-heal/playbooks")

    assert r.status_code == 200
    playbooks = r.json()
    assert isinstance(playbooks, list)


def test_cognitive_playbooks_fallback_on_error() -> None:
    """Falls back to hard-coded defaults when the DB raises an exception."""

    async def _session_with_error():
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("table does not exist"))
        yield session

    client = TestClient(_make_app(_session_with_error))
    r = client.get("/api/v1/cognitive/self-heal/playbooks")

    assert r.status_code == 200
    _playbooks_raw: Any = r.json()
    assert isinstance(_playbooks_raw, list)
    playbooks = cast(list[Any], _playbooks_raw)
    assert len(playbooks) >= 1
    for pb in playbooks:
        assert "playbook_id" in pb
        assert "name" in pb


# ---------------------------------------------------------------------------
# GET /cognitive/self-heal/history
# ---------------------------------------------------------------------------


def test_cognitive_self_heal_history_empty() -> None:
    """Returns an empty list when no self-healing actions have been executed."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/self-heal/history")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /cognitive/health-scores
# ---------------------------------------------------------------------------


def test_cognitive_health_scores_empty() -> None:
    """Returns an empty list when no hosts have snapshot data."""
    client = TestClient(_make_app())
    r = client.get("/api/v1/cognitive/health-scores")

    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# InsightOut schema — evidence field type contract
# ---------------------------------------------------------------------------


def test_insight_out_evidence_defaults_to_empty_list() -> None:
    """InsightOut.evidence must default to [] with element type list[dict[str, Any]].

    Regression test for the Pylance reportUnknownVariableType error that was
    triggered by Field(default_factory=list) yielding list[Unknown] in strict
    mode.  The fix changed the field to a mutable default [] (safe in Pydantic
    v2 because Pydantic copies mutable defaults) and the annotation
    list[dict[str, Any]] now governs inference unambiguously.
    """
    from internalcmdb.api.routers.cognitive import InsightOut  # noqa: PLC0415

    out = InsightOut(
        insight_id="test-id",
        entity_id="entity-1",
        entity_type="host",
    )
    assert out.evidence == []
    assert isinstance(out.evidence, list)


def test_insight_out_evidence_accepts_typed_dicts() -> None:
    """InsightOut.evidence accepts a list of dict[str, Any] entries."""
    from internalcmdb.api.routers.cognitive import InsightOut  # noqa: PLC0415

    evidence: list[dict[str, Any]] = [
        {"type": "anomaly", "score": 0.95},
        {"type": "drift", "field": "cpu_model"},
    ]
    out = InsightOut(insight_id="test-id", evidence=evidence)
    assert len(out.evidence) == 2
    assert out.evidence[0]["type"] == "anomaly"


def test_insight_out_evidence_instances_are_independent() -> None:
    """Pydantic v2 mutable default must NOT share state between instances."""
    from internalcmdb.api.routers.cognitive import InsightOut  # noqa: PLC0415

    a = InsightOut(insight_id="a")
    b = InsightOut(insight_id="b")
    # Mutation of one instance must not affect the other.
    a.evidence.append({"x": 1})
    assert b.evidence == []


# ---------------------------------------------------------------------------
# JSONB payload helper functions — unit tests for cast-safe parsing
# ---------------------------------------------------------------------------


class TestParseCpuPct:
    """_parse_cpu_pct covers the cpu_times dict cast (reportUnknownVariableType fix)."""

    def test_no_cpu_data_returns_zero(self) -> None:
        assert _parse_cpu_pct({}) == _approx(0.0)

    def test_none_cpu_times_returns_zero(self) -> None:
        assert _parse_cpu_pct({"cpu_times": None}) == _approx(0.0)

    def test_typical_linux_cpu_times(self) -> None:
        payload: dict[str, Any] = {
            "cpu_times": {"user": 100, "system": 20, "idle": 380, "iowait": 0}
        }
        pct = _parse_cpu_pct(payload)
        # idle=380, total=500 → cpu_pct=(500-380)/500*100 = 24.0
        assert abs(pct - 24.0) < 0.01

    def test_all_idle_returns_zero(self) -> None:
        payload: dict[str, Any] = {"cpu_times": {"idle": 1000}}
        assert _parse_cpu_pct(payload) == _approx(0.0)

    def test_saturated_cpu_capped_at_100(self) -> None:
        payload: dict[str, Any] = {"cpu_times": {"user": 9999, "idle": 0}}
        assert _parse_cpu_pct(payload) == _approx(100.0)

    def test_string_values_in_cpu_times(self) -> None:
        """JSONB may return numeric values as strings; must not raise."""
        payload: dict[str, Any] = {"cpu_times": {"user": "50", "idle": "50"}}
        pct = _parse_cpu_pct(payload)
        assert 0.0 <= pct <= 100.0


class TestParseMemPct:
    """_parse_mem_pct covers the memory_kb dict cast (reportUnknownVariableType fix)."""

    def test_no_mem_data_returns_zero(self) -> None:
        assert _parse_mem_pct({}) == _approx(0.0)

    def test_none_memory_kb_returns_zero(self) -> None:
        assert _parse_mem_pct({"memory_kb": None}) == _approx(0.0)

    def test_typical_8gb_host(self) -> None:
        payload: dict[str, Any] = {"memory_kb": {"MemTotal": 8_000_000, "MemAvailable": 4_000_000}}
        pct = _parse_mem_pct(payload)
        assert abs(pct - 50.0) < 0.01

    def test_memfree_fallback_when_memavailable_absent(self) -> None:
        payload: dict[str, Any] = {"memory_kb": {"MemTotal": 4_000_000, "MemFree": 1_000_000}}
        pct = _parse_mem_pct(payload)
        assert abs(pct - 75.0) < 0.01

    def test_zero_total_returns_zero(self) -> None:
        payload: dict[str, Any] = {"memory_kb": {"MemTotal": 0}}
        assert _parse_mem_pct(payload) == _approx(0.0)


class TestParseRootDiskPct:
    """_parse_root_disk_pct covers the disks list cast (reportUnknownVariableType fix)."""

    def test_no_disk_data_returns_zero(self) -> None:
        assert _parse_root_disk_pct({}) == _approx(0.0)

    def test_none_disks_returns_zero(self) -> None:
        assert _parse_root_disk_pct({"disks": None}) == _approx(0.0)

    def test_empty_disks_list_returns_zero(self) -> None:
        assert _parse_root_disk_pct({"disks": []}) == _approx(0.0)

    def test_root_partition_found(self) -> None:
        payload: dict[str, Any] = {
            "disks": [
                {"mountpoint": "/boot", "used_pct": "10%"},
                {"mountpoint": "/", "used_pct": "72%"},
                {"mountpoint": "/data", "used_pct": "55%"},
            ]
        }
        assert _parse_root_disk_pct(payload) == _approx(72.0)

    def test_no_root_partition_returns_zero(self) -> None:
        payload: dict[str, Any] = {"disks": [{"mountpoint": "/data", "used_pct": "40%"}]}
        assert _parse_root_disk_pct(payload) == _approx(0.0)

    def test_invalid_pct_string_returns_zero(self) -> None:
        payload: dict[str, Any] = {"disks": [{"mountpoint": "/", "used_pct": "N/A"}]}
        assert _parse_root_disk_pct(payload) == _approx(0.0)

    def test_numeric_used_pct_without_percent_sign(self) -> None:
        payload: dict[str, Any] = {"disks": [{"mountpoint": "/", "used_pct": 85}]}
        assert _parse_root_disk_pct(payload) == _approx(85.0)


class TestParseContainerCounts:
    """_parse_container_counts covers the containers list cast (reportUnknownVariableType fix)."""

    def test_no_docker_data_returns_zeros(self) -> None:
        total, running = _parse_container_counts({})
        assert total == 0
        assert running == 0

    def test_none_containers_returns_zeros(self) -> None:
        total, running = _parse_container_counts({"containers": None})
        assert total == 0
        assert running == 0

    def test_all_running_containers(self) -> None:
        payload: dict[str, Any] = {
            "containers": [
                {"id": "abc", "status": "Up 2 hours"},
                {"id": "def", "status": "Up 5 minutes"},
            ]
        }
        total, running = _parse_container_counts(payload)
        assert total == 2
        assert running == 2

    def test_mixed_running_and_stopped(self) -> None:
        payload: dict[str, Any] = {
            "containers": [
                {"id": "a", "status": "Up 1 hour"},
                {"id": "b", "status": "Exited (1) 3 minutes ago"},
                {"id": "c", "status": "Up 30 seconds"},
            ]
        }
        total, running = _parse_container_counts(payload)
        assert total == 3
        assert running == 2

    def test_non_dict_items_in_containers_are_skipped(self) -> None:
        """Non-dict items must not cause a crash — isinstance guard is the fix."""
        payload: dict[str, Any] = {"containers": ["string-item", 42, None, {"status": "Up 1 min"}]}
        total, running = _parse_container_counts(payload)
        assert total == 4
        assert running == 1


# ---------------------------------------------------------------------------
# Insight CRUD endpoints — rowcount / CursorResult contract
# ---------------------------------------------------------------------------


def test_acknowledge_insight_not_found() -> None:
    """POST /insights/{id}/ack returns 404 when rowcount == 0 (no active insight matched).

    This test exercises the CursorResult.rowcount path that was previously
    reported as reportAttributeAccessIssue / reportUnknownMemberType because
    AsyncSession.execute() is typed as returning Result[Any] (which lacks
    rowcount in its base class), not the concrete CursorResult subclass.
    The fix: cast() to CursorResult[Any] before accessing .rowcount.
    """

    async def _session_rowcount_zero():
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()
        yield session

    client = TestClient(_make_app(_session_rowcount_zero))
    r = client.post(
        "/api/v1/cognitive/insights/non-existent-id/ack",
        json={"acknowledged_by": "admin"},
    )
    assert r.status_code == 404


def test_acknowledge_insight_success() -> None:
    """POST /insights/{id}/ack returns 200 with status=acknowledged on rowcount > 0."""

    async def _session_rowcount_one():
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()
        yield session

    client = TestClient(_make_app(_session_rowcount_one))
    r = client.post(
        "/api/v1/cognitive/insights/existing-id/ack",
        json={"acknowledged_by": "admin"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "acknowledged"
    assert data["insight_id"] == "existing-id"


def test_dismiss_insight_not_found() -> None:
    """POST /insights/{id}/dismiss returns 404 when rowcount == 0."""

    async def _session_rowcount_zero():
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()
        yield session

    client = TestClient(_make_app(_session_rowcount_zero))
    r = client.post(
        "/api/v1/cognitive/insights/non-existent-id/dismiss",
        json={"dismissed_by": "admin", "reason": "false positive"},
    )
    assert r.status_code == 404


def test_dismiss_insight_success() -> None:
    """POST /insights/{id}/dismiss returns 200 with status=dismissed on rowcount > 0."""

    async def _session_rowcount_one():
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()
        yield session

    client = TestClient(_make_app(_session_rowcount_one))
    r = client.post(
        "/api/v1/cognitive/insights/some-id/dismiss",
        json={"dismissed_by": "operator", "reason": "resolved manually"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "dismissed"


# ---------------------------------------------------------------------------
# analyze_host — AnalysisResult type contract (anomalies: list[AnalysisResult])
# ---------------------------------------------------------------------------


def test_analyze_host_returns_analysis_out_no_db() -> None:
    """POST /analyze/host/{host_id} returns AnalysisOut even when DB has no facts.

    Exercises the anomalies: list[AnalysisResult] annotation path — an empty
    DB result means no anomalies, so worst is None and the defaults apply.
    """

    async def _session_no_facts():
        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute = AsyncMock(return_value=result)
        yield session

    client = TestClient(_make_app(_session_no_facts))
    import uuid  # noqa: PLC0415

    host_id = str(uuid.uuid4())
    r = client.post(f"/api/v1/cognitive/analyze/host/{host_id}")

    assert r.status_code == 200
    data = r.json()
    assert data["entity_type"] == "host"
    assert data["entity_id"] == host_id
    assert isinstance(data["is_anomaly"], bool)
    assert isinstance(data["confidence"], float)
    assert isinstance(data["severity"], str)


def test_analyze_host_graceful_with_invalid_uuid() -> None:
    """POST /analyze/host/{id} returns 422 for a non-UUID host_id."""
    client = TestClient(_make_app())
    r = client.post("/api/v1/cognitive/analyze/host/not-a-uuid")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# _source_label — unit tests for the source chunk label builder
# ---------------------------------------------------------------------------


class TestSourceLabel:
    """Full coverage of _source_label across all source types and edge cases."""

    def test_cmdb_host_with_host_code(self) -> None:
        s = {"metadata": {"source": "cmdb_host", "host_code": "hz.164"}}
        assert _source_label(s) == "hz.164"

    def test_cmdb_host_missing_host_code_falls_back(self) -> None:
        s = {"metadata": {"source": "cmdb_host", "host_code": None}}
        assert _source_label(s) == "host"

    def test_cmdb_host_empty_host_code_falls_back(self) -> None:
        s = {"metadata": {"source": "cmdb_host", "host_code": ""}}
        assert _source_label(s) == "host"

    def test_cmdb_service_with_service_code(self) -> None:
        s = {"metadata": {"source": "cmdb_service", "service_code": "svc-auth"}}
        assert _source_label(s) == "svc-auth"

    def test_cmdb_service_missing_service_code_falls_back(self) -> None:
        s = {"metadata": {"source": "cmdb_service", "service_code": None}}
        assert _source_label(s) == "service"

    def test_cognitive_insight_with_category_and_severity(self) -> None:
        s = {"metadata": {
            "source": "cognitive_insight", "category": "capacity", "severity": "warning",
        }}
        assert _source_label(s) == "capacity/warning"

    def test_cognitive_insight_no_severity_returns_category_only(self) -> None:
        s = {"metadata": {"source": "cognitive_insight", "category": "reliability", "severity": ""}}
        assert _source_label(s) == "reliability"

    def test_cognitive_insight_missing_category_defaults(self) -> None:
        s = {"metadata": {"source": "cognitive_insight"}}
        assert _source_label(s) == "insight"

    def test_cognitive_insight_missing_severity_defaults(self) -> None:
        s = {"metadata": {"source": "cognitive_insight", "category": "availability"}}
        assert _source_label(s) == "availability"

    def test_docs_source_returns_basename_without_extension(self) -> None:
        s = {"metadata": {"source": "docs", "file": "docs/runbooks/deploy.md"}}
        assert _source_label(s) == "deploy"

    def test_docs_source_nested_path(self) -> None:
        s = {"metadata": {"source": "docs", "file": "docs/adr/ADR-001-storage.md"}}
        assert _source_label(s) == "ADR-001-storage"

    def test_docs_source_no_file_returns_source_tag(self) -> None:
        s = {"metadata": {"source": "docs", "file": None}}
        assert _source_label(s) == "docs"

    def test_docs_source_empty_file_returns_source_tag(self) -> None:
        s = {"metadata": {"source": "docs", "file": ""}}
        assert _source_label(s) == "docs"

    def test_subprojects_source_json_file(self) -> None:
        s = {"metadata": {"source": "subprojects", "file": "subprojects/audit_result.json"}}
        assert _source_label(s) == "audit_result"

    def test_unknown_source_uses_section_field(self) -> None:
        s = {"section": "capacity/info", "metadata": {"source": "unknown_type"}}
        assert _source_label(s) == "capacity/info"

    def test_unknown_source_no_section_uses_source_tag(self) -> None:
        s = {"metadata": {"source": "custom_source"}}
        assert _source_label(s) == "custom_source"

    def test_no_metadata_at_all_uses_section(self) -> None:
        s = {"section": "my-section"}
        assert _source_label(s) == "my-section"

    def test_no_metadata_no_section_returns_literal_source(self) -> None:
        s: dict[str, Any] = {}
        assert _source_label(s) == "source"

    def test_metadata_none_falls_through_to_section(self) -> None:
        s = {"metadata": None, "section": "fallback"}
        assert _source_label(s) == "fallback"

    def test_all_strings_returned_are_str(self) -> None:
        """Every code path must return a plain str, never None, int, or other types."""
        cases = [
            {"metadata": {"source": "cmdb_host", "host_code": "hz.1"}},
            {"metadata": {"source": "cmdb_service", "service_code": "svc-x"}},
            {"metadata": {"source": "cognitive_insight", "category": "cap", "severity": "crit"}},
            {"metadata": {"source": "docs", "file": "docs/readme.md"}},
            {"metadata": {"source": "subprojects", "file": "sub/report.json"}},
            {"section": "my-sec"},
            {},
        ]
        for c in cases:
            result = _source_label(c)
            assert isinstance(result, str), f"Expected str, got {type(result)} for {c}"
            assert len(result) > 0, f"Expected non-empty string for {c}"


# ---------------------------------------------------------------------------
# _label_insight — unit tests for the extracted cognitive_insight helper
# ---------------------------------------------------------------------------


class TestLabelInsight:
    """Direct unit tests for _label_insight(meta) — the extracted helper."""

    def test_category_and_severity_combined(self) -> None:
        assert _label_insight({"category": "capacity", "severity": "warning"}) == "capacity/warning"

    def test_severity_critical(self) -> None:
        meta = {"category": "reliability", "severity": "critical"}
        assert _label_insight(meta) == "reliability/critical"

    def test_empty_severity_returns_category_only(self) -> None:
        assert _label_insight({"category": "availability", "severity": ""}) == "availability"

    def test_none_severity_returns_category_only(self) -> None:
        assert _label_insight({"category": "capacity", "severity": None}) == "capacity"

    def test_missing_severity_key_returns_category_only(self) -> None:
        assert _label_insight({"category": "reliability"}) == "reliability"

    def test_missing_category_defaults_to_insight(self) -> None:
        assert _label_insight({}) == "insight"

    def test_none_category_defaults_to_insight(self) -> None:
        assert _label_insight({"category": None}) == "insight"

    def test_always_returns_str(self) -> None:
        for meta in [
            {"category": "cap", "severity": "warn"},
            {"category": "cap"},
            {"severity": "warn"},
            {},
        ]:
            result = _label_insight(meta)
            assert isinstance(result, str)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# _label_file_source — unit tests for the extracted docs/subprojects helper
# ---------------------------------------------------------------------------


class TestLabelFileSource:
    """Direct unit tests for _label_file_source(meta, src) — the extracted helper."""

    def test_markdown_file_returns_stem(self) -> None:
        assert _label_file_source({"file": "docs/runbooks/deploy.md"}, "docs") == "deploy"

    def test_json_file_returns_stem(self) -> None:
        result = _label_file_source({"file": "subprojects/audit_result.json"}, "subprojects")
        assert result == "audit_result"

    def test_nested_path_returns_only_stem(self) -> None:
        assert _label_file_source({"file": "a/b/c/deep-doc.md"}, "docs") == "deep-doc"

    def test_file_with_multiple_dots_only_removes_last_extension(self) -> None:
        assert _label_file_source({"file": "docs/report.v2.md"}, "docs") == "report.v2"

    def test_empty_file_falls_back_to_src(self) -> None:
        assert _label_file_source({"file": ""}, "docs") == "docs"
        assert _label_file_source({"file": ""}, "subprojects") == "subprojects"

    def test_none_file_falls_back_to_src(self) -> None:
        assert _label_file_source({"file": None}, "docs") == "docs"

    def test_missing_file_key_falls_back_to_src(self) -> None:
        assert _label_file_source({}, "subprojects") == "subprojects"

    def test_always_returns_str(self) -> None:
        for meta, src in [
            ({"file": "docs/x.md"}, "docs"),
            ({"file": None}, "docs"),
            ({}, "subprojects"),
        ]:
            result = _label_file_source(meta, src)
            assert isinstance(result, str)
            assert len(result) > 0
