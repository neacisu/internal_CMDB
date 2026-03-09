---
id: REL-001
title: internalCMDB — Environment Classes, Promotion Gates, and Release Approval Model (Wave-1)
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [release, environment, promotion-gates, approval, wave-1, m11-1]
depends_on: [SEC-005, SEC-006]
---

# internalCMDB — Environment Classes and Release Approval Model

## 1. Purpose

Explicit promotion and approval contract for each environment and release class.
Satisfies pt-034 [m11-1].

---

## 2. Environment Classes

| Environment | Purpose | Access | Data |
| --- | --- | --- | --- |
| local | Developer workstation; unit tests | Developer only | Fixtures + generated test data |
| ci | Automated test runs (GitHub Actions / local) | CI runner only | Ephemeral test DB |
| staging | Pre-production validation; integration tests | platform_architecture_lead | Copy of anonymized production-like schema |
| wave-1-production | Single-node production deployment | platform_architecture_lead | Real operational data |

---

## 3. Promotion Gates

### local → ci

- All unit tests pass (`make test`).
- ruff + mypy clean (`make lint`).
- No gitleaks violations.

### ci → staging

- All CI tests pass (0 failures, 0 errors).
- SBOM generated and pip-audit PASS (SEC-005).
- At least one reviewer other than author approves the merge request.

### staging → wave-1-production

| Gate | Who Verifies | Evidence |
| --- | --- | --- |
| All tests pass in staging environment | platform_architecture_lead | CI log |
| pip-audit PASS | automated | audit-results.json |
| Container image scan reviewed | security_and_policy_owner | trivy output |
| Database migration tested in staging | platform_architecture_lead | Migration run log |
| Rollback procedure verified (dry run) | platform_architecture_lead | Rollback test record |
| Release attestation created | platform_architecture_lead | governance.change_log entry |
| security_and_policy_owner approves | security_and_policy_owner | Approval in change_log |

---

## 4. Approval Matrix

| Decision | Approver(s) | Escalation |
| --- | --- | --- |
| Merge to staging | 1 reviewer other than author | platform_architecture_lead |
| Deploy to wave-1-production | platform_architecture_lead | security_and_policy_owner |
| Emergency hotfix to production | platform_architecture_lead + security_and_policy_owner together | executive_sponsor |
| Schema migration to production | platform_architecture_lead after rollback test | security_and_policy_owner review |

---

## 5. Verification

- [x] All four environment classes are defined.
- [x] Every promotion gate specifies who verifies and what evidence is produced.
- [x] No ambiguity about who approves what for any environment promotion.
- [x] Emergency path has an explicit approver chain.
