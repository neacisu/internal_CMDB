"""Diff engine — compute RFC 6902 JSON Patches and human-readable summaries."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast


def compute_json_diff(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute a simplified JSON diff (RFC 6902 inspired).

    Returns a list of operations: add, remove, replace.
    Does not require deepdiff/jsonpatch — pure-Python for agent deployability.
    """
    ops: list[dict[str, Any]] = []
    _diff_recursive(old, new, "", ops)
    return ops


def _diff_recursive(
    old: Any,
    new: Any,
    path: str,
    ops: list[dict[str, Any]],
) -> None:
    """Recursively compare two values and emit diff operations."""
    if isinstance(old, dict) and isinstance(new, dict):
        old_d = cast(dict[str, Any], old)
        new_d = cast(dict[str, Any], new)
        all_keys = set(old_d.keys()) | set(new_d.keys())
        for key in sorted(all_keys):
            child_path = f"{path}/{key}" if path else f"/{key}"
            if key not in old_d:
                ops.append({"op": "add", "path": child_path, "value": new_d[key]})
            elif key not in new_d:
                ops.append({"op": "remove", "path": child_path})
            else:
                _diff_recursive(old_d[key], new_d[key], child_path, ops)
    elif isinstance(old, list) and isinstance(new, list):
        if old != new:
            ops.append({"op": "replace", "path": path, "value": new})
    elif old != new:
        ops.append({"op": "replace", "path": path, "value": new})


_SUMMARY_LIMIT = 3


def generate_summary(diff_ops: list[dict[str, Any]]) -> str:
    """Generate a human-readable summary from diff operations."""
    if not diff_ops:
        return "No changes"

    adds = [op for op in diff_ops if op["op"] == "add"]
    removes = [op for op in diff_ops if op["op"] == "remove"]
    replaces = [op for op in diff_ops if op["op"] == "replace"]

    parts: list[str] = []
    if adds:
        paths = [op["path"].rsplit("/", 1)[-1] for op in adds[:_SUMMARY_LIMIT]]
        suffix = f" (+{len(adds) - _SUMMARY_LIMIT} more)" if len(adds) > _SUMMARY_LIMIT else ""
        parts.append(f"{len(adds)} added: {', '.join(paths)}{suffix}")
    if removes:
        paths = [op["path"].rsplit("/", 1)[-1] for op in removes[:_SUMMARY_LIMIT]]
        extra = len(removes) - _SUMMARY_LIMIT
        suffix = f" (+{extra} more)" if extra > 0 else ""
        parts.append(f"{len(removes)} removed: {', '.join(paths)}{suffix}")
    if replaces:
        paths = [op["path"].rsplit("/", 1)[-1] for op in replaces[:_SUMMARY_LIMIT]]
        extra = len(replaces) - _SUMMARY_LIMIT
        suffix = f" (+{extra} more)" if extra > 0 else ""
        parts.append(f"{len(replaces)} changed: {', '.join(paths)}{suffix}")

    return "; ".join(parts)


def compute_diff_with_summary(
    old: dict[str, Any],
    new: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    """Compute diff and summary in one call."""
    ops = compute_json_diff(old, new)
    summary = generate_summary(ops)
    return ops, summary


def payload_hash(payload: dict[str, Any]) -> str:
    """Compute a stable SHA-256 hash of a JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
