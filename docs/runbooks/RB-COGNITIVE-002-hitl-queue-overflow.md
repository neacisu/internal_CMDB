---
id: RB-COGNITIVE-002
title: HITL Queue Overflow Runbook Procedure
doc_class: runbook
domain: governance
version: "1.0"
status: draft
created: 2026-03-22
updated: 2026-03-23
owner: sre_observability_owner
binding:
  - entity_type: registry.service
    entity_id: hitl-workflow
    relation: describes
---

# RB-COGNITIVE-002 — HITL Queue Overflow

## Problem

The Human-In-The-Loop review queue has accumulated more items than reviewers
can process within SLA thresholds, causing automatic escalations and
eventual auto-blocking of pending items.

## Symptoms

- HITL dashboard shows > 20 pending items
- Multiple items showing `status = 'escalated'` or `status = 'blocked'`
- Prometheus alert `HITLQueueOverflow` firing (threshold: 20 items)
- API logs: `"Auto-escalated N HITL items"`
- Legitimate RC-2/RC-3 actions being blocked due to escalation overflow

## Impact

- **Medium-High** — Remediation actions are delayed; RC-3 items with
  operational urgency (certificate rotation, LLM engine restart) stall.
- After 3 escalations, items are auto-blocked requiring manual intervention.

## Steps to Resolve

1. **Assess the queue:**
   ```bash
   curl -s https://infraq.app/api/v1/hitl/queue?status=pending | jq '. | length'
   curl -s https://infraq.app/api/v1/hitl/queue?status=escalated | jq '. | length'
   ```

2. **Prioritise critical items:**
   - Sort by `risk_class` (RC-4 first, then RC-3)
   - Use the `/hitl/bulk-decide` endpoint for batch decisions

3. **Bulk approve low-risk items:**
   ```bash
   curl -X POST https://infraq.app/api/v1/hitl/bulk-decide \
     -H "Content-Type: application/json" \
     -d '{"item_ids": [...], "decision": "approved", "reason": "bulk triage"}'
   ```

4. **Investigate root cause of volume spike:**
   - Check if a noisy insight source is generating excessive items
   - Review guard gate thresholds — RC-2 items should auto-approve if
     confidence > 0.9

5. **Temporarily adjust escalation thresholds:**
   ```sql
   -- Extend RC-2 SLA from 4h to 8h (emergency only)
   -- Coordinate with the team before applying
   ```

## Prevention

- Set up auto-approve rules for high-confidence RC-1/RC-2 items
- Schedule daily HITL review sessions (15 min)
- Alert when queue depth exceeds 20 items (early warning)
- Review and tune guard gate risk classification monthly
