"""Router: results — read current.json and historical results from subproject output directories."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..schemas.ops import ResultHistoryItem, ResultTypeMeta

router = APIRouter(prefix="/results", tags=["results"])

# Result type registry — maps result_type key to (subproject_dir, subfolder)
_BASE = Path(__file__).resolve().parent.parent.parent.parent.parent  # repo root

RESULT_TYPES: dict[str, dict[str, str]] = {
    "ssh_connectivity": {
        "display_name": "SSH Connectivity",
        "directory": "subprojects/cluster-ssh-checker/results/ssh_connectivity",
    },
    "network_audit": {
        "display_name": "Cluster Network Audit",
        "directory": "subprojects/cluster-audit/results/network_audit",
    },
    "full_cluster_audit": {
        "display_name": "Full Cluster Audit",
        "directory": "subprojects/cluster-full-audit/results/full_cluster_audit",
    },
    "runtime_posture": {
        "display_name": "Runtime Posture",
        "directory": "subprojects/runtime-posture-audit/results/runtime_posture",
    },
    "trust_surface": {
        "display_name": "Trust Surface",
        "directory": "subprojects/trust-surface-audit/results/trust_surface",
    },
    "cluster_key_mesh_state": {
        "display_name": "Cluster Key Mesh State",
        "directory": "subprojects/cluster-key-mesh/results/cluster_key_mesh_state",
    },
}


def _result_dir(result_type: str) -> Path:
    meta = RESULT_TYPES.get(result_type)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Unknown result type: {result_type!r}")
    return _BASE / meta["directory"]


@router.get("/types", response_model=list[ResultTypeMeta])
def list_result_types() -> list[ResultTypeMeta]:
    out = []
    for key, meta in RESULT_TYPES.items():
        result_dir = _BASE / meta["directory"]
        current = result_dir / "current.json"
        last_modified = None
        if current.exists():
            mtime = os.path.getmtime(current)
            last_modified = datetime.fromtimestamp(mtime, tz=UTC).isoformat()
        out.append(
            ResultTypeMeta(
                result_type=key,
                display_name=meta["display_name"],
                directory=meta["directory"],
                current_file="current.json" if current.exists() else None,
                last_modified=last_modified,
            )
        )
    return out


@router.get("/{result_type}/current")
def get_current_result(result_type: str) -> JSONResponse:
    result_dir = _result_dir(result_type)
    current = result_dir / "current.json"
    if not current.exists():
        raise HTTPException(status_code=404, detail="No current result available")
    data: Any = json.loads(current.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


@router.get("/{result_type}/history", response_model=list[ResultHistoryItem])
def list_history(result_type: str) -> list[ResultHistoryItem]:
    result_dir = _result_dir(result_type)
    if not result_dir.exists():
        return []
    items = []
    for path in sorted(result_dir.iterdir(), reverse=True):
        if path.suffix == ".json" and path.name != "current.json":
            mtime = os.path.getmtime(path)
            items.append(
                ResultHistoryItem(
                    filename=path.name,
                    modified_at=datetime.fromtimestamp(mtime, tz=UTC).isoformat(),
                    size_bytes=path.stat().st_size,
                )
            )
    return items


@router.get("/{result_type}/history/{filename}")
def get_historical_result(result_type: str, filename: str) -> JSONResponse:
    # Security: only allow .json filenames with no path traversal
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    result_dir = _result_dir(result_type)
    path = result_dir / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)
