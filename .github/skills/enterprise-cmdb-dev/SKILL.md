---
name: enterprise-cmdb-dev
description: "Enterprise-grade development skill for internalCMDB. Use when: implementing features, fixing bugs, resolving IDE problems, adding tests, understanding endpoints, auditing codebase, cognitive analysis, anti-hallucination enforcement, quality gate verification, complete implementation (no partial code), test suite, linting. Triggers: implement, fix, add test, router, endpoint, coverage, quality gate, cognitive audit, enterprise dev, no partial."
argument-hint: "Describe the feature, bug, or task to implement with full enterprise quality"
---

# Enterprise CMDB Development — Cognitive Audit Skill

> April 2026 — Highest enterprise-grade standards. Zero tolerance for partial implementations, invented facts, or assumed behaviour.

## Application Context

**internalCMDB** is an Enterprise Infrastructure Registry and Cognitive Brain system:

| Domain | Module | Purpose |
|--------|--------|---------|
| Registry | `src/internalcmdb/api/routers/registry.py` | Hosts, clusters, services, GPU, network, storage |
| Discovery | `src/internalcmdb/api/routers/discovery.py` | Collection runs, observed facts, evidence |
| Cognitive | `src/internalcmdb/api/routers/cognitive.py` | NL queries, health scores, drift, reports |
| Governance | `src/internalcmdb/api/routers/governance.py` | Policies, approvals, changelog |
| HITL | `src/internalcmdb/api/routers/hitl.py` | Human-in-the-loop review, decisions |
| SLO | `src/internalcmdb/api/routers/slo.py` | Service Level Objectives, error budgets |
| Compliance | `src/internalcmdb/api/routers/compliance.py` | EU AI Act, data lineage, Article 12 |
| Graph | `src/internalcmdb/api/routers/graph.py` | Dependency topology, impact analysis |
| Workers | `src/internalcmdb/api/routers/workers.py` | Script execution, job history, schedules |
| Audit | `src/internalcmdb/api/routers/audit.py` | Audit trail |
| Collectors | `src/internalcmdb/api/routers/collectors.py` | Agent enrollment, telemetry |
| Dashboard | `src/internalcmdb/api/routers/dashboard.py` | Aggregated statistics |
| Realtime | `src/internalcmdb/api/routers/realtime.py` | WebSocket / SSE streams |
| Debug | `src/internalcmdb/api/routers/debug.py` | LLM traces, guard blocks |
| Results | `src/internalcmdb/api/routers/results.py` | Subproject audit results |
| Documents | `src/internalcmdb/api/routers/documents.py` | Documentation index |
| Agent | `src/internalcmdb/api/routers/agent.py` | Agent control |

**Stack:** FastAPI + SQLAlchemy (sync ORM + async sessions) + PostgreSQL + Redis (ARQ) + OpenTelemetry + prometheus-client + pgvector (embeddings) + Next.js frontend (pnpm).

**Quality gates:** `ruff` lint → `mypy` strict → `pytest` (coverage ≥ 55%) → `bandit` → `pip-audit`. Run via `make check`.

---

## Mandatory Workflow — Follow Every Step, Every Time

### Phase 0 — Cognitive Orientation (BEFORE any code)

Load and follow [cognitive-audit.md](./references/cognitive-audit.md).

**Required reading before touching any file:**
1. Read the relevant router file completely — understand every endpoint, its HTTP verb, path, query params, response schema, dependencies, and side-effects.
2. Read the relevant domain module (e.g., `src/internalcmdb/cognitive/`, `src/internalcmdb/governance/`).
3. Read the existing tests for the affected module.
4. Read `src/internalcmdb/api/deps.py` for dependency injection patterns.
5. Read `src/internalcmdb/api/schemas/` for response/request schemas.
6. Read `src/internalcmdb/models/` for ORM model definitions.

**Orientation questions to answer explicitly before coding:**
- What does this module/endpoint/function actually do today?
- What is its place in the application's data/control flow?
- What are the real callers and consumers?
- What invariants must not be broken?

### Phase 1 — Anti-Hallucination Enforced Analysis

Load and follow [anti-hallucination.md](./references/anti-hallucination.md).

Rules that can never be broken:
- **Never invent** a function, class, field, or behaviour that is not confirmed by reading the actual source file.
- **Never assume** a relationship between models, schemas, or services without reading the ORM definitions.
- **Never guess** an import path — verify it with `grep_search` or `file_search`.
- If a function is referenced but its body has not been read — READ IT before using it.
- If unsure about any fact: stop, read the source, then proceed.

### Phase 2 — Cognitive Scenario Analysis

For every proposed change, perform all branches of:

```
WHAT does this change do?
  IF the change is correct → what does the system gain?
  ELSE → what breaks, and where?

WHAT IF the change is called with edge inputs?
  IF value is None, empty, 0, UUID that doesn't exist, max int?
  ELSE fallback path — does it exist?

WHAT ELSE must be updated?
  IF a model field is added → migration? schema? seed? test fixture?
  IF an endpoint is added → must be registered in main.py? schema needed?
  IF a dependency changes → all callers affected?

WHAT are the security implications?
  OWASP Top 10 — injection, broken auth, exposure, rate limiting?
  Does RBAC (require_role) apply to this endpoint?
  Does rate limiting (limiter) apply?
```

