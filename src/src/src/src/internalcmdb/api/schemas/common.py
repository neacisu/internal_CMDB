"""Pydantic v2 response schemas — shared primitives."""

from __future__ import annotations

import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict

# ---------------------------------------------------------------------------
# Annotated scalar types that coerce ORM objects before field validation.
# Use these for any field that the ORM may return as datetime / IPv*Address
# rather than a plain string.
# ---------------------------------------------------------------------------


def _coerce_dt(v: object) -> str | None:
    if isinstance(v, datetime):
        return v.isoformat()
    return v  # type: ignore[return-value]


def _coerce_ip(v: object) -> str | None:
    if isinstance(v, IPv4Address | IPv6Address):
        return str(v)
    return v  # type: ignore[return-value]


# Required datetime-as-string (ORM datetime → ISO-8601 str)
DatetimeStr = Annotated[str, BeforeValidator(_coerce_dt)]
# Optional datetime-as-string
OptDatetimeStr = Annotated[str | None, BeforeValidator(_coerce_dt)]
# Optional IP-address-as-string
OptIpStr = Annotated[str | None, BeforeValidator(_coerce_ip)]


class OrmBase(BaseModel):
    """Base class for all ORM-mapped response schemas."""

    model_config = ConfigDict(from_attributes=True)


class TaxonomyTermOut(OrmBase):
    taxonomy_term_id: uuid.UUID
    taxonomy_domain_id: uuid.UUID
    term_code: str
    display_name: str
    description: str | None = None
    is_active: bool


class TaxonomyDomainOut(OrmBase):
    taxonomy_domain_id: uuid.UUID
    domain_code: str
    name: str
    description: str | None = None
    schema_version: str
    is_active: bool
    terms: list[TaxonomyTermOut] = []


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class Page[T](BaseModel):
    items: list[T]
    meta: PageMeta


def paginate(query: Any, page: int, page_size: int) -> tuple[list[Any], int]:
    """Return (items, total) for a given SQLAlchemy query with pagination applied."""
    total: int = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total
