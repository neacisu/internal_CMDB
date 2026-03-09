---
id: VER-NNN           # REQUIRED — next available VER number e.g. VER-001
title: "<System or feature> — Verification Specification"  # REQUIRED
doc_class: verification_spec  # REQUIRED — do not change
domain: platform-foundations  # REQUIRED — change to relevant domain
version: "1.0"        # REQUIRED — quoted decimal
status: draft         # REQUIRED
created: "2026-03-09"   # REQUIRED
updated: "2026-03-09"   # REQUIRED
owner: platform_engineering_lead  # REQUIRED — role that approves verification
binding: []
tags: []
depends_on: []
---

# VER-NNN: <System or Feature> — Verification Specification

<!-- Replace VER-NNN and system/feature name. Remove this comment. -->

## Purpose

<!-- What is being verified? What does "success" mean for this feature or system?
Link to the task, ADR, or work package this spec covers. -->

**Work package / task:** <!-- pt-NNN or epic-N -->
**Acceptance from milestone:** <!-- m-N -->

## Scope

**Verified components:**
<!-- List the specific files, modules, tables, or services under test -->

**Not in scope:**
<!-- What is explicitly not tested here -->

## Preconditions

<!-- Conditions that must be true before any test in this spec can run -->

- [ ] <!-- e.g. PostgreSQL running and migrations applied -->
- [ ] <!-- e.g. discovery loader executed at least once -->
- [ ] <!-- e.g. `ruff check` and `mypy --strict` pass -->

## Test Cases

<!-- Format: TC-NNN — Title / Type / Steps / Expected outcome / Pass criteria -->

### TC-001 — <Test name>

**Type:** <!-- unit / integration / smoke / manual -->
**Description:** <!-- What behaviour is being tested? -->

**Steps:**
1. <!-- Step 1 -->
2. <!-- Step 2 -->

**Expected outcome:** <!-- Concrete, observable result -->

**Pass criteria:** <!-- Exact condition that constitutes passing -->

---

### TC-002 — <Test name>

<!-- ... -->

---

### TC-NNN — Regression validation

<!-- At least one negative test: verify that the system rejects invalid input
or enforces a constraint. -->

**Type:** negative / regression
**Description:** <!-- What should NOT happen? -->

**Steps:**
1. <!-- Step 1 -->

**Expected outcome:** <!-- Error, rejection, or audit log entry -->

## Evidence Requirements

<!-- What evidence must be captured at verification time? -->

| Evidence item | Format | Where stored |
| --- | --- | --- |
| <!-- test run output --> | <!-- log / json / screenshot --> | <!-- path / audit table --> |
| <!-- query result --> | <!-- SQL output --> | <!-- path --> |

## Sign-off

<!-- Who must review and approve the verification results? -->

| Role | Sign-off required | Approved |
| --- | --- | --- |
| <!-- role token --> | yes | [ ] |

**Approved evidence pack location:** <!-- path or audit record ID -->
