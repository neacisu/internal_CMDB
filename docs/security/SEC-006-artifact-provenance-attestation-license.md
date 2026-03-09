---
id: SEC-006
title: internalCMDB — Artifact Provenance, Attestation, and License Review Policy (Wave-1)
doc_class: policy_pack
domain: security
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: security_and_policy_owner
tags: [provenance, attestation, license, wave-1, m10-3]
depends_on: [SEC-004, SEC-005]
---

# internalCMDB — Artifact Provenance, Attestation, and License Review Policy

## 1. Purpose

Provenance and attestation model tied to release classes and license review obligations.
Satisfies pt-033 [m10-3].

---

## 2. Release Classes

| Release Class | Description | Provenance Requirements |
| --- | --- | --- |
| development | Local commits on feature branches | SBOM generation; no formal attestation |
| staging | Commits merged to staging branch | SBOM + pip-audit PASS required |
| wave-1-production | Tagged release on main/release branch | SBOM + pip-audit + container scan + change_log entry |
| wave-2-production | Subsequent production releases | All wave-1 requirements + trivy PASS + license review PASS |

---

## 3. Provenance Evidence Chain

For each wave-1-production release:

| Evidence Item | Source | Storage |
| --- | --- | --- |
| Git commit SHA | `git rev-parse HEAD` | Release tag annotation |
| SBOM (CycloneDX JSON) | `cyclonedx-bom` output | Attached to release in governance.change_log |
| pip-audit result | `pip-audit --format json` | Attached to release in governance.change_log |
| Trivy image scan result | `trivy image --format json` | Attached to release in governance.change_log |
| Approver identity | Named platform_architecture_lead | governance.change_log entry |

---

## 4. Attestation Model

An attestation record must be created in `governance.change_log` for each production release:

```
change_type: release_attestation
change_description: "Release attestation for v{version}"
requested_by: platform_architecture_lead
approved_by: security_and_policy_owner
evidence_references:
  - sbom: sbom-python-{version}.json
  - audit: pip-audit-{version}.json
  - image_scan: trivy-postgres-{version}.json
statement: "All dependencies scanned. No unmitigated CRITICAL/HIGH CVEs. SBOM complete."
```

---

## 5. License Review Obligations

| License Type | Usage | Action Required |
| --- | --- | --- |
| MIT / BSD / Apache 2.0 | Production runtime | No action; record in SBOM |
| LGPL v2.1 | Production runtime | No action if used as library (not modified) |
| GPL v2.0 | Dev tooling only | Confirm not shipped in production runtime |
| GPL v3.0+ | Any usage | Review required; copyleft may trigger obligations |
| AGPL v3.0 | Any usage | Block unless legal review confirms isolation |
| Unknown / No License | Any usage | Block; request clarification from security_and_policy_owner |

License review tool:

```bash
pip install pip-licenses
pip-licenses --format json -o licenses.json
# Flag any GPL-3.0+, AGPL, or Unknown licenses
pip-licenses | grep -E "GPL-3|AGPL|UNKNOWN"
```

---

## 6. Verification

- [x] Release classes are defined with explicit provenance requirements.
- [x] Provenance evidence chain covers git SHA, SBOM, audit results, and approver identity.
- [x] Attestation model produces a reviewable record in governance.change_log.
- [x] License review obligations are explicit for all license types encountered.
- [x] Promoted artifacts can be defended through provenance evidence and policy-compliant records.
