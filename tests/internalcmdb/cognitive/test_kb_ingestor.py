"""Tests for KnowledgeBaseIngestor and its module-level text-building helpers.

Coverage targets:
- _build_tags_str     — all tag shapes (None, empty list, list, plain string)
- _build_metrics_parts — all combinations of NULL / non-NULL metric columns
- _build_host_content  — full + minimal + edge-case rows
- _walk_json_value     — dicts, lists, scalars, numeric-only skipping
- KnowledgeBaseIngestor._safe_ingest / _safe_ingest_dir — success + rollback paths
- KnowledgeBaseIngestor._ingest_hosts  — 0 rows, N rows, full metric row
- KnowledgeBaseIngestor._ingest_directory — missing dir, skip binaries, JSON flatten
- KnowledgeBaseIngestor._json_to_text  — valid JSON, invalid JSON
- KnowledgeBaseIngestor.ingest_all     — end-to-end with all stubs
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internalcmdb.cognitive.kb_ingestor import (
    KnowledgeBaseIngestor,
    _build_host_content,
    _build_metrics_parts,
    _build_tags_str,
    _walk_json_value,
)

# ---------------------------------------------------------------------------
# Fixtures / factories
# ---------------------------------------------------------------------------


def _host_row(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid host row dict; all metric fields default to None."""
    base: dict[str, Any] = {
        "host_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "host_code": "hz.test",
        "status": "Active",
        "environment": "Production",
        "tags": None,
        "cpu_usage_pct": None,
        "mem_usage_pct": None,
        "ram_used_gb": None,
        "ram_total_gb": None,
        "cpu_core_count": None,
        "cpu_model": None,
    }
    return {**base, **overrides}


def _make_session(rows: list[Any] | None = None) -> MagicMock:
    """Return a mock AsyncSession whose execute() returns *rows* via mappings().all()."""
    session = MagicMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows if rows is not None else []
    session.execute = AsyncMock(return_value=result)
    session.rollback = AsyncMock()
    return session


def _make_kb(chunk_ids: list[str] | None = None) -> MagicMock:
    """Return a mock KnowledgeBase whose embed_document returns *chunk_ids*."""
    kb = MagicMock()
    kb.embed_document = AsyncMock(return_value=chunk_ids or ["chunk-uuid-1"])
    kb._session = MagicMock()
    kb._session.rollback = AsyncMock()
    return kb


# ---------------------------------------------------------------------------
# _walk_json_value
# ---------------------------------------------------------------------------


class TestWalkJsonValue:
    def test_flat_dict_produces_lines(self) -> None:
        lines: list[str] = []
        _walk_json_value({"key": "value"}, "", lines)
        assert any("key" in line and "value" in line for line in lines)

    def test_nested_dict_dot_path(self) -> None:
        lines: list[str] = []
        _walk_json_value({"a": {"b": "deep"}}, "", lines)
        assert any("a" in line and "b" in line and "deep" in line for line in lines)

    def test_list_items_indexed(self) -> None:
        lines: list[str] = []
        _walk_json_value(["alpha", "beta"], "items: ", lines)
        assert any("alpha" in line for line in lines)
        assert any("beta" in line for line in lines)

    def test_list_capped_at_50(self) -> None:
        lines: list[str] = []
        _walk_json_value([f"item{i}" for i in range(100)], "", lines)
        # After cap: at most 50 items expanded
        matching = [line for line in lines if "item" in line]
        assert len(matching) <= 50

    def test_short_values_skipped(self) -> None:
        lines: list[str] = []
        _walk_json_value({"k": "ab"}, "", lines)  # len("ab") == 2 → skipped
        assert not any("ab" in line for line in lines)

    def test_numeric_only_values_skipped(self) -> None:
        lines: list[str] = []
        _walk_json_value({"k": "12345"}, "", lines)
        assert not any("12345" in line for line in lines)

    def test_string_with_letters_included(self) -> None:
        lines: list[str] = []
        _walk_json_value({"k": "abc123"}, "", lines)  # mixed: not digits-only
        assert any("abc123" in line for line in lines)


# ---------------------------------------------------------------------------
# _build_tags_str
# ---------------------------------------------------------------------------


