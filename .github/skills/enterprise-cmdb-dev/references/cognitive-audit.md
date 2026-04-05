# Cognitive Audit Methodology

> Used in Phase 0 before any implementation begins.
> The goal: deeply understand the real application context before writing a single line of code.

## What Is a Cognitive Audit?

A cognitive audit is a structured, systematic reading and reasoning process applied to the codebase before any change. It prevents:
- Implementing features on wrong assumptions
- Breaking existing invariants
- Duplicating logic that already exists
- Missing integration points
- Introducing regressions

## Audit Depth Levels

### Level 1 — Surface Scan (always required)
Read the **direct files** involved:
- The router file(s) referenced in the task
- The domain module(s) touched
- The test file(s) that currently cover it

**Output:** Understand the current API contract and what existing tests verify.

### Level 2 — Dependency Trace (required for any new feature)
Trace all dependencies:
- `Depends(...)` injections in the route
- ORM models accessed (read full model class)
- Services/classes instantiated inside the route or domain module
- Background tasks triggered (`enqueue_job`, `asyncio.create_task`)

**Output:** Full map of what this feature touches.

### Level 3 — Impact Analysis (required for any modification)
For modifications to existing code:
- Find all callers of the modified function with `grep_search`
- Find all tests that cover the modified path
- Identify if the modified code is used in lifespan hooks, background loops, or middleware
- Check if schema changes break serialization of existing stored data

**Output:** List of affected files and a risk assessment.

## Cognitive Reasoning Framework

For every task, answer all branches before writing code:

### WHAT Analysis
```
WHAT does the requested change achieve?
WHAT is the real goal vs the stated goal? (Are they aligned?)
WHAT existing code is most similar? (Can I reuse/extend instead of creating new?)
WHAT are the data flow entry points and exit points?
WHAT does the user/API consumer actually receive at the end?
```

### IF/ELSE Analysis
```
IF the implementation works perfectly → what exactly is the output?
IF the input is None/empty/zero/max → what happens? Is it handled?
IF the database row does not exist → is there a 404? Is it correct?
IF the external service (Redis, LLM API) is down → graceful degradation or crash?
IF a concurrent request arrives simultaneously → is there a race condition?
IF this runs in the async event loop → are all awaits correct? No sync blocking?
```

### WHAT IF Scenarios — Apply to Every Change
```
WHAT IF the feature already partially exists in another module?
WHAT IF removing this breaks a background task (staleness_loop, escalation_loop)?
WHAT IF the Alembic migration fails mid-deployment?
WHAT IF the test passes but the implementation is wrong (false positive)?
WHAT IF the coverage increases but a critical path is still untested?
WHAT IF mypy is satisfied but the runtime type is different?
```

### WHAT ELSE Analysis
```
WHAT ELSE must change because of this? (schema, migration, seed, worker, test)
WHAT ELSE reads from the same table/field I'm modifying?
WHAT ELSE relies on the response format I'm changing?
WHAT ELSE breaks if I rename this identifier?
```

## Application Architecture Orientation

Before any deep-domain work, orient yourself by reading:

```
src/internalcmdb/api/main.py          → lifespan, router registration, background loops
src/internalcmdb/api/config.py        → all settings (pydantic-settings), env vars
src/internalcmdb/api/deps.py          → how DB sessions, Redis, auth are injected
src/internalcmdb/models/              → all ORM models — the schema of truth
src/internalcmdb/api/schemas/         → all Pydantic request/response schemas
```

## Domain Module Map

| If the task involves... | Read first... |
|------------------------|---------------|
| NL queries / health scores | `cognitive/query_engine.py`, `cognitive/health_scorer.py` |
| Drift detection | `cognitive/drift_detector.py` |
| Policy enforcement | `governance/policy_enforcer.py`, `governance/guard_gate.py` |
| HITL decisions | `governance/hitl_workflow.py` |
| Infrastructure inventory | `models/registry.py` |
| Observed facts / discovery | `models/discovery.py` (verify path) |
| SLO / error budget | `slo/framework.py` |
| Dependency graph | `graph/knowledge_graph.py` |
| Background jobs | `workers/cognitive_tasks.py`, `workers/executor.py` |
| Agent control | `control/` |
| Data quality | `cognitive/data_quality.py` |
| Embeddings / retrieval | `retrieval/`, `models/retrieval.py` |
| EU AI Act compliance | `governance/ai_compliance.py` |

## Audit Completion Checklist

Before leaving Phase 0:
```
□ I have read every file I will touch, completely
□ I understand the sync/async boundary for each route I will modify
□ I have traced all dependencies of the affected module
□ I have identified all existing tests that cover this path
□ I have confirmed all model fields and relationships I will use
□ I have an explicit answer to every WHAT/IF/ELSE question above
□ I have identified what NEW tests are needed
□ I know the full implementation scope — nothing will surprise me mid-coding
```

If any box is unchecked: continue reading before proceeding to Phase 1.
