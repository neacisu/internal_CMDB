"""Router: documents — browse and read project markdown documentation from docs/."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

router = APIRouter(prefix="/documents", tags=["documents"])

# docs/ directory is five parents up from this file (repo root / docs)
_DOCS_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent / "docs"

_CATEGORY_LABELS: dict[str, str] = {
    "": "General",
    "adr": "Architecture Decisions",
    "capacity": "Capacity",
    "continuity": "Continuity",
    "governance": "Governance",
    "llm": "LLM / AI",
    "observability": "Observability",
    "operations": "Operations",
    "pilot": "Pilot",
    "release": "Release",
    "retrieval": "Retrieval",
    "security": "Security",
    "templates": "Templates",
}


class DocMeta(BaseModel):
    path: str  # relative path from docs root, e.g. "adr/ADR-001-truth-model.md"
    title: str  # human-readable title derived from filename
    category: str  # subdirectory key (empty string = root level)
    category_label: str
    size_bytes: int
    modified_at: str  # ISO-8601


class DocCategory(BaseModel):
    category: str
    label: str
    docs: list[DocMeta]


def _to_title(stem: str) -> str:
    """Convert a filename stem to a human-readable title."""
    # Remove leading code prefix like "ADR-001-", "OBS-003-" etc.
    clean = re.sub(r"^[A-Z]+-\d+-", "", stem)
    return clean.replace("-", " ").replace("_", " ")


def _scan_docs() -> list[DocCategory]:
    if not _DOCS_ROOT.exists():
        return []

    by_cat: dict[str, list[DocMeta]] = {}
    for md_file in sorted(_DOCS_ROOT.rglob("*.md")):
        # Skip hidden dirs and __pycache__
        rel = md_file.relative_to(_DOCS_ROOT)
        if any(p.startswith((".", "__")) for p in rel.parts):
            continue

        parts = rel.parts
        category = parts[0] if len(parts) > 1 else ""
        label = _CATEGORY_LABELS.get(category, category.replace("-", " ").title())

        stat = md_file.stat()
        meta = DocMeta(
            path=rel.as_posix(),
            title=_to_title(rel.stem),
            category=category,
            category_label=label,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
        )
        by_cat.setdefault(category, []).append(meta)

    # Build ordered list: root docs first, then alphabetical categories
    result: list[DocCategory] = []
    for cat_key in ["", *sorted(k for k in by_cat if k != "")]:
        if cat_key not in by_cat:
            continue
        label = _CATEGORY_LABELS.get(cat_key, cat_key.replace("-", " ").title())
        result.append(DocCategory(category=cat_key, label=label, docs=by_cat[cat_key]))
    return result


@router.get("/index", response_model=list[DocCategory])
def get_document_index() -> list[DocCategory]:
    """Return all document categories with their file listings."""
    return _scan_docs()


@router.get("/content")
def get_document_content(
    path: str = Query(
        ...,
        description="Relative path from docs root, e.g. adr/ADR-001-truth-model.md",
    ),
) -> PlainTextResponse:
    """Return raw markdown content for a single document."""
    # Security: prevent path traversal outside docs/
    docs_resolved = _DOCS_ROOT.resolve()
    try:
        target = (docs_resolved / path).resolve()
        target.relative_to(docs_resolved)  # raises ValueError if outside docs root
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document path") from exc

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    if target.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="Only markdown files are accessible")

    return PlainTextResponse(content=target.read_text(encoding="utf-8"))