class TestBuildTagsStr:
    def test_none_returns_empty_string(self) -> None:
        assert _build_tags_str(None) == ""

    def test_empty_list_returns_empty_string(self) -> None:
        assert _build_tags_str([]) == ""

    def test_list_of_strings_joined(self) -> None:
        assert _build_tags_str(["gpu", "bare-metal"]) == "gpu, bare-metal"

    def test_list_with_mixed_types_coerced(self) -> None:
        result = _build_tags_str([1, True, "worker"])
        assert "1" in result
        assert "worker" in result

    def test_plain_string_returned_verbatim(self) -> None:
        assert _build_tags_str("k8s-node") == "k8s-node"

    def test_non_list_non_string_coerced(self) -> None:
        # e.g. a JSON dict stored as tag (edge case)
        result = _build_tags_str({"role": "db"})
        assert result != ""  # anything non-empty is acceptable


# ---------------------------------------------------------------------------
# _build_metrics_parts
# ---------------------------------------------------------------------------


class TestBuildMetricsParts:
    def test_all_null_returns_empty_list(self) -> None:
        row = _host_row()
        assert _build_metrics_parts(row) == []

    def test_only_cpu_usage(self) -> None:
        row = _host_row(cpu_usage_pct=3.7)
        parts = _build_metrics_parts(row)
        assert parts == ["cpu_usage=3.7%"]

    def test_only_mem_usage_pct(self) -> None:
        row = _host_row(mem_usage_pct=42.1)
        parts = _build_metrics_parts(row)
        assert parts == ["memory_usage=42.1%"]

    def test_cpu_and_mem_usage_pct_order(self) -> None:
        row = _host_row(cpu_usage_pct=5.0, mem_usage_pct=80.0)
        parts = _build_metrics_parts(row)
        assert parts[0] == "cpu_usage=5.0%"
        assert parts[1] == "memory_usage=80.0%"

    def test_ram_used_and_total_fallback(self) -> None:
        """When mem_usage_pct is NULL but both ram_*_gb are present."""
        row = _host_row(ram_used_gb=29.8, ram_total_gb=62.9)
        parts = _build_metrics_parts(row)
        assert "ram=29.8GB/62.9GB" in parts

    def test_ram_total_only_fallback(self) -> None:
        """When ram_used_gb is NULL (hardware not reporting used), show capacity."""
        row = _host_row(ram_total_gb=125.6)
        parts = _build_metrics_parts(row)
        assert "ram_total=125.6GB" in parts

    def test_mem_pct_takes_priority_over_ram_gb(self) -> None:
        """mem_usage_pct should suppress the ram_used/total fallback branch."""
        row = _host_row(mem_usage_pct=32.3, ram_used_gb=40.6, ram_total_gb=125.6)
        parts = _build_metrics_parts(row)
        assert any("memory_usage" in p for p in parts)
        assert not any("ram=" in p for p in parts)

    def test_cpu_core_count_without_model(self) -> None:
        row = _host_row(cpu_core_count=8)
        parts = _build_metrics_parts(row)
        assert "cpu_cores=8" in parts

    def test_cpu_core_count_with_model(self) -> None:
        row = _host_row(cpu_core_count=48, cpu_model="AMD EPYC 7401P 24-Core Processor")
        parts = _build_metrics_parts(row)
        assert "cpu_cores=48 (AMD EPYC 7401P 24-Core Processor)" in parts

    def test_cpu_empty_model_string_omitted(self) -> None:
        """Empty string model is falsy — must NOT append the parenthesised suffix."""
        row = _host_row(cpu_core_count=16, cpu_model="")
        parts = _build_metrics_parts(row)
        assert parts == ["cpu_cores=16"]

    def test_all_fields_present_order(self) -> None:
        row = _host_row(
            cpu_usage_pct=4.1,
            mem_usage_pct=32.3,
            ram_used_gb=40.6,
            ram_total_gb=125.6,
            cpu_core_count=64,
            cpu_model="AMD EPYC 7502P 32-Core Processor",
        )
        parts = _build_metrics_parts(row)
        assert parts[0] == "cpu_usage=4.1%"
        assert parts[1] == "memory_usage=32.3%"
        assert parts[2] == "cpu_cores=64 (AMD EPYC 7502P 32-Core Processor)"
        assert len(parts) == 3  # ram_* suppressed by mem_usage_pct


