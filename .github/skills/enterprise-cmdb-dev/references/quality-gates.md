# Quality Gates Reference

> All five gates must pass before any implementation is considered complete.
> A gate that passes on its own but fails in combination with others is not a pass.

## Gate 1 — Ruff Lint

**Command:** `make lint` → `ruff check src tests`

**Configuration:** `pyproject.toml` `[tool.ruff.lint]`
- Enabled rules: `E, F, I, N, UP, B, A, C4, PT, SIM, PL, RUF`
- Line length: 100
- Target: Python 3.14

**Common Failures and Fixes:**

| Error | Meaning | Fix |
|-------|---------|-----|
| `E501` | Line too long (>100) | Break the line |
| `F401` | Unused import | Remove the import |
| `I001` | Import order wrong | Run `ruff format` or reorder imports |
| `UP006` | Use `list` instead of `List` | Replace `List[x]` with `list[x]` |
| `UP007` | Use `X \| Y` instead of `Optional[X]` | Replace `Optional[x]` with `x \| None` |
| `B006` | Mutable default argument | Use `Field(default_factory=list)` |
| `RUF012` | Mutable class attribute | Use `ClassVar` or factory |
| `PLC0415` | Import not at top of file | Move import to top, or add `# noqa: PLC0415` ONLY for runtime lazy imports |
| `PLR2004` | Magic value comparison | Extract to a named constant |
| `SIM108` | Ternary instead of if/else | Use `x if cond else y` pattern |

**Suppression Policy:**
- Never add `# noqa` for new code unless the rule generates a false positive.
- Existing `# noqa` annotations in untouched lines are acceptable.
- Per-file ignores in `pyproject.toml` take precedence.

---

## Gate 2 — Mypy Strict Type Checking

**Command:** `make type` → `mypy src tests`

**Strictness configuration:** See `pyproject.toml` `[tool.mypy]` (verify current flags).

**Rules in this codebase:**
- `from __future__ import annotations` is used — annotations are strings at runtime; do not use them for runtime introspection.
- Return types must be declared on all public functions.
- `Any` use must be justified and limited (already present in some routers for `dict[str, Any]` — only acceptable where the shape is genuinely dynamic).
- Use `list[X]` not `List[X]`; `X | None` not `Optional[X]`.

**Common Failures and Fixes:**

| Error | Fix |
|-------|-----|
| `error: Incompatible return value type` | Align the return annotation with what is actually returned |
| `error: Item "None" of "X \| None" has no attribute "y"` | Add a `None` guard before the attribute access |
| `error: Missing return statement` | Ensure all branches return a value |
| `error: Argument 1 to "X" has incompatible type` | Match the types expected by the function |
| `error: "type[X]" has no attribute "y"` | You used the class itself instead of an instance |
| `error: Returning Any from function declared to return "X"` | Cast or narrow the type explicitly |

**SQLAlchemy + mypy:**
- `db.scalars(select(X)).all()` returns `Sequence[X]` — annotate as `list[X]` with `# type: ignore[return-value]` only when the ORM result is equivalent (pre-existing pattern in this codebase).
- Async sessions: `await session.execute(stmt)` returns `Result[Any]` — use `.scalars().all()` and narrow.

---

## Gate 3 — Pytest + Coverage

**Command:** `make test` → `pytest`

**Coverage gate:** ≥ 55% (project roadmap: 55 → 75 → 90%).

**Rules:**
- New code must not decrease overall coverage percentage.
- Omit list in `pyproject.toml` is authoritative — do not add new entries without justification.
- Use `pytest.mark.asyncio` (or `asyncio_mode = "auto"` which is set) for async tests.
- Fixtures in `tests/internalcmdb/conftest.py` are shared — read before duplicating.

**Test Failure Patterns:**

| Failure | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError` | Wrong import path | Verify with `grep_search` |
| `fixture 'X' not found` | Fixture not in conftest | Add to conftest or import |
| `RuntimeError: no running event loop` | Sync code calling async without `asyncio.run` | Use `pytest-asyncio` fixture properly |
| `sqlalchemy.exc.InvalidRequestError` | Session used after close | Don't reuse test session across test isolation boundaries |
| `AssertionError` on status_code | Route handler threw an exception | Read the full traceback — likely a missing dependency or wrong model usage |
| Coverage drop | New code not covered by new tests | Add tests for all new branches |

**Coverage Omit Policy:**
- Migration versions: always omit (auto-generated).
- Seed scripts: omit (data, not logic).
- `api/main.py` lifespan: omit (tested via integration/smoke).
- Worker scheduler glue: omit (tested when worker runs).
- New business logic: NEVER omit.

---

## Gate 4 — Bandit Security Scan

**Command:** `make security` → `bandit -c pyproject.toml -r src`

**Severity levels that block merge:**
- HIGH confidence + HIGH severity: always blocking.
- MEDIUM confidence + HIGH severity: blocking.
- LOW severity: informational, not blocking.

**Common Violations to Avoid in New Code:**

| Bandit ID | Issue | Fix |
|-----------|-------|-----|
| B101 | `assert` in production code | Use explicit `if/raise` instead |
| B105/B106 | Hardcoded password | Use settings/env var |
| B107 | Hardcoded password in function arg | Same |
| B201/B202 | Flask/Django debug | N/A to FastAPI, but don't enable debug mode |
| B301 | `pickle` deserialization | Use JSON |
| B311 | Standard `random` for security | Use `secrets` module |
| B324 | MD5/SHA1 use | Use SHA-256+ |
| B501-B506 | SSL/TLS issues | Never disable SSL verification |
| B601 | Shell injection via Popen | Never interpolate user input into shell commands |
| B608 | SQL injection | Use ORM or SQLAlchemy parameterized queries — NEVER string interpolation |

**OWASP Top 10 Checklist for New Endpoints:**
```
□ No direct user input into SQL (use ORM bindparams only)
□ Authentication checked before data access
□ RBAC (require_role) applied to admin/write endpoints
□ Rate limiting applied to expensive or public endpoints
□ No sensitive data in URL path parameters (use body/header)
□ Response does not leak stack traces or internal details
□ Pydantic validates and rejects malformed inputs
□ No hardcoded credentials or tokens
```

---

## Gate 5 — IDE Problems (get_errors tool)

**After every edit:** run `get_errors` on all modified files.

**Zero tolerance policy:** No new errors or warnings introduced by your changes.

**Common IDE/LSP errors:**

| Error | Fix |
|-------|-----|
| Import resolution failure | Verify the module path, check `pythonpath` in `pyproject.toml` |
| Unresolved reference | The function/class doesn't exist at that path — re-read the source |
| Type mismatch (Pylance) | Align with mypy check |
| Missing `await` | All `AsyncSession` operations require `await` |
| Redefinition of unused variable | Variable assigned but never used before reassignment |

---

## Gate Execution Order and Blocking Logic

```
lint PASS? → YES → type PASS? → YES → test PASS? → YES → security PASS? → YES → IDE PASS?
   ↓ NO          ↓ NO              ↓ NO               ↓ NO                   ↓ NO
   FIX FIRST     FIX FIRST         FIX FIRST          FIX FIRST              FIX FIRST
```

**Never run the next gate if the current gate fails.**
Fix each gate's output completely before advancing.

## Pre-Implementation Verification

Before beginning any implementation, verify the current state of all gates:

```bash
make check
```

If the gates are already failing before your changes, document this explicitly and do not introduce additional failures. The current baseline state must be preserved or improved — never degraded.
