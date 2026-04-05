# Implementation Standards

> Used in Phase 3. These are not guidelines — they are mandatory constraints.

## The 100% Rule

**An implementation is either complete or it does not exist.**

This means:
- Every function that is declared must have a full, correct body.
- Every endpoint must have: route decorator, request validation, business logic, response model, error handling, and a test.
- Every ORM field addition must have a migration.
- Every new public API must have complete documentation (docstring + schema description).
- No `# TODO left for later`, no `pass`, no `raise NotImplementedError` in production paths.

If the full implementation cannot be done in one session, the correct approach is to NOT add the stub at all — not to add it incomplete.

## Router Implementation Standard

A router endpoint is complete when it has all of the following:

```python
@router.post(
    "/path",
    response_model=ResponseSchemaOut,           # 1. Response model declared
    status_code=201,                              # 2. Correct status code
    summary="One line description",              # 3. OpenAPI summary
    dependencies=[Depends(require_role("admin"))], # 4. Auth if needed
)
@limiter.limit("10/minute")                       # 5. Rate limit if needed
async def endpoint_name(
    body: RequestSchemaIn,                        # 6. Validated input
    session: Annotated[AsyncSession, Depends(get_async_session)],  # 7. Correct session type
    request: Request,                             # 8. Request when using limiter
) -> ResponseSchemaOut:                           # 9. Return type annotation
    """Detailed docstring: what it does, when to use, what it returns."""
    result = await some_service.do_thing(session, body.field)
    if result is None:
        raise HTTPException(status_code=404, detail="Entity not found")  # 10. Error handling
    return ResponseSchemaOut.model_validate(result)  # 11. Schema conversion
```

## Pydantic Schema Standard

Every request/response schema is complete when:

```python
class EntityOut(BaseModel):
    id: uuid.UUID                         # Correct type, not str
    name: str
    status: str
    created_at: datetime                  # Use datetime, not str where possible
    optional_field: str | None = None     # X | None, not Optional[X]
    list_field: list[str] = Field(default_factory=list)  # No mutable default

    model_config = ConfigDict(from_attributes=True)  # If ORM-backed
```

## ORM Model Standard

A new model or field is complete when:

1. **Model definition** in `src/internalcmdb/models/<domain>.py` — full column spec including `nullable`, `default`, `index`, `foreign_key`.
2. **Alembic migration** generated and reviewed — column type correct, `server_default` if needed.
3. **Pydantic schema** updated to include the new field.
4. **Seed scripts** updated if default/test data needs the field.
5. **Test fixtures** updated to include the field in mock data.

## Service / Domain Module Standard

A domain class method is complete when:

```python
async def do_thing(self, session: AsyncSession, entity_id: uuid.UUID) -> EntityResult | None:
    """What this method does, what it returns, edge cases.

    Returns None if entity does not exist (caller must handle 404).
    """
    # 1. Query — parameterized, using ORM
    stmt = select(EntityModel).where(EntityModel.id == entity_id)
    row = await session.scalar(stmt)

    # 2. Guard — explicit None check
    if row is None:
        return None

    # 3. Business logic — pure transformation
    result = EntityResult(
        id=row.id,
        computed_field=_compute(row),
    )

    # 4. Return typed result
    return result
```

## Test Implementation Standard

A test is complete when it:

1. **Tests the stated behaviour** — not the mock structure.
2. **Asserts the actual output** — not just `assert result is not None`.
3. **Covers the failure paths** — at minimum: happy path + not-found + invalid input.
4. **Is isolated** — does not depend on running database; uses `MagicMock(spec=...)`.
5. **Uses correct async patterns** — `AsyncMock` for coroutines, `await` in async tests.

### Router Test Pattern (httpx TestClient)

```python
"""Tests for <router_name> router."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from internalcmdb.api.main import create_app

app = create_app()
client = TestClient(app)


class TestEntityEndpoints:
    def test_list_returns_200_with_items(self) -> None:
        with patch("internalcmdb.api.routers.X.some_dep") as mock_dep:
            mock_dep.return_value = [...]
            resp = client.get("/entity/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_returns_404_for_unknown_id(self) -> None:
        resp = client.get(f"/entity/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_post_validates_required_fields(self) -> None:
        resp = client.post("/entity/", json={})
        assert resp.status_code == 422
```

### Domain Service Test Pattern

```python
"""Tests for <service_name>."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.<domain>.<module> import ServiceClass


class TestServiceClass:
    @pytest.fixture
    def session(self) -> AsyncMock:
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, session: AsyncMock) -> ServiceClass:
        return ServiceClass(session)

    async def test_method_happy_path(self, service: ServiceClass, session: AsyncMock) -> None:
        mock_row = MagicMock(spec=TargetModel)
        mock_row.id = uuid.uuid4()
        session.scalar.return_value = mock_row

        result = await service.do_thing(uuid.uuid4())

        assert result is not None
        assert result.id == mock_row.id

    async def test_method_returns_none_when_not_found(
        self, service: ServiceClass, session: AsyncMock
    ) -> None:
        session.scalar.return_value = None
        result = await service.do_thing(uuid.uuid4())
        assert result is None
```

## Naming Conventions (from the existing codebase)

| Entity | Convention | Example |
|--------|------------|---------|
| Router functions | `snake_case` verb + noun | `list_hosts`, `create_policy`, `get_slo_budget` |
| Pydantic schemas | `PascalCase` + `Out`/`In`/`Body` | `HostOut`, `SLODefineBody`, `NLQueryRequest` |
| ORM models | `PascalCase` | `Host`, `PolicyRecord`, `ClusterAuditResult` |
| Router prefixes | `/lowercase-kebab` or `/lowercase` | `/registry`, `/slo`, `/cognitive` |
| Test classes | `TestClassName` | `TestRegistryEndpoints` |
| Test methods | `test_<what>_<expected_result>` | `test_list_hosts_returns_paginated_result` |

## Completeness Verification Before Claiming "Done"

```
□ All route functions have: decorator, response_model, status_code, body/query params, return annotation
□ All new Pydantic schemas have: field types, Field() validators, model_config if ORM-backed
□ All ORM changes have a migration file
□ All domain functions have: docstring, typed args, typed return, None guards
□ All tests are in the correct test directory, mirroring the source tree
□ Tests cover: happy path, 404, 422, forbidden (if RBAC applied), edge inputs
□ No new `# type: ignore` without explanation
□ No new `pragma: no cover` without justification
□ Ruff clean, mypy clean, tests pass, bandit clean, IDE 0 errors
□ Frontend changes: `cd frontend && pnpm test` passes
```

If every box is checked: the implementation is complete.
If any box is unchecked: the implementation is not complete.
