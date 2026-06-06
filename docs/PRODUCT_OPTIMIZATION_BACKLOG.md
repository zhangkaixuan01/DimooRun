# Product Optimization Backlog

This backlog prioritizes product optimizations that reinforce runtime control, operational trust, migration confidence, governance, quality, or developer activation. Items outside those values should be removed or deferred.

Priority rules:

- `P0`: Must be completed before External GA because it unblocks activation, runtime trust, governance safety, compatibility confidence, or production recovery.
- `P1`: Belongs to Competitive Excellence after GA-critical workflows are safe.
- `P2`: Later roadmap only, unless product evidence shows it removes a real activation or recovery blocker.

## Priority Table

| Priority | User | Value | Risk | Engineering Risk | Effort | Dependency | Phase | Read Model | Console Workflow | Browser Evidence | Non-goal Guardrail |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P0 | Agent developer, platform operator | Guided activation from dependency check to first successful run. | Users fail before seeing product value. | Cross-service health can drift from real runtime behavior. | L | Phase -3, -2, -1A, 12A | Phase 12A | Activation checklist, dependency health, first-run progress. | First-run setup wizard/workbench. | Success, failed dependency, empty state, mobile. | Not a builder; uses example agent package. |
| P0 | Agent developer, incident responder | Runtime workbench unifies run, task, timeline, attempts, artifacts, traces, audit, replay, and compare. | Failed-run recovery remains fragmented. | Aggregate reads can become inconsistent with source event semantics. | L | Phase -1C, 0C, 5 | Phase 0C | Run evidence aggregate. | Run triage and replay workbench. | Failed run, replay, permission denial, responsive. | Runtime white box only; no business semantic editor. |
| P0 | Governance/security reviewer | Impact preview for high-risk actions. | Dangerous actions lack decision context. | Affected-resource calculation can miss indirect dependencies. | M | Phase -1C, 0B, 0D, 9 | Phase 0B | Action summary and affected-resource graph. | Promotion, policy, approval, settings, restore confirmations. | Blocked and successful high-risk actions. | No Policy Engine bypass. |
| P0 | Platform operator, incident responder | Action center for approvals, failed validations, stuck tasks, unhealthy workers, expiring keys, failed backups, budget breaches, incidents. | Operators miss urgent work. | Pending-action aggregation needs stable dedupe and severity semantics. | L | Phase -1C, 0G, 0J, 0K, 0M | Phase -1C | Pending actions aggregate. | Global action queue with drilldown. | Empty, loading, error, action resolution. | Not ticketing/ITSM. |
| P0 | Governance/security reviewer, platform operator | Resource graph for dependencies and used-by impact. | Changes break hidden dependents. | Graph maintenance can lag writes without clear ownership. | L | Phase -1C, 0B, 0E, 0K, 0O | Phase 0O | Resource dependency graph. | Used-by panels and impact previews. | Key rotation, deployment change, asset rollback. | Graph is operational dependency, not visual workflow builder. |
| P0 | Incident responder, auditor | Evidence bundles for incidents, failed runs, replay comparisons, policy decisions, deployment promotions. | Evidence is incomplete or hard to share. | Bundle redaction must match source authorization. | M | Phase 0C, 0D, 0G, 5 | Phase 0G | Evidence bundle read model. | Export/link evidence from workbench and audit pages. | Bundle creation and redaction. | Evidence-bound notes only. |
| P0 | Compatibility adopter | Capability explainers for adapters and migration paths. | Users hit unsupported semantics late. | Capability claims can become stale as adapters change. | M | Phase 0A, 0I, 8 | Phase 0I | Capability matrix and compatibility result. | Package validation and compatibility explorer. | Unsupported capability and recommended workaround. | Does not fork/replace external frameworks. |
| P0 | Platform operator | Integration health center for model gateway, secret provider, object store, Redis, Postgres, notifications, webhooks, observability. | Dependency failure root cause is unclear. | Health checks can overload dependencies or report false positives. | M | Phase 5, 0L, 10 | Phase 0L | Integration health aggregate. | Settings/operations health center. | Healthy/degraded/offline states. | Not a generic monitoring product. |
| P0 | Auditor, governance reviewer | Compare/diff primitive for deployment, policy, role, asset, replay, and setting changes. | Reviewers approve changes without understanding delta. | Type-specific diffs need stable normalization. | M | Phase 0B, 0D, 0K, 0O | Phase 7 | Diff summaries by resource type. | Diff panels inside high-risk workflows. | Diff navigation and approval. | Diff supports control-plane review only. |
| P1 | Agent developer, incident responder | Feedback capture from run detail and replay into datasets. | Quality loop lacks production evidence. | Feedback schema can diverge from dataset item schema. | M | Phase 0C, 0F | Phase 0F | Feedback and dataset capture aggregate. | Rate/correct/label and capture workflow. | Capture success, validation error. | Not a generic annotation platform. |
| P1 | Platform operator | Saved operational views for runs, incidents, costs, audit logs, worker health, request logs. | Users repeatedly rebuild investigative filters. | Saved filters require versioned query contracts. | M | Phase 5, 0H, 0J, 0M | Phase 7 | Saved view model. | Save/share filter views. | Save, load, permission error. | Not dashboard builder. |
| P1 | Platform operator, governance reviewer | Environment promotion lanes across deployment, settings, gateway, policy, and quality workflows. | Dev/staging/prod intent is unclear. | Cross-environment links can create scope leaks. | L | Phase 0B, 0D, 0H, 0L | Phase 0B | Environment lane summary. | Promote across environment scopes. | Promotion blocker and rollback. | Not CI/CD replacement. |
| P1 | Product maintainer | Product telemetry for activation failures and recovery friction. | Product cannot improve based on real usage. | Telemetry can violate redaction or retention expectations. | M | Trust/security docs, Phase 5, Phase 12B | Phase 12B | Redacted tenant/project-scoped telemetry events. | Admin telemetry settings and reports. | Disable, sampled event, redaction proof. | No secret or prompt payload collection. |
| P1 | Incident responder, auditor | Collaboration notes bound to runtime/deployment/approval/replay/incident evidence. | Investigation context is lost. | Notes must inherit evidence authorization and audit behavior. | M | Evidence bundles, audit | Phase 0G | Evidence-bound comments. | Notes on evidence records. | Create/edit/delete with audit. | No task assignment, kanban, SLA ticket routing, or ITSM replacement. |
| P1 | All roles | Polished empty states with next action by role and scope. | Empty pages feel like broken CRUD. | Empty-state recommendations can become inconsistent with permissions. | S | Phase -3, -1A, 7 | Phase 7 | Role/scope-aware empty-state metadata. | Empty states across core pages. | Empty state assertions. | No marketing landing content inside app. |
| P2 | Auditor, platform operator | Advanced export formats for evidence and audit data. | Export scope can become compliance-product sprawl. | Export jobs need retention, auth, and redaction guarantees. | M | Evidence bundles, trust docs | Later roadmap | Export job metadata. | Export evidence bundle. | Export generated and redacted. | Avoid full compliance suite scope. |
| P2 | Agent developer | Deeper local developer diagnostics in Console. | Could duplicate CLI/SDK responsibilities. | Diagnostics can require environment-specific probes. | M | SDK/CLI completion | Later roadmap | Developer diagnostic summary. | Developer diagnostics panel. | Diagnostic success/error. | Console remains operations/control plane. |

