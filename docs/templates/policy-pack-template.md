---
id: POL-NNN           # REQUIRED — next available POL number e.g. POL-003
title: "<Domain> — <Policy name>"  # REQUIRED
doc_class: policy_pack  # REQUIRED — do not change
domain: platform-foundations  # REQUIRED — change to relevant domain
version: "1.0"        # REQUIRED — quoted decimal
status: draft         # REQUIRED
created: "2026-03-09"   # REQUIRED
updated: "2026-03-09"   # REQUIRED
owner: platform_program_manager  # REQUIRED — role that owns this policy
binding: []
tags: []
depends_on: []
---

# POL-NNN: <Domain> — <Policy Name>

<!-- Replace POL-NNN, domain, and policy name. Remove this comment. -->

## Purpose

<!-- 1-2 paragraphs: What risk or operational need does this policy address?
What is the scope of applicability — which systems, roles, or workflows does it govern? -->

## Scope

**Applies to:** <!-- list of roles, systems, or operations subject to this policy -->

**Effective from:** <!-- YYYY-MM-DD -->

**Supersedes:** <!-- Previous policy ID or "none" -->

## Policy Rules

<!-- State each rule in imperative form using "must", "must not", or "may".
Group related rules under sub-headings. Each rule is numbered for reference. -->

### <Rule Group 1>

**P-01**: <!-- Statement using "must" / "must not" / "may" + who + what + when/how -->

**P-02**: <!-- ... -->

### <Rule Group 2>

**P-03**: <!-- ... -->

## Exceptions

<!-- Describe how exceptions to this policy are obtained and tracked.
If no exceptions are permitted, state that explicitly. -->

All exceptions require written approval from the `<!-- owner role token -->` and must be logged in `governance.change_log` with:
- Requesting party
- Justification
- Scope of exception
- Expiry date

## Enforcement

<!-- How is compliance with this policy enforced or verified?
Automated checks? Manual audits? CI/CD gates? -->

| Enforcement mechanism | Frequency | Owner |
| --- | --- | --- |
| <!-- mechanism --> | <!-- frequency --> | <!-- role token --> |

## Escalation

Per [[doc:GOV-001]]: non-compliance or ambiguity escalates through the L1→L4 model documented in the ownership matrix.

## Related Policies and ADRs

<!-- Remove if empty -->

| Document | Relation |
| --- | --- |
| [[doc:ADR-NNN]] | <!-- how it relates --> |

## Revision History

| Version | Date | Changed by | Summary |
| --- | --- | --- | --- |
| 1.0 | <!-- YYYY-MM-DD --> | <!-- role token --> | Initial policy |
