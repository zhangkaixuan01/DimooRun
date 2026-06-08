# Console Experience Acceptance

This document defines the minimum user experience acceptance criteria for DimooRun Console workflows. It turns the task model in `console-user-task-model.md` into testable product expectations.

Each workflow must be evaluated by user outcome, visible system state, validation, empty/loading/error behavior, keyboard use, responsive behavior, and recovery guidance.

## Global Acceptance Rules

| Area | Acceptance criteria |
|---|---|
| Task completion | The user can complete the intended job without editing raw JSON unless the job is explicitly a developer/admin advanced path. |
| Visible system status | Current tenant, project, environment, resource status, dependency health, and last update are visible before important decisions. |
| Field validation | Invalid input is blocked before submit when possible, points to the field, explains the constraint, and preserves user input. |
| Empty state | Empty state names the resource, why it is empty, and the next correct action for the role and scope. |
| Loading state | Loading state keeps layout stable, identifies the region being loaded, and does not make destructive actions available. |
| Error state | Error state normalizes API errors, preserves context, names retryability, and links to logs/evidence where available. |
| Keyboard flow | Interactive controls are reachable by keyboard, focus order matches reading order, Escape closes dialogs/drawers, and focus is restored. |
| Responsive behavior | Workflows remain usable at mobile, tablet, laptop, and desktop widths without overlapping text or hiding required risk context. |
| Authorization | Disabled actions show required permission and disabled reason. Hidden controls are not used as the only authorization model. |
| Auditability | High-risk actions require an audit reason where policy requires it and show the resulting audit record. |

## Core Workflow Acceptance

### First-Run Setup

| Check | Acceptance criteria |
|---|---|
| Task completion | User can select scope, verify dependencies, create or identify credentials, register an example agent, deploy it, submit a task, and inspect the run. |
| Visible system status | Shows server, worker, database, Redis, object store, Console API, selected scope, and runtime mode. |
| Field validation | Blocks missing scope, invalid package URI, missing manifest, unsupported framework/runtime pair, and missing required secret references. |
| Empty state | Empty agent/deployment/run states point to the next setup step. |
| Loading state | Health checks and validation show progress without enabling dependent actions early. |
| Error state | Failed step shows exact failing dependency or validation issue and retry guidance. |
| Keyboard flow | Setup navigation, validation, submit, and retry are keyboard reachable. |
| Responsive behavior | Setup remains linear and readable on 375px width with status and next action visible. |

### Agent Package And Version Readiness

| Check | Acceptance criteria |
|---|---|
| Task completion | User can upload or reference a package, preview manifest, validate compatibility, and understand why a version is or is not ready. |
| Visible system status | Shows framework, adapter, entrypoint, version status, validation result, required secrets, dependency warnings, and capability result. |
| Field validation | Blocks malformed manifest, invalid package URI, unsupported adapter, missing entrypoint, and unsafe local URI in production mode. |
| Empty state | No versions state explains how to register a package and what readiness means. |
| Loading state | Package validation is explicit and prevents status promotion until complete. |
| Error state | Validation errors are grouped by manifest, dependency, secret, capability, and policy. |
| Keyboard flow | Manifest preview, validation result, and readiness action are keyboard navigable. |
| Responsive behavior | Manifest and validation panes stack without losing action summary. |

### Deployment Promotion And Rollback

| Check | Acceptance criteria |
|---|---|
| Task completion | User can promote, pause, resume, drain, stop, restart, and roll back with impact preview and audit reason. |
| Visible system status | Shows desired status, runtime status, current version, candidate version, active runs, queued tasks, policy warnings, and rollback target. |
| Field validation | Blocks invalid candidate, missing audit reason, incompatible config, and policy-denied action. |
| Empty state | No deployments state directs the user to create a deployment from a ready version. |
| Loading state | Control action has busy state and prevents duplicate submits. |
| Error state | Failed control action shows current state after failure and whether retry or rollback is available. |
| Keyboard flow | Impact dialog traps focus, supports Escape, restores focus, and has explicit confirm/cancel order. |
| Responsive behavior | Impact preview and confirmation remain readable without horizontal scrolling on mobile. |

### Run Triage

