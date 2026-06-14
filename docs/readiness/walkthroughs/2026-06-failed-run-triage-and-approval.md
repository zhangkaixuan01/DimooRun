# Walkthrough: Failed-Run Triage And Approval Decision

## Roles

- Agent developer
- Governance/security reviewer
- Auditor

## Workflow Scope

- Failed-run triage
- Approval decision

## Preconditions

- A run exists with attempts, events, and failure evidence
- Human approval and policy workflows are enabled in the current scope
- Operator can access run detail, replay comparison, and approval queues

## Walkthrough

1. Open the failed run and inspect attempts, events, output, error, deployment/version context, and linked runtime evidence before deciding whether to retry or replay.
2. Classify the failure as transient, governed, dependency-related, or code/config-related by correlating events, attempts, and recent deployment change context.
3. If the next action is risky or blocked by policy, open the approval decision path and inspect requester identity, policy match, affected resources, and risk reason before acting.
4. Record an approval decision only after the decision context, audit reason, and expected runtime resume outcome are visible.
5. Return to the run or replay workflow and verify whether the resumed or replayed action produced a new run/task record without mutating the original evidence.

## Evidence Produced

- Failed-run detail with attempts, events, and audit-linked follow-up actions
- Replay comparison or retry records linked to the source run
- Human task decision record with actor, timestamp, and resume result
- Browser workflow proof from replay comparison, policy approval, and live approval smoke paths

## Friction Log

- The run triage evidence is strong, but the operator still has to switch mental context between run detail and approval workbench instead of using one integrated runtime workbench.
- Approval decisions surface policy and audit data, but side-by-side diff and affected-resource evidence can still feel fragmented for complex changes.
- Replay, retry, and approval outcomes are all auditable, but the product still lacks a single evidence bundle export for the whole failed-run investigation.

## Follow-Up Backlog Items

- Add a unified run workbench that combines run detail, replay, approval context, and linked audit evidence in one operator workflow.
- Add a reusable affected-resource diff panel for approval decision, replay candidate comparison, and rollback flows.
- Add evidence bundle export for failed-run triage and approval decision so one investigation can be shared without manual reconstruction.