## Backlog Budget Rules

| Rule | Requirement |
|---|---|
| P0 budget | P0 items must be implemented before External GA or explicitly downgraded with evidence that they no longer block activation, runtime trust, governance safety, compatibility confidence, or production recovery. |
| P1 budget | P1 items belong to Competitive Excellence unless a measured activation/recovery blocker promotes them to P0. |
| P2 budget | P2 items stay out of production-grade scope unless they remove a proven blocker without broadening product category. |
| Scope budget | Any item that cannot map to runtime control, operational trust, migration confidence, governance, quality, or developer activation must be removed or moved to later ideas. |

## Exit Rules

Remove or defer an optimization when any of these are true:

| Exit rule | Reason |
|---|---|
| It turns DimooRun into a low-code agent builder, prompt design platform, workflow canvas, business app builder, generic model gateway, billing platform, ticketing system, kanban, SLA router, or ITSM replacement. | Violates product positioning. |
| It cannot name a user role, job, decision, risk, and recovery path from `docs/CONSOLE_USER_TASK_MODEL.md`. | Not grounded in user work. |
| It cannot identify a backend read model or workflow API needed to make the UI reliable. | Likely to become page-local fragile UX. |
| It cannot define browser evidence. | Not verifiable as product quality. |
| It collects secret values, prompt payloads, hidden run payloads, or unrestricted business content. | Violates trust and redaction posture. |

## Telemetry Requirements

Telemetry-related work must satisfy all requirements before implementation:

| Requirement | Rule |
|---|---|
| Tenant/project scope | Telemetry events must include scope boundaries and must not aggregate across tenants without explicit operator-approved reporting semantics. |
| Redaction | Secret values, prompt payloads, run input/output payloads, and hidden audit payloads must not be collected. |
| Sampling | High-volume telemetry must be sampled or aggregated with documented defaults. |
| Retention | Retention must be configurable and documented. |
| Disable behavior | Operators must be able to disable product telemetry where deployment policy requires it. |
| Trust docs | Data categories, purpose, retention, and disable behavior must be documented in `docs/TRUST_AND_SECURITY.md` before telemetry is marketed. |

## Collaboration Requirements

Collaboration-related work must satisfy all requirements before implementation:

| Requirement | Rule |
|---|---|
| Evidence-bound | Notes must attach to runtime, deployment, approval, replay, incident, audit, or restore evidence. |
| Audited | Create/update/delete of notes must produce audit records where required. |
| Redacted | Notes must follow the same redaction and permission model as the evidence they reference. |
| Explicit non-goals | No generic project management, task assignment, kanban, SLA ticket routing, or ITSM replacement scope. |

## Maintenance Rule

Every optimization added to this backlog must include priority, user, value, product risk, engineering risk, effort, dependency, phase, read model, Console workflow, browser evidence, and non-goal guardrail. Missing columns mean the item is not ready for roadmap execution.