| Check | Acceptance criteria |
|---|---|
| Task completion | User can inspect input/output visibility, error, attempts, events, artifacts, trace, audit, cost, and choose retry/replay/dataset/incident next action. |
| Visible system status | Shows run state, task state, deployment/version, timing, attempts, policy decisions, redaction state, and related incidents. |
| Field validation | Blocks retry/replay when state or permissions do not allow it and explains why. |
| Empty state | No runs state points to task submission or filters that may hide data. |
| Loading state | Timeline, events, and artifacts load independently without shifting the page. |
| Error state | Missing or redacted payloads explain authorization/redaction reason. |
| Keyboard flow | Timeline, tabs, evidence links, and actions are keyboard reachable. |
| Responsive behavior | Timeline and detail panels collapse into a readable single-column workbench. |

### Replay Comparison

| Check | Acceptance criteria |
|---|---|
| Task completion | User can select a source run and candidate version, create replay, compare output/events/errors/latency, and save evidence to dataset or experiment. |
| Visible system status | Shows source run, candidate, replay status, diff summary, provenance, and regression classification where available. |
| Field validation | Blocks missing source run, invalid candidate, incompatible input, and duplicate replay without idempotency handling. |
| Empty state | No replay jobs state explains how to start from a failed run. |
| Loading state | Replay creation and diff generation have independent progress. |
| Error state | Replay failure links back to source run and candidate validation. |
| Keyboard flow | Diff navigation is keyboard reachable and announces changed sections. |
| Responsive behavior | Diff view provides stacked summaries when side-by-side layout does not fit. |

### Policy Authoring And Simulation

| Check | Acceptance criteria |
|---|---|
| Task completion | User can build a condition, simulate against action/resource/scope, preview impact, activate with audit reason, and roll back. |
| Visible system status | Shows policy status, matched resources, conflicts, warnings, required permissions, and last activation. |
| Field validation | Blocks malformed condition, unsupported operator, missing scope, conflict requiring resolution, and missing audit reason. |
| Empty state | No policies state offers a safe template and simulation-first path. |
| Loading state | Simulation is visibly running and activation remains blocked until result is available. |
| Error state | Policy parse and simulation errors point to exact condition segment when possible. |
| Keyboard flow | Condition builder and simulation result are usable without mouse. |
| Responsive behavior | Builder, preview, and impact summary stack while keeping activate action visible after review. |

### Human Approval

| Check | Acceptance criteria |
|---|---|
| Task completion | Reviewer can understand requester, action, risk, policy reason, resource diff, approve/reject/comment, and see resume result. |
| Visible system status | Shows assignment, SLA or age if configured, requester, affected scope, policy match, audit requirement, and current runtime wait state. |
| Field validation | Blocks empty required comment, stale decision, missing permission, and already-decided task. |
| Empty state | Empty queue explains filters and where pending actions appear globally. |
| Loading state | Decision submit disables duplicate decisions and preserves comment. |
| Error state | Resume failure is separated from decision persistence and shows next action. |
| Keyboard flow | Queue selection, detail review, comment, approve, and reject support keyboard flow. |
| Responsive behavior | Queue and detail become stacked while preserving decision controls after context. |

### Model Gateway, Tool Gateway, And Secret Governance

| Check | Acceptance criteria |
|---|---|
| Task completion | User can configure provider/tool/secret reference, validate binding, simulate or dry-run where safe, bind policy, and inspect usage. |
| Visible system status | Shows provider health, credential ref status, risk class, policy binding, last used, quota/budget, and runtime usage history. |
| Field validation | Blocks secret value display, invalid external ref, invalid schema, unsafe tool risk without policy, and credential validation failure. |
| Empty state | Empty gateway/tool/secret states guide safe registration and validation. |
| Loading state | Test call, schema validation, and secret-ref validation show scoped busy states. |
| Error state | Provider/tool/secret errors avoid exposing sensitive values and identify retryability. |
| Keyboard flow | Schema preview, risk controls, and validation result are keyboard accessible. |
| Responsive behavior | Risk, health, and used-by data remain visible before save on narrow screens. |

### Quality Loop

