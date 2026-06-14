# Walkthrough: Incident Recovery

## Roles

- Incident responder
- Platform operator
- Auditor

## Workflow Scope

- Incident recovery

## Preconditions

- Incident, notification, backup, and restore workflows available in the selected scope
- Operator can access incident timeline, notification delivery attempts, and backup/restore dry-run pages
- Runtime scope and destructive confirmation requirements are visible before any restore action

## Walkthrough

1. Open the incident detail or triage surface and review the linked runs, tasks, events, notification delivery attempts, and current resolution status before changing runtime state.
2. Acknowledge the incident with an audit note and verify the timeline records who acted, what evidence was linked, and which channels were notified.
3. If runtime recovery requires data validation, open backup and restore dry-run workflows and confirm scope headers, object-store reference, destructive confirmation phrase, and validation output before proceeding.
4. Resolve the incident only after the resolution summary, affected evidence, and notification attempts are visible in the same recovery story.
5. Confirm the final incident state, restore validation result, and audit trail can explain what changed and what did not change.

## Evidence Produced

- Incident acknowledge and resolve timeline entries
- Linked runtime evidence and delivery attempts
- Backup dry-run and restore dry-run validation output
- Browser workflow proof from enterprise operations and backup/restore specs

## Friction Log

- Incident and backup/restore workflows are present, but there is still no single action center that pulls incident pressure, restore readiness, and provider health into one recovery queue.
- The product explains destructive restore confirmation and validation, but operators still need to move between incident, notification, and restore pages to complete the full incident recovery story.
- Recovery evidence is auditable, but runbook-style next actions are still more document-driven than product-driven once the operator leaves the incident page.

## Follow-Up Backlog Items

- Add an action center that groups incidents, failed notifications, restore blockers, and unhealthy providers by environment and urgency.
- Add direct links from incident recovery to backup validation and restore dry-run results so the operator can stay inside one recovery lane.
- Add recovery evidence bundles that combine incident timeline, linked runtime evidence, notification attempts, and restore validation into one exportable record.
