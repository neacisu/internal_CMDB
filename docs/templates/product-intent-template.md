---
id: APP-NNN           # REQUIRED — next available APP number e.g. APP-001
title: "<Application name> — Product Intent"  # REQUIRED
doc_class: product_intent  # REQUIRED — do not change
domain: application   # REQUIRED — change if needed
version: "1.0"        # REQUIRED — quoted decimal
status: draft         # REQUIRED
created: "2026-03-09"   # REQUIRED
updated: "2026-03-09"   # REQUIRED
owner: platform_engineering_lead  # REQUIRED — role token
binding:
  - entity_type: registry.applications  # REQUIRED for application docs — do not change schema.table
    entity_id: "<app_name>"             # REQUIRED — replace with canonical application name
    relation: describes
tags: []
depends_on: []
---

# APP-NNN: <Application Name> — Product Intent

<!-- Replace APP-NNN and Application Name. Remove this comment. -->

## Application Identity

| Field | Value |
| --- | --- |
| **Application name** | <!-- canonical name matching registry.applications --> |
| **Application type** | <!-- service / CLI / daemon / agent / batch --> |
| **Registry entity** | `[[entity:registry.applications:<app_name>]]` |
| **Owning team role** | <!-- canonical role token --> |
| **Deployment target** | <!-- hostname or cluster --> |

## Purpose Statement

<!-- 2-3 sentences: What problem does this application solve?
Who are its users or consumers?
What outcome does it produce? -->

## Scope

**In scope for this application:**
<!-- What capabilities belong here -->

**Out of scope:**
<!-- What is explicitly not this application's responsibility -->

## Context Boundary

<!-- What is the application's bounded context?
What data does it own exclusively?
What shared data does it consume (read-only)? -->

**Owns:**
<!-- data / state / resources exclusively owned -->

**Consumes (read-only):**
<!-- data from registry, services, or other apps -->

**Produces (canonical outputs):**
<!-- what this app writes to the registry or event stream -->

## Functional Requirements

<!-- List key functional requirements. Use imperative "must" statements.
These feed into verification specs (VER-NNN). -->

**FR-01**: <!-- The application must ... -->

**FR-02**: <!-- ... -->

## Non-Functional Requirements

| Property | Requirement | Source |
| --- | --- | --- |
| Availability | <!-- e.g. 99.5% / 4h RTO --> | [[doc:POL-001]] |
| Security | <!-- e.g. no direct external access, auth required --> | [[doc:POL-002]] |
| Auditability | <!-- e.g. all writes logged --> | [[doc:ADR-004]] |

## Dependencies

| Dependency | Type | Version constraint |
| --- | --- | --- |
| <!-- service or library --> | <!-- runtime / build --> | <!-- e.g. >=3.2 --> |

## Verification Reference

<!-- Link to the verification spec for this application -->

Acceptance testing defined in: [[doc:VER-NNN]]

## Open Decisions

<!-- Decisions not yet made that block design or implementation -->

1. <!-- Decision — who owns it — target date -->
