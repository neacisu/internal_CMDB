# Anti-Hallucination Protocol

> Applies at every moment of every task. This is not optional.

## Core Principle

An AI agent operating on enterprise production code must treat **every unverified fact as a hallucination risk**. The cost of a wrong assumption in a production CMDB is data corruption, silent failures, broken infrastructure inventory, and compliance violations.

## The Verification Contract

Before using any of the following, you MUST have read the actual source:

| Claim Type | Verification Required |
|------------|----------------------|
| "This function exists" | Read the file that declares it |
| "This field is on the model" | Read `src/internalcmdb/models/*.py` |
| "This import works" | Verify the module path with `grep_search` or `file_search` |
| "This endpoint returns X" | Read the router function body completely |
| "This test covers Y" | Read the test file — do not infer from file name |
| "This migration exists" | `ls src/internalcmdb/migrations/versions/` |
| "This config field exists" | Read `src/internalcmdb/api/config.py` or `pydantic_settings` class |
| "This dependency injects Z" | Read `src/internalcmdb/api/deps.py` |

## Seven Anti-Hallucination Rules

### Rule 1 — Source Before Statement
Never describe what code does without having read its full source. Partial reads produce partial truths. Read complete functions, not just their signatures.

### Rule 2 — No Invented Identifiers
Never write code using a class name, function name, field name, enum value, or constant that you did not read from a source file. If in doubt: `grep_search` first.

### Rule 3 — No Assumed Relationships
Never assume that Model A has a FK to Model B, that Service X calls Module Y, or that Endpoint Z uses dependency D — without reading both sides. The schema is in `src/internalcmdb/models/`. Read it.

### Rule 4 — No Guess Imports
Python import paths are exact. `from internalcmdb.cognitive.query_engine import QueryEngine` either works or it doesn't. Verify the file and class name exist before writing the import.

### Rule 5 — Distinguish Sync/Async
This codebase uses both `Session` (sync) and `AsyncSession`. Getting this wrong causes runtime failures. Always read the `Depends(...)` in the route signature before writing query code.

### Rule 6 — Read Before Extending
Before adding a method to an existing class or adding a field to an existing model, read the **entire** class to understand existing invariants, existing similar methods, and naming conventions.

### Rule 7 — Tests Must Assert Real Behaviour
A test that only checks `assert result is not None` is worse than no test — it gives false confidence. Every test must assert the actual produced value, response status code, or side effect. Use `assert response.status_code == 200` AND `assert data["field"] == expected_value`.

## Self-Check Protocol

Before committing any written code, perform this internal checklist:

```
□ Every identifier I used — have I read its definition?
□ Every import I wrote — have I verified the module path exists?
□ Every field I accessed — have I read the model's __tablename__ and columns?
□ Every behaviour I described — have I confirmed it by reading the implementation?
□ Every "this already exists" claim — have I seen it with my own read_file call?
□ Every new test — does it assert something that could actually fail?
```

If any box is unchecked: stop, go read, then proceed.

## Common Hallucination Patterns in This Codebase

| Hallucination | Reality |
|---------------|---------|
| Assuming `get_db` returns `AsyncSession` | It returns sync `Session`; async routes use `get_async_session` |
| Assuming all routers use async | Many registry/governance routes are synchronous |
| Assuming Page pagination is built-in FastAPI | It is a custom `Page[T]` in `src/internalcmdb/api/schemas/common.py` |
| Assuming `require_role` is a FastAPI dependency | It is a custom middleware in `src/internalcmdb/api/middleware/rbac.py` |
| Assuming ARQ tasks are in one file | They are split across `cognitive_tasks.py` and `executor.py` |
| Assuming test fixtures are global | Most fixtures are in `tests/internalcmdb/conftest.py` — read it |
| Assuming coverage omits apply everywhere | Check `[tool.coverage.run] omit` in `pyproject.toml` |

## When You Are Uncertain

The correct response to uncertainty is:
1. Use `grep_search` with the identifier.
2. Use `file_search` if you need the path.
3. Use `read_file` to see the full context.
4. Then proceed.

Never proceed from uncertainty. Uncertainty + action = hallucination.
