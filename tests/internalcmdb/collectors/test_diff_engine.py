"""Tests for the diff engine."""

from __future__ import annotations

from internalcmdb.collectors.diff_engine import (
    compute_diff_with_summary,
    compute_json_diff,
    generate_summary,
    payload_hash,
)


class TestComputeJsonDiff:
    def test_identical_dicts(self) -> None:
        old = {"a": 1, "b": 2}
        assert compute_json_diff(old, old.copy()) == []

    def test_added_key(self) -> None:
        old = {"a": 1}
        new = {"a": 1, "b": 2}
        ops = compute_json_diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "add"
        assert ops[0]["path"] == "/b"
        assert ops[0]["value"] == 2

    def test_removed_key(self) -> None:
        old = {"a": 1, "b": 2}
        new = {"a": 1}
        ops = compute_json_diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "remove"
        assert ops[0]["path"] == "/b"

    def test_changed_value(self) -> None:
        old = {"a": 1}
        new = {"a": 2}
        ops = compute_json_diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "replace"
        assert ops[0]["value"] == 2

    def test_nested_change(self) -> None:
        old = {"a": {"b": 1}}
        new = {"a": {"b": 2}}
        ops = compute_json_diff(old, new)
        assert len(ops) == 1
        assert ops[0]["path"] == "/a/b"

    def test_list_change(self) -> None:
        old = {"a": [1, 2, 3]}
        new = {"a": [1, 2, 3, 4]}
        ops = compute_json_diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "replace"

    def test_mixed_operations(self) -> None:
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 99, "d": 4}
        ops = compute_json_diff(old, new)
        assert len(ops) == 3  # replace b, remove c, add d


class TestGenerateSummary:
    def test_no_changes(self) -> None:
        assert generate_summary([]) == "No changes"

    def test_with_adds(self) -> None:
        ops = [{"op": "add", "path": "/foo", "value": 1}]
        summary = generate_summary(ops)
        assert "1 added" in summary
        assert "foo" in summary

    def test_with_removes(self) -> None:
        ops = [{"op": "remove", "path": "/bar"}]
        summary = generate_summary(ops)
        assert "1 removed" in summary

    def test_truncation_at_3(self) -> None:
        ops = [{"op": "add", "path": f"/key{i}", "value": i} for i in range(5)]
        summary = generate_summary(ops)
        assert "+2 more" in summary


class TestComputeDiffWithSummary:
    def test_combined(self) -> None:
        old = {"a": 1}
        new = {"a": 2, "b": 3}
        ops, summary = compute_diff_with_summary(old, new)
        assert len(ops) == 2
        assert summary


class TestPayloadHash:
    def test_deterministic(self) -> None:
        data = {"b": 2, "a": 1}
        h1 = payload_hash(data)
        h2 = payload_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_payloads(self) -> None:
        assert payload_hash({"a": 1}) != payload_hash({"a": 2})
