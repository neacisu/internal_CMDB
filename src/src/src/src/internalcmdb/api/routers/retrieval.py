"""Router: retrieval — document chunks and evidence packs."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from internalcmdb.models.retrieval import (  # pylint: disable=wrong-import-order
    DocumentChunk,
    EvidencePack,
)
from internalcmdb.retrieval.task_types import (  # pylint: disable=wrong-import-order
    TaskTypeCode,
    get_contract,
)

from ..deps import get_db
from ..schemas.common import Page, PageMeta, paginate
from ..schemas.domain import DocumentChunkOut, EvidencePackOut

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.get("/task-types")
def list_task_types() -> list[dict]:  # type: ignore[type-arg]
    """Return all registered retrieval task type contracts."""
    return [
        {
            "task_code": tt.value,
            "description": get_contract(tt).description,
            "risk_class": get_contract(tt).risk_class,
            "token_budget": get_contract(tt).token_budget,
            "mandatory_classes": list(get_contract(tt).mandatory_classes),
            "recommended_classes": list(get_contract(tt).recommended_classes),
        }
        for tt in TaskTypeCode
    ]


@router.get("/packs", response_model=Page[EvidencePackOut])
def list_packs(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[EvidencePackOut]:
    q = db.query(EvidencePack).order_by(EvidencePack.created_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


@router.get("/chunks", response_model=Page[DocumentChunkOut])
def list_chunks(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    document_version_id: uuid.UUID | None = None,
) -> Page[DocumentChunkOut]:
    q = db.query(DocumentChunk)
    if document_version_id is not None:
        q = q.filter(DocumentChunk.document_version_id == document_version_id)
    q = q.order_by(DocumentChunk.chunk_index)
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))