# ---------------------------------------------------------------------------
# _build_host_content
# ---------------------------------------------------------------------------


class TestBuildHostContent:
    def test_minimal_row_format(self) -> None:
        row = _host_row()
        content = _build_host_content(row)
        assert content == "Host hz.test: status=Active, environment=Production"

    def test_null_status_shows_unknown(self) -> None:
        row = _host_row(status=None)
        assert "status=unknown" in _build_host_content(row)

    def test_null_environment_shows_unknown(self) -> None:
        row = _host_row(environment=None)
        assert "environment=unknown" in _build_host_content(row)

    def test_tags_appended(self) -> None:
        row = _host_row(tags=["gpu", "bare-metal"])
        content = _build_host_content(row)
        assert "tags=gpu, bare-metal" in content

    def test_metrics_appended(self) -> None:
        row = _host_row(cpu_usage_pct=1.0, ram_total_gb=62.9, cpu_core_count=8)
        content = _build_host_content(row)
        assert "cpu_usage=1.0%" in content
        assert "ram_total=62.9GB" in content
        assert "cpu_cores=8" in content

    def test_no_trailing_comma_when_no_tags_no_metrics(self) -> None:
        content = _build_host_content(_host_row())
        assert not content.endswith(",")
        assert ", " not in content.split("environment=Production")[1]

    def test_full_row_content_string(self) -> None:
        row = _host_row(
            host_code="hz.164",
            status="Active",
            environment="Production",
            tags=["storage"],
            cpu_usage_pct=4.1,
            mem_usage_pct=32.3,
            cpu_core_count=64,
            cpu_model="AMD EPYC 7502P 32-Core Processor",
        )
        content = _build_host_content(row)
        assert "Host hz.164:" in content
        assert "tags=storage" in content
        assert "cpu_usage=4.1%" in content
        assert "memory_usage=32.3%" in content
        assert "cpu_cores=64 (AMD EPYC 7502P 32-Core Processor)" in content


# ---------------------------------------------------------------------------
# KnowledgeBaseIngestor._safe_ingest / _safe_ingest_dir
# ---------------------------------------------------------------------------


