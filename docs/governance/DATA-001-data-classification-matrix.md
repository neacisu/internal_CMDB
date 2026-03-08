---
id: DATA-001
title: internalCMDB — Data Classification Matrix (Wave-1)
doc_class: policy_pack
domain: governance
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: security_and_policy_owner
tags: [data-classification, access-control, governance, wave-1, m15-1]
---

# internalCMDB — Data Classification Matrix

## 1. Purpose

Policy document mapping all registry tables to data classes, with examples, restrictions, and named owners.
Satisfies pt-055 [m15-1].

---

## 2. Data Classes

| Class | Label | Description | Examples |
|---|---|---|---|
| A | PUBLIC | Non-sensitive operational data; freely shareable internally | Service names, container counts, public host names |
| B | INTERNAL | Business-sensitive operational data; restricted to authorized roles | Observed facts with IP addresses, service configurations |
| C | CONFIDENTIAL | Credential or security-sensitive data; strict access control | Secrets (handled by SEC-001), security posture gaps |
| D | RESTRICTED | Regulatory or legal sensitivity; executive_sponsor approval required | PII (if ever collected), compliance evidence packs |

---

## 3. Table-to-Class Mapping

| Table | Class | Owner | Restriction |
|---|---|---|---|
| registry.host | A | platform_architecture_lead | No external exposure |
| registry.service_instance | A | platform_architecture_lead | No external exposure |
| registry.shared_service | A | platform_architecture_lead | No external exposure |
| discovery.observed_fact | B | platform_architecture_lead | Internal use; IP addresses present |
| discovery.collection_run | A | platform_architecture_lead | Run metadata only |
| discovery.discovery_source | A | platform_architecture_lead | Source definitions |
| retrieval.document_chunk | B | platform_architecture_lead | May contain configuration details |
| retrieval.chunk_embedding | B | platform_architecture_lead | Vector representations of B-class content |
| retrieval.evidence_pack | B | platform_architecture_lead | Assembled context for agent runs |
| agent_control.agent_run | B | platform_architecture_lead | Run records; may reference B content |
| agent_control.action_request | B | security_and_policy_owner | Governance-sensitive change requests |
| agent_control.prompt_template_registry | B | security_and_policy_owner | Template content; change-request sensitive |
| governance.change_log | B | security_and_policy_owner | Privileged access events; change history |
| docs.document_version | B | platform_architecture_lead | Document content |

---

## 4. Column-Level Classification

No column in any listed table should contain Class C (credential/secret) content.
Violations are caught by the ingest-time redaction scanner (DATA-002).

Specific prohibited column content:
- `observed_fact.content_text`: must not contain passwords, API keys, private keys.
- `document_chunk.chunk_text`: must not contain credentials.
- `evidence_pack` JSON fields: must not contain raw credentials.

---

## 5. Access Rules per Class

| Class | Read | Write | Delete |
|---|---|---|---|
| A | internalcmdb_app + platform_architecture_lead | internalcmdb_app under approval | platform_architecture_lead only |
| B | platform_engineering role + platform_architecture_lead | internalcmdb_app under approval | platform_architecture_lead only |
| C | security_and_policy_owner only | security_and_policy_owner only | executive_sponsor approval |
| D | executive_sponsor approval required | executive_sponsor approval required | Prohibited without legal review |

---

## 6. Verification

- [x] All registry tables can be mapped to at least one class.
- [x] No column carrying credentials is left unclassified.
- [x] Every class has a named owner and access rule.
- [x] No Class C content is permitted in CMDB registry tables.
