---
id: RUN-NNN           # REQUIRED — next available RUN number e.g. RUN-001
title: "<Service or system> — <Procedure name>"  # REQUIRED
doc_class: runbook    # REQUIRED — do not change
domain: infrastructure  # REQUIRED — change to relevant domain
version: "1.0"        # REQUIRED — quoted decimal
status: draft         # REQUIRED
created: YYYY-MM-DD   # REQUIRED
updated: YYYY-MM-DD   # REQUIRED
owner: sre_observability_owner  # REQUIRED — role token of the runbook owner
binding: []           # OPTIONAL — binding entries use format:
                      # - entity_type: registry.services
                      #   entity_id: "<service_name>"
                      #   relation: describes
tags: []
depends_on: []
---

# RUN-NNN: <Service or System> — <Procedure Name>

<!-- Replace RUN-NNN, service name, and procedure name. Remove this comment. -->

## Metadata

| Field | Value |
|-------|-------|
| **Trigger** | <!-- When should this runbook be executed? --> |
| **Severity / Impact** | <!-- What is the severity level? What is the blast radius? --> |
| **Estimated duration** | <!-- How long does this procedure normally take? --> |
| **Requires approval** | <!-- Yes (RC-N per ADR-004) / No --> |
| **Alert / ticket** | <!-- Alert name or ticket that triggered this runbook, if any --> |

## Prerequisites

<!-- List everything that must be true BEFORE starting this runbook.
If a prerequisite is not met, stop and escalate rather than continuing. -->

- [ ] Access to: <!-- list required systems, VMs, services -->
- [ ] Tools available: <!-- e.g. ssh, psql, docker -->
- [ ] Context loaded: <!-- e.g. latest discovery run completed, registry state verified -->
- [ ] Approval obtained: <!-- reference approval record if RC ≥ 2 per ADR-004 -->

## Scope

**In scope:**
<!-- What systems or components will this runbook touch? -->

**Out of scope:**
<!-- What must NOT be touched or changed by this runbook? -->

## Procedure

<!-- Numbered steps. Each step must have a clear action and a stated expected outcome.
If a step can fail, include a "What to do if this fails" note. -->

### Step 1 — <Action summary>

```bash
# Example command
```

**Expected outcome:** <!-- What should you see when this step succeeds? -->

**If this fails:** <!-- Stop and escalate, or see Step X, or ... -->

---

### Step 2 — <Action summary>

<!-- ... -->

---

### Step N — Verify success

<!-- Final verification step that confirms the procedure worked correctly. -->

**Verification checks:**

- [ ] <!-- Check 1 — e.g. service responds on port 5432 -->
- [ ] <!-- Check 2 — e.g. registry record updated with correct state -->
- [ ] <!-- Check 3 — e.g. no error log entries in last 5 minutes -->

## Rollback

<!-- At least one rollback procedure. If rollback is not possible, state that explicitly
and describe the recovery path. -->

### Rollback — <Summary of how to undo this procedure>

1. <!-- Rollback step 1 -->
2. <!-- Rollback step 2 -->

**Verify rollback:** <!-- How to confirm the rollback was successful -->

## Audit Trail

<!-- Document actions taken when this runbook is executed -->

| Field | Value |
|-------|-------|
| Executed by | |
| Execution date | |
| Approval reference | |
| Outcome | success / partial / failed |
| Registry records updated | yes / no — list IDs |
| Incident or ticket reference | |

## Related Documents

<!-- Remove if empty -->

- [[doc:]] — reason
