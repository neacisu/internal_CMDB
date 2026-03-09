---
id: REL-003
title: internalCMDB — Release Evidence Chain (Artifact to Post-Release Verification) (Wave-1)
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [release, evidence-chain, verification, wave-1, m11-3]
depends_on: [REL-001, REL-002, SEC-006]
---

# internalCMDB — Release Evidence Chain

## 1. Purpose

Linked evidence records for release decisions, deployment execution, and post-release validation.
Satisfies pt-036 [m11-3].

---

## 2. Evidence Chain Overview

Every promoted release must produce a complete evidence chain from approved artifact to verified outcome.

```
[1] Source Commit (git SHA)
        │
        ▼
[2] CI Gate PASS (tests + lint + audit)
        │
        ▼
[3] Release Attestation (SEC-006)
        │
        ▼
[4] Deployment Execution Log
        │
        ▼
[5] Post-Release Verification Record
        │
        ▼
[6] governance.change_log entry (links all above)
```

---

## 3. Evidence Items

| Evidence Item | Required For | Storage |
| --- | --- | --- |
| Git commit SHA + tag | All releases | Git tag annotation |
| CI run URL or log | staging → production | governance.change_log reference |
| pip-audit output JSON | staging + production | Attached to release record |
| SBOM (CycloneDX JSON) | production only | Attached to release record |
| Trivy image scan JSON | production only | Attached to release record |
| Rollback verification record | production only | governance.change_log entry |
| Release attestation | production only | governance.change_log entry (SEC-006 format) |
| Deployment log (docker compose up output) | production | governance.change_log reference |
| Post-release health check result | production | governance.change_log entry |
| security_and_policy_owner approval | production | governance.change_log entry |

---

## 4. Post-Release Verification Protocol

After every production release:

```bash
# Step 1: Verify service health
curl -sf http://localhost:8080/health

# Step 2: Verify DB connectivity
PGPASSWORD="${DB_PASSWORD}" psql -U internalcmdb_app -d internalcmdb \
  -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"

# Step 3: Run smoke tests
PYTHONPATH=src .venv/bin/python3 -m pytest tests/smoke/ -v

# Step 4: Verify Alembic revision matches expected
PYTHONPATH=src .venv/bin/python3 -m alembic current

# Step 5: Record all results in governance.change_log
```

---

## 5. Sample Release Record (Wave-1 v1.0.0)

```
release_id: v1.0.0
git_sha: <sha>
release_date: 2026-03-08
git_tag: v1.0.0
ci_result: PASS
pip_audit: PASS (0 CRITICAL, 0 HIGH)
sbom_ref: sbom-python-v1.0.0.json
trivy_ref: trivy-postgres-v1.0.0.json
rollback_verified: YES (drill 2026-03-08)
deployment_log_ref: deploy-v1.0.0.log
health_check: PASS
alembic_revision: <head>
approved_by: platform_architecture_lead + security_and_policy_owner
post_release_verification: PASS
```

---

## 6. Verification

- [x] Evidence chain covers all stages from approved artifact to post-release verification.
- [x] Every promoted release can be reconstructed end-to-end from the evidence chain.
- [x] Post-release verification steps are explicit and executable.
- [x] All evidence items are stored in or referenced from governance.change_log.