### Phase 3 — Complete Implementation (100% or Nothing)

Load and follow [implementation-standards.md](./references/implementation-standards.md).

**Non-negotiable rules:**
- Implementation is either **complete and correct** or it is **not started**.
- No `# TODO`, no `pass` placeholders, no stub functions left in production code.
- Every new public function must have a matching test.
- Every new endpoint must have: request schema, response schema, error handling, test coverage.
- Every new ORM model field must have an Alembic migration.
- Every declared-but-not-implemented function that serves the application's real purpose must be fully implemented.

### Phase 4 — Test Suite (Complete Coverage)

**Test file conventions:**
- Tests live in `tests/internalcmdb/<domain>/test_<module>.py` mirroring the source tree.
- Use `pytest-asyncio` for all async code; pytest fixtures in `tests/internalcmdb/conftest.py`.
- Use `MagicMock(spec=<ActualClass>)` — never a bare `MagicMock()`.
- Use `AsyncMock` for coroutines; `aioresponses` for HTTP.
- Test all paths: happy path, not-found (404), validation error (422), forbidden (403), edge inputs.
- For routers: use `TestClient` (sync) or `AsyncClient` (async) from `httpx`.
- Coverage gate: ≥ 55% (project baseline, increasing toward 90%). New code must not decrease coverage.
- For pnpm frontend tests: `cd frontend && pnpm test` (Vitest + coverage).

**Test structure template:**
```python
"""Tests for <module>."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

class TestClassName:
    def test_happy_path(self, ...) -> None: ...
    def test_not_found(self, ...) -> None: ...
    def test_edge_case_empty(self, ...) -> None: ...
    def test_validation_rejects_invalid_input(self, ...) -> None: ...
```

### Phase 5 — Quality Gate Verification (ALL must pass)

After every implementation, run and verify — **in this exact order**:

```bash
# 1. Ruff lint
make lint
# Expected: exit 0, no violations

# 2. Mypy strict type-check
make type
# Expected: exit 0, no errors

# 3. Full test suite with coverage
make test
# Expected: all tests pass, coverage ≥ 55%

# 4. Bandit security scan
make security
# Expected: no HIGH/MEDIUM issues in new code

# 5. IDE Problems check
# Use get_errors tool on all changed files
# Expected: 0 errors, 0 warnings
```

**If any gate fails:**
- Do not move on.
- Read the full error output.
- Fix the root cause — never suppress with `# noqa`, `# type: ignore`, `# pragma: no cover`, or `mypy: ignore-errors` unless the suppression is pre-existing and justified.

Load [quality-gates.md](./references/quality-gates.md) for detailed gate criteria and common failure patterns.

---

## Domain-Specific Patterns

### Sync vs Async Sessions
- Sync routes (`get_db`) → `Session` → synchronous ORM.
- Async routes (`get_async_session`) → `AsyncSession` → `await session.execute(...)`.
- Never mix; check the router's `Depends` before writing queries.

### RBAC & Rate Limiting
- Admin-mutating endpoints must use `require_role("admin")`.
- High-volume read endpoints must use `@limiter.limit(...)`.
- Pattern: `router.get("/path", dependencies=[Depends(require_role("admin"))])`.

### Pagination
- Use `Page[T]` generic + `PageMeta` + `paginate()` from `src/internalcmdb/api/schemas/common.py`.

### Error Responses
- 404: `raise HTTPException(status_code=404, detail="<Entity> not found")`.
- 422: handled automatically by Pydantic validation.
- 403: handled by `require_role` dependency.

### Alembic Migrations
- New column or table → `alembic revision --autogenerate -m "description"` then review.
- Never modify existing migration files.

### ARQ Workers
- New background task → register in `src/internalcmdb/workers/cognitive_tasks.py`.
- Enqueue via `enqueue_job(task_name, **kwargs)` from `workers/executor.py`.

---

## Anti-Patterns — These Are Forbidden

- Inventing a module path without confirming it exists.
- Returning `dict[str, Any]` from an endpoint without a Pydantic response model.
- Writing a test that always passes (trivially mocks everything, asserts nothing meaningful).
- Adding `from __future__ import annotations` and then using runtime annotation introspection.
- Touching `src/internalcmdb/migrations/versions/` manually.
- Using `eval()`, `exec()`, shell injection vectors, raw SQL string interpolation.
- Leaving business logic in the router layer — it belongs in the domain module.

---

## Reference Files

| File | Load When |
|------|-----------|
| [cognitive-audit.md](./references/cognitive-audit.md) | Phase 0 — orientation and understanding |
| [anti-hallucination.md](./references/anti-hallucination.md) | Phase 1 — any analysis or coding decision |
| [implementation-standards.md](./references/implementation-standards.md) | Phase 3 — writing production code |
| [quality-gates.md](./references/quality-gates.md) | Phase 5 — verification before PR |
