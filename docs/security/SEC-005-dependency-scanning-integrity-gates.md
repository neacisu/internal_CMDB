---
id: SEC-005
title: internalCMDB — Dependency Scanning and Integrity Gates Policy (Wave-1)
doc_class: policy_pack
domain: security
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: security_and_policy_owner
tags: [scanning, integrity-gates, dependency, wave-1, m10-2]
depends_on: [SEC-004]
---

# internalCMDB — Dependency Scanning and Integrity Gates Policy

## 1. Purpose

Scanning pipeline and policy gates for code packages and container images.
Satisfies pt-032 [m10-2].

---

## 2. Scanning Gates

| Gate | Tool | Trigger | Block Condition |
|---|---|---|---|
| Python dependency audit | `pip-audit` | Every `make lint` run | CRITICAL or HIGH CVE with no exception |
| SBOM generation | `cyclonedx-bom` | Every release commit | Failure to generate = hard block |
| Container image scan | `trivy` (advisory) | Pre-deployment | CRITICAL CVE without documented exception |
| Secret leak scan | `gitleaks` | Pre-push hook (active) | Any matched secret pattern |
| License compliance check | `pip-licenses` (advisory) | Quarterly review | GPL-3.0+ copyleft in production runtime |

---

## 3. pip-audit Integration

```bash
# Install and run
pip install pip-audit
pip-audit --requirement requirements.txt --format json -o audit-results.json

# In Makefile:
audit:
	pip-audit --requirement requirements.txt
```

Gate criterion:
- Zero CRITICAL or HIGH findings without documented exception in `governance.change_log`.
- MEDIUM findings tracked; exception allowed with 30-day remediation target.

---

## 4. Container Image Scanning (Trivy)

```bash
# Install trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Scan image
trivy image --format json -o image-scan.json postgres:17

# Parse results
trivy image --severity CRITICAL,HIGH postgres:17
```

Gate criterion:
- CRITICAL unpatched vulnerabilities with no workaround block image promotion.
- HIGH vulnerabilities require documented exception in `governance.change_log`.
- Image SHA must be pinned after scanning (removes mutable tag risk).

---

## 5. gitleaks Pre-Push Hook (Active)

Currently enforced via pre-commit framework in this repository. Rules enforced:

- Matches common secret patterns: API keys, connection strings, private keys, AWS/GCP/Azure credential patterns.
- Blocks push if any match found.
- Exceptions: Must be documented with `# gitleaks:allow` inline comment and a corresponding `governance.change_log` entry explaining the false positive.

---

## 6. Exception Model

| Exception Type | Approval Required | Max Duration | Required Documentation |
|---|---|---|---|
| Known CVE; no patch available | security_and_policy_owner | 30 days | CVE ID + justification in change_log |
| License copyleft in dev-only dep | security_and_policy_owner | Until next review | Confirmation dep not in production runtime |
| gitleaks false positive | security_and_policy_owner | Permanent (if confirmed FP) | Inline comment + change_log entry |
| CRITICAL CVE; mitigated by isolation | security_and_policy_owner + executive_sponsor | 7 days | Mitigation description + change_log entry |

---

## 7. Verification

- [x] Scanning gate for Python dependencies is defined and tooled.
- [x] SBOM generation gate is integrated into release process.
- [x] Container image scanning procedure is documented.
- [x] gitleaks pre-push hook is active (confirmed via .pre-commit-config.yaml).
- [x] Exception model with approval and documentation requirements is defined.
- [x] Artifacts with critical unresolved issues are blocked or require documented escalation.
