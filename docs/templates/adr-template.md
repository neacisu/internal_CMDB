---
id: ADR-NNN           # REQUIRED — next available ADR number e.g. ADR-006
title: "<Decision summary — one line>"  # REQUIRED — active voice, e.g. "Use X for Y"
doc_class: adr        # REQUIRED — do not change
domain: platform-foundations  # REQUIRED — change to relevant domain
version: "1.0"        # REQUIRED — quoted decimal
status: draft         # REQUIRED — start as draft, progress to in-review → approved
created: "2026-03-09"   # REQUIRED — date you create this file
updated: "2026-03-09"   # REQUIRED — date of last edit
owner: architecture_board  # REQUIRED — role token of the deciding authority
binding: []           # OPTIONAL — binding entries use format:
                      # - entity_type: registry.hosts  # schema.table
                      #   entity_id: "<hostname>"
                      #   relation: governs
tags: []              # OPTIONAL — relevant keyword tags
depends_on: []        # OPTIONAL — ADR IDs this decision depends on
---

# ADR-NNN: <Decision Summary>

<!-- Replace ADR-NNN and the decision summary with real values. Remove this comment. -->

## Context

<!-- 1-3 paragraphs describing:
- The problem or situation requiring a decision
- The constraints that apply (technical, operational, policy)
- Any prior decisions that set the frame for this one
- References to blueprint sections or observed infrastructure state

Example:
"The platform needs a single authoritative store for host and service records.
Without a consistent system of record, discovery results, agent writes, and
human edits have no defined merge order, causing drift between observed and
canonical state."
-->

## Decision

<!-- One unambiguous sentence naming the decision. Start with "We will..." or "The platform will...".

Example:
"The platform will use PostgreSQL 17 as the single authoritative operational
registry for all host, service, application, and ownership records."
-->

## Alternatives Considered

<!-- List at least one rejected alternative with a brief rationale.
Format: bullet list, each item = "Alternative — Reason rejected" -->

- **Alternative 1** — reason rejected
- **Alternative 2** — reason rejected

## Consequences

### Rules Derived from This Decision

<!-- State the binding rules as imperatives. These become enforceable constraints. -->

1. <!-- Rule 1 — "No X may Y without Z" -->
2. <!-- Rule 2 — ... -->

### Positive Consequences

<!-- What gets simpler, safer, or more consistent as a result? -->

-

### Negative Consequences / Trade-offs

<!-- What is harder, slower, or more constrained? Be honest. -->

-

## Implementation Bindings

<!-- List the code paths, schema elements, or config files that must implement this decision.
Remove items that do not apply. -->

- Schema: `registry.<table>` owns the canonical record
- Code: `src/internalcmdb/<module>/` enforces this constraint
- Policy: referenced in [[doc:GOV-002]] operating rules

## Review Notes

<!-- Optional: notes from review cycle, open questions at time of approval, etc. -->

<!-- Remove this section if empty before setting status: approved -->