class TestSafeIngest:
    @pytest.mark.asyncio
    async def test_success_returns_count(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        session = _make_session()
        kb = _make_kb()
        fn = AsyncMock(return_value=7)
        result = await ingestor._safe_ingest("test", fn, session, kb)
        assert result == 7

    @pytest.mark.asyncio
    async def test_exception_triggers_rollback_returns_zero(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        session = _make_session()
        kb = _make_kb()
        fn = AsyncMock(side_effect=RuntimeError("DB exploded"))
        result = await ingestor._safe_ingest("test", fn, session, kb)
        assert result == 0
        session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_failure_still_returns_zero(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        session = _make_session()
        session.rollback = AsyncMock(side_effect=RuntimeError("rollback failed too"))
        kb = _make_kb()
        fn = AsyncMock(side_effect=RuntimeError("initial error"))
        # Must not raise — swallows both errors
        result = await ingestor._safe_ingest("test", fn, session, kb)
        assert result == 0

    @pytest.mark.asyncio
    async def test_safe_ingest_dir_missing_directory_returns_zero(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        kb = _make_kb()
        result = await ingestor._safe_ingest_dir(
            "docs", kb, Path("/nonexistent/path/xyz"), "docs"
        )
        assert result == 0


# ---------------------------------------------------------------------------
# KnowledgeBaseIngestor._ingest_hosts
# ---------------------------------------------------------------------------


class TestIngestHosts:
    @pytest.mark.asyncio
    async def test_zero_rows_returns_zero(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        session = _make_session(rows=[])
        kb = _make_kb()
        result = await ingestor._ingest_hosts(session, kb)
        assert result == 0
        kb.embed_document.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_single_row_minimal_embeds_once(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        session = _make_session(rows=[_host_row()])
        kb = _make_kb(chunk_ids=["c1"])
        result = await ingestor._ingest_hosts(session, kb)
        assert result == 1
        kb.embed_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_rows_accumulates_count(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        rows = [_host_row(host_code=f"hz.{i}", host_id=f"uuid-{i}") for i in range(5)]
        session = _make_session(rows=rows)
        kb = _make_kb(chunk_ids=["c1"])
        result = await ingestor._ingest_hosts(session, kb)
        assert result == 5
        assert kb.embed_document.await_count == 5

    @pytest.mark.asyncio
    async def test_embed_called_with_correct_metadata(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        row = _host_row(host_id="host-uuid-42", host_code="hz.99")
        session = _make_session(rows=[row])
        kb = _make_kb()
        await ingestor._ingest_hosts(session, kb)
        call_kwargs = kb.embed_document.call_args
        meta = call_kwargs.args[1]
        assert meta["source"] == "cmdb_host"
        assert meta["host_id"] == "host-uuid-42"
        assert meta["host_code"] == "hz.99"

    @pytest.mark.asyncio
    async def test_full_metrics_row_content_correct(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        row = _host_row(
            cpu_usage_pct=4.1,
            mem_usage_pct=32.3,
            cpu_core_count=64,
            cpu_model="AMD EPYC 7502P 32-Core Processor",
        )
        session = _make_session(rows=[row])
        kb = _make_kb()
        await ingestor._ingest_hosts(session, kb)
        content_passed = kb.embed_document.call_args.args[0]
        assert "cpu_usage=4.1%" in content_passed
        assert "memory_usage=32.3%" in content_passed
        assert "cpu_cores=64 (AMD EPYC 7502P 32-Core Processor)" in content_passed

    @pytest.mark.asyncio
    async def test_embed_returning_multiple_chunks_counted(self) -> None:
        """embed_document may split a long document into multiple chunks."""
        ingestor = KnowledgeBaseIngestor()
        session = _make_session(rows=[_host_row()])
        kb = _make_kb(chunk_ids=["c1", "c2", "c3"])
        result = await ingestor._ingest_hosts(session, kb)
        assert result == 3


# ---------------------------------------------------------------------------
# KnowledgeBaseIngestor._ingest_directory
# ---------------------------------------------------------------------------


class TestIngestDirectory:
    @pytest.mark.asyncio
    async def test_nonexistent_directory_returns_zero(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        kb = _make_kb()
        result = await ingestor._ingest_directory(
            kb, Path("/no/such/dir"), source_tag="docs"
        )
        assert result == 0
        kb.embed_document.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_markdown_file_embedded(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        kb = _make_kb()
        with tempfile.TemporaryDirectory() as tmpdir:
            md = Path(tmpdir) / "README.md"
            md.write_text("# Title\nSome content here.", encoding="utf-8")
            with patch("internalcmdb.cognitive.kb_ingestor._REPO_ROOT", Path(tmpdir)):
                result = await ingestor._ingest_directory(
                    kb, Path(tmpdir), source_tag="docs"
                )
        assert result >= 1
        kb.embed_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_file_skipped(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        kb = _make_kb()
        with tempfile.TemporaryDirectory() as tmpdir:
            empty = Path(tmpdir) / "empty.md"
            empty.write_text("   \n\t\n   ", encoding="utf-8")
            result = await ingestor._ingest_directory(
                kb, Path(tmpdir), source_tag="docs"
            )
        assert result == 0
        kb.embed_document.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unsupported_extension_skipped(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        kb = _make_kb()
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "image.png"
            binary.write_bytes(b"\x89PNG\r\n")
            result = await ingestor._ingest_directory(
                kb, Path(tmpdir), source_tag="docs"
            )
        assert result == 0
        kb.embed_document.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_json_file_flattened_before_embed(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        kb = _make_kb()
        data = {"host": "hz.test", "status": "active", "cpu": "EPYC processor"}
        with tempfile.TemporaryDirectory() as tmpdir:
            jf = Path(tmpdir) / "data.json"
            jf.write_text(json.dumps(data), encoding="utf-8")
            with patch("internalcmdb.cognitive.kb_ingestor._REPO_ROOT", Path(tmpdir)):
                await ingestor._ingest_directory(kb, Path(tmpdir), source_tag="docs")
        content_passed = kb.embed_document.call_args.args[0]
        # Flattened text should contain the string value "EPYC processor"
        assert "EPYC processor" in content_passed

    @pytest.mark.asyncio
    async def test_json_file_with_only_numeric_values_skipped(self) -> None:
        """JSON that flattens to empty (all short numerics) must be skipped."""
        ingestor = KnowledgeBaseIngestor()
        kb = _make_kb()
        data = {"a": 1, "b": 2}  # all numeric-only → _walk_json_value skips them
        with tempfile.TemporaryDirectory() as tmpdir:
            jf = Path(tmpdir) / "nums.json"
            jf.write_text(json.dumps(data), encoding="utf-8")
            result = await ingestor._ingest_directory(
                kb, Path(tmpdir), source_tag="docs"
            )
        assert result == 0
        kb.embed_document.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_metadata_contains_relative_file_path(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        kb = _make_kb()
        with tempfile.TemporaryDirectory() as tmpdir:
            doc = Path(tmpdir) / "notes.md"
            doc.write_text("Some important notes here", encoding="utf-8")
            with patch("internalcmdb.cognitive.kb_ingestor._REPO_ROOT", Path(tmpdir)):
                await ingestor._ingest_directory(kb, Path(tmpdir), source_tag="docs")
        meta = kb.embed_document.call_args.args[1]
        assert meta["source"] == "docs"
        assert "notes.md" in meta["file"]


# ---------------------------------------------------------------------------
# KnowledgeBaseIngestor._json_to_text
# ---------------------------------------------------------------------------


class TestJsonToText:
    def test_valid_flat_json_produces_text(self) -> None:
        raw = json.dumps({"name": "hz.test", "role": "worker node"})
        result = KnowledgeBaseIngestor._json_to_text(raw)
        assert "worker node" in result

    def test_invalid_json_returned_verbatim(self) -> None:
        raw = "not { json at all"
        result = KnowledgeBaseIngestor._json_to_text(raw)
        assert result == raw

    def test_nested_json_flattened(self) -> None:
        raw = json.dumps({"outer": {"inner": "deep value here"}})
        result = KnowledgeBaseIngestor._json_to_text(raw)
        assert "deep value here" in result

    def test_json_array_flattened(self) -> None:
        raw = json.dumps(["alpha entry", "beta entry"])
        result = KnowledgeBaseIngestor._json_to_text(raw)
        assert "alpha entry" in result
        assert "beta entry" in result


# ---------------------------------------------------------------------------
# KnowledgeBaseIngestor.ingest_all — integration-level stub
# ---------------------------------------------------------------------------


class TestIngestAll:
    @pytest.mark.asyncio
    async def test_returns_expected_keys(self) -> None:
        """ingest_all must always return a dict with all 6 keys."""
        ingestor = KnowledgeBaseIngestor()
        session = _make_session(rows=[])
        llm = MagicMock()
        llm.embed = AsyncMock(return_value=[[0.1] * 4096])

        # Patch all 5 source methods to avoid real DB / filesystem access
        for attr in ("_ingest_hosts", "_ingest_services", "_ingest_insights"):
            setattr(
                ingestor,
                attr,
                AsyncMock(return_value=0),
            )

        # _safe_ingest_dir also needs patching since docs/subprojects may not exist
        ingestor._safe_ingest_dir = AsyncMock(return_value=0)  # type: ignore[method-assign]

        result = await ingestor.ingest_all(session, llm)
        assert set(result.keys()) == {
            "hosts", "services", "insights", "docs", "subprojects", "total"
        }

    @pytest.mark.asyncio
    async def test_total_is_sum_of_sources(self) -> None:
        ingestor = KnowledgeBaseIngestor()
        session = _make_session(rows=[])
        llm = MagicMock()

        ingestor._safe_ingest = AsyncMock(side_effect=[3, 5, 11])  # type: ignore[method-assign]
        ingestor._safe_ingest_dir = AsyncMock(side_effect=[47, 12])  # type: ignore[method-assign]

        result = await ingestor.ingest_all(session, llm)
        assert result["total"] == 3 + 5 + 11 + 47 + 12
