---
id: RES-NNN           # REQUIRED — next available RES number e.g. RES-001
title: "<Topic> — Research Dossier"  # REQUIRED
doc_class: research_dossier  # REQUIRED — do not change
domain: platform-foundations  # REQUIRED — change to relevant domain
version: "1.0"        # REQUIRED — quoted decimal
status: draft         # REQUIRED
created: YYYY-MM-DD   # REQUIRED
updated: YYYY-MM-DD   # REQUIRED
owner: platform_architecture_lead  # REQUIRED — role token
binding: []
tags: []
depends_on: []
---

# RES-NNN: <Topic> — Research Dossier

<!-- Replace RES-NNN and Topic. Remove this comment. -->

## Purpose of This Investigation

<!-- 1-2 paragraphs: What question or problem is being investigated?
What decision or work package does this research feed into?
What is the scope boundary — what is NOT being investigated here? -->

## Investigation Scope

**In scope:**
<!-- What was examined / tested / measured -->

**Out of scope:**
<!-- What was explicitly excluded and why -->

**Timeline:**
<!-- From YYYY-MM-DD to YYYY-MM-DD -->

## Findings

<!-- Present findings as numbered, factual statements.
Distinguish clearly between: observed facts, measurements, inferences, and open questions.

Format:
F-01: [FACT] ...
F-02: [MEASUREMENT] ...
F-03: [INFERENCE] ...
F-04: [OPEN] ...
-->

### F-01 — <Finding title>

<!-- Describe the finding. Include:
- How was it observed/measured?
- What is the evidence?
- What is the confidence level?
- Is this canonical / observed / inferred?
-->

**Evidence:** <!-- reference to file, log, query, test run -->
**Confidence:** <!-- high / medium / low + rationale -->

---

### F-02 — <Finding title>

<!-- ... -->

## Analysis

<!-- Interpret the findings. State explicitly:
- What do the findings confirm or contradict?
- What assumptions were invalidated?
- What constraints does this impose on the solution?
-->

## Recommendations

<!-- Numbered recommendations derived from the analysis.
Each recommendation must reference at least one finding. -->

1. **Rec-01**: <!-- Recommendation text — based on F-0N -->
2. **Rec-02**: <!-- ... -->

## Decision Feed

<!-- Which decisions, ADRs, or work packages should consume this research? -->

| Decision / Task | How this research applies |
|----------------|-----------------------------|
| [[doc:ADR-NNN]] | <!-- what it informs --> |

## Open Questions

<!-- Questions that arose during investigation but were not resolved. -->

1. <!-- Question 1 — owner / deadline for resolution -->
2. <!-- ... -->

## Evidence Artifacts

<!-- List all evidence files, logs, scripts, or test outputs referenced in this dossier. -->

| Artifact | Location | Description |
|----------|----------|-------------|
| <!-- name --> | <!-- path or URL --> | <!-- what it shows --> |
