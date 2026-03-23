---
id: OPS-001
title: internalCMDB — RACI Matrix and Service Ownership Model (Wave-1)
doc_class: ownership_matrix
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [raci, ownership, service-boundaries, wave-1, m14-1]
---

# internalCMDB — RACI Matrix and Service Ownership

## 1. Purpose

Named responsibility matrix and accepted service ownership model.
Satisfies pt-043 [m14-1].

---

## 2. Named Roles

| Role Identifier | Responsibilities |
| --- | --- |
| platform_architecture_lead | System design, deployment, DB operations, release management |
| security_and_policy_owner | Security review, credential approval, compliance declarations |
| executive_sponsor | Final approval authority for critical decisions and declarations |
| dba_role | PostgreSQL DDL, migrations, user management (Wave-1 = platform_architecture_lead) |
| on_call_engineer | Incident response during reviewed on-call hours |

---

## 3. Service Boundaries

| Service | Owner | Backup |
| --- | --- | --- |
| internalcmdb-postgres (DB) | platform_architecture_lead | security_and_policy_owner |
| internalcmdb-app (API) | platform_architecture_lead | security_and_policy_owner |
| vLLM primary (reasoning_32b) | platform_architecture_lead | — |
| vLLM secondary (fast_14b) | platform_architecture_lead | — |
| Prometheus / Grafana | platform_architecture_lead | — |
| SSH access / host OS | platform_architecture_lead | security_and_policy_owner |

---

## 4. RACI Matrix

**R** = Responsible (does the work), **A** = Accountable (approves), **C** = Consulted, **I** = Informed

| Capability | platform_architecture_lead | security_and_policy_owner | executive_sponsor |
| --- | --- | --- | --- |
| DB schema migration | R/A | C | I |
| Secret rotation | R | A | I |
| Production deployment | R | A | I |
| Model retirement | R | A | I |
| Incident response (critical) | R | C | A |
| Access grant/revoke | R | A | I |
| Compliance declaration | R | A | A |
| Emergency hotfix | R | A | A |
| SBOM + audit gate | R | A | I |
| On-call coverage | R | I | I |

---

## 5. Critical Capabilities Without Gaps

Verification that no critical capability lacks a named owner or review authority:

| Critical Capability | Named Owner | Review Authority |
| --- | --- | --- |
| DB availability | platform_architecture_lead | security_and_policy_owner |
| Credential rotation | platform_architecture_lead | security_and_policy_owner |
| Agent approval enforcement | platform_architecture_lead | security_and_policy_owner |
| Compliance reporting | platform_architecture_lead | executive_sponsor |
| Incident command | platform_architecture_lead | executive_sponsor |

---

## 6. Verification

- [x] All critical capabilities have a named owner.
- [x] No critical capability remains without a review authority.
- [x] RACI is complete for all governance and operational decision types.
