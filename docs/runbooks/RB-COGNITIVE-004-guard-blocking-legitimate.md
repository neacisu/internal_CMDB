---
id: RB-COGNITIVE-004
title: Guard Blocking Legitimate Requests Runbook
doc_class: runbook
domain: governance
version: "1.0"
status: draft
created: 2026-03-22
updated: 2026-03-23
owner: sre_observability_owner
binding:
  - entity_type: registry.service
    entity_id: guard-gate
    relation: describes
---

# RB-COGNITIVE-004 — Guard Blocking Legitimate Requests

## Problem

The GuardGate 5-level evaluation pipeline is incorrectly blocking
legitimate actions or queries — false positives from the redaction
scanner, LLM Guard, or policy enforcer.

## Symptoms

- Users report "action blocked" for operations that should succeed
- Debug endpoint `/debug/guard-blocks` shows increasing block count
- HITL queue receives items that should have been auto-approved
- API returns 403 with `"L1 redaction"`, `"L2 llm-guard"`, or
  `"L3 policy"` reasons for valid requests
- Cognitive query accuracy drops (guard blocks valid prompts)

## Impact

- **Medium** — Operational actions are delayed; user frustration increases.
- Automated remediation stalls for RC-1/RC-2 actions.
- False-positive rate erodes trust in the cognitive system.

## Steps to Resolve

1. **Check the block log:**
   ```bash
   curl -s https://infraq.app/api/v1/debug/guard-blocks?limit=20 | jq .
   ```

2. **Identify which guard level is blocking:**
   - **L1 (Redaction):** Check if the payload contains patterns that
     match PII/credential regexes but are actually benign (e.g., test
     UUIDs that look like SSNs).
     - Fix: Add exceptions to `RedactionScanner` allowlist.
   - **L2 (LLM Guard):** The external LLM Guard API may be overly
     sensitive.
     - Fix: Adjust threshold scores in LLM Guard config, or add the
       specific phrase to the allowlist.
   - **L3 (Policy Enforcer):** A governance policy is too restrictive.
     - Fix: Update the policy in the governance schema or add a
       time-window exception.

3. **Temporarily bypass for urgent operations:**
   ```bash
   # Use the debug override (requires admin role)
   curl -X POST https://infraq.app/api/v1/debug/guard-override \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -d '{"action_id": "...", "reason": "false positive - RB-COGNITIVE-004"}'
   ```

4. **Update scanner rules:**
   - Edit `src/internalcmdb/governance/redaction_scanner.py`
   - Add test cases for the false-positive pattern
   - Deploy via `make deploy-api`

## Prevention

- Track false-positive rate as a metric (target: < 1%)
- Weekly review of guard block logs
- A/B test scanner rule changes against a sample of recent queries
- Maintain an allowlist for known-safe patterns in the infrastructure domain
