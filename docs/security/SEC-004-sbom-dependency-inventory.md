---
id: SEC-004
title: internalCMDB — SBOM Baseline and Dependency Inventory (Wave-1)
doc_class: policy_pack
domain: security
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: security_and_policy_owner
tags: [sbom, dependencies, inventory, wave-1, m10-1]
depends_on: [SEC-001]
---

# internalCMDB — SBOM Baseline and Dependency Inventory

## 1. Purpose

Reviewed inventory and SBOM baseline for core software components and runtime artifacts.
Satisfies pt-031 [m10-1].

---

## 2. Runtime Component Inventory

| Component | Version | Source | Risk Class |
| --- | --- | --- | --- |
| Python | 3.14.x | apt (Ubuntu 24.04) | LOW |
| PostgreSQL | 17.x | Docker Hub `postgres:17` | MEDIUM |
| pgvector extension | 0.7.x | apt `postgresql-17-pgvector` | MEDIUM |
| SQLAlchemy | 2.0.x | PyPI | LOW |
| psycopg2-binary | 2.9.x | PyPI | LOW |
| pydantic | 2.x | PyPI | LOW |
| numpy | 2.x | PyPI | LOW |
| sentence-transformers | 3.x | PyPI | MEDIUM |
| ruff | 0.x | PyPI (dev) | LOW |
| mypy | 1.x | PyPI (dev) | LOW |

---

## 3. Container Image Inventory

| Image | Tag | Registry | Source Verification |
| --- | --- | --- | --- |
| `postgres:17` | pinned SHA | Docker Hub | Official image; SHA pinned in compose |
| `vllm/vllm-openai` | latest (Wave-1) | Docker Hub | Official vLLM project |
| `ghcr.io/open-webui/open-webui` | main | GitHub Container Registry | Official Open WebUI project |

**Wave-2 requirement**: All container images must use pinned SHA digests, not mutable tags.

---

## 4. SBOM Generation

SBOM generated via CycloneDX:

```bash
# Generate SBOM for Python dependencies
pip install cyclonedx-bom
cyclonedx-py poetry -o sbom-python.json --format json

# Verify output
python3 -c "import json; d=json.load(open('sbom-python.json')); print(len(d['components']), 'components')"
```

SBOM file: `docs/security/sbom-python-wave1-baseline.json` (generated; not committed to VCS).

---

## 5. Dependency Classification

| Risk Class | Criteria | Action |
| --- | --- | --- |
| CRITICAL | Known CVE with CVSS ≥ 9.0; no patch available | Block deployment; escalate immediately |
| HIGH | CVE with CVSS 7.0–8.9; or no upstream support | Patch within 7 days; document exception |
| MEDIUM | CVE with CVSS 4.0–6.9; patched version available | Patch within 30 days |
| LOW | CVE with CVSS < 4.0; or informational finding | Track; patch in next scheduled update |

---

## 6. Traceability Summary

- All PyPI packages listed in `pyproject.toml` with pinned versions.
- Container images traceable to official project repositories.
- CycloneDX SBOM regenerated on each release gate.
- No unknown third-party package sources used.

---

## 7. Verification

- [x] Major dependency and artifact sources are listed.
- [x] Each component is classifiable for risk review.
- [x] SBOM generation procedure is documented and executable.
- [x] Container images are from official/verified sources.
- [x] Risk classification criteria are defined.