| Check | Acceptance criteria |
|---|---|
| Task completion | User can capture run evidence to dataset, configure experiment/evaluator, inspect score distribution, and use quality gate evidence for promotion. |
| Visible system status | Shows dataset provenance, evaluator config, experiment status, score summary, gate result, and linked deployment/version. |
| Field validation | Blocks missing dataset, invalid evaluator config, incompatible output schema, and promotion without required gate. |
| Empty state | Empty dataset/experiment states start from production run capture or example data. |
| Loading state | Experiment execution and score calculation have progress without blocking unrelated inspection. |
| Error state | Evaluator errors distinguish config, runtime, and data failures. |
| Keyboard flow | Dataset item review and score distribution summaries are keyboard readable. |
| Responsive behavior | Charts provide table summaries and stack with evidence links. |

### Incident, Notification, Backup, And Restore

| Check | Acceptance criteria |
|---|---|
| Task completion | User can test notification delivery, acknowledge incident, resolve with note, run backup validation, dry-run restore, and block destructive restore without proof. |
| Visible system status | Shows incident timeline, alert source, delivery attempts, runbook link, backup manifest, restore validation, affected scope, and audit requirement. |
| Field validation | Blocks destructive restore without dry-run, scope proof, confirmation, permission, and audit reason. |
| Empty state | Empty incidents/backups states explain monitoring and backup setup prerequisites. |
| Loading state | Delivery test, backup validation, and dry-run restore show long-running job progress. |
| Error state | Partial failure lists completed and incomplete checks. |
| Keyboard flow | Incident timeline, notes, confirmations, and restore proof are keyboard accessible. |
| Responsive behavior | Timeline and validation report remain readable on mobile. |

### Identity, Role, Permission, Session, And Key Rotation

| Check | Acceptance criteria |
|---|---|
| Task completion | User can inspect effective permissions, prevent self-lockout, rotate keys, revoke sessions, and understand dependent resources. |
| Visible system status | Shows actor, roles, effective permissions, sessions, service accounts, key age, last used, used-by graph, and self-lockout warning. |
| Field validation | Blocks self-lockout, invalid permission set, missing rotation confirmation, and revocation without scope clarity. |
| Empty state | Empty service-account/key states explain creation requirements and rotation policy. |
| Loading state | Permission calculation and used-by graph load with stable placeholders. |
| Error state | Permission errors show required permission and do not expose hidden resources. |
| Keyboard flow | Role matrix, session table, and rotation dialog support keyboard operation. |
| Responsive behavior | Matrices become readable stacked or scroll-managed tables with clear row/column labels. |

### Platform Settings And Danger Zone

| Check | Acceptance criteria |
|---|---|
| Task completion | User can inspect environment/provider/runtime settings, run preflight, make safe changes, and perform dangerous changes only with confirmation and audit reason. |
| Visible system status | Shows environment, provider health, runtime mode, unsafe defaults, last change, pending restart/rollout, and affected resources. |
| Field validation | Blocks production-unsafe defaults, missing secret provider, permissive CORS, dev API key mode, and missing audit reason. |
| Empty state | Missing provider/settings state explains setup and production requirements. |
| Loading state | Preflight shows progress and disables final submit until complete. |
| Error state | Failed preflight blocks dangerous action and lists exact failed checks. |
| Keyboard flow | Danger confirmations require deliberate keyboard-accessible confirmation. |
| Responsive behavior | Danger context appears before destructive controls on all viewport widths. |

## Browser Evidence Requirements

For each workflow promoted beyond generic CRUD, add browser evidence for:

| Evidence type | Requirement |
|---|---|
| Success path | The primary user can finish the job and see success feedback. |
| Loading path | At least one async region shows stable loading behavior. |
| Empty path | Empty state gives the next correct action. |
| API error path | Normalized error is visible and preserves context. |
| Permission denial | Disabled action explains required permission and reason. |
| Destructive confirmation | High-risk action shows impact, audit reason, confirm/cancel, and focus handling. |
| Accessibility | Critical axe violations are zero for representative pages and dialogs. |
| Responsive | Workflow is usable at 375px and desktop width without overlap. |

## Acceptance Gate

A Console workflow can be marked complete only when it satisfies the user task model and the experience checks above. If a page only lists records, edits raw JSON, or exposes generic enable/disable controls without domain validation, policy/audit behavior, impact preview, success feedback, and failure recovery, it remains partial.
