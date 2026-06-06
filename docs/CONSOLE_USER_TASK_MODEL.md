# Console User Task Model

This document defines the Console from user jobs, decisions, risks, and recovery paths. Product workflow work must start here before it starts from tables, routes, or generic resource CRUD.

DimooRun Console is the primary interaction surface for the Runtime / Ops / Control Plane. It is not a low-code agent builder, prompt design tool, workflow canvas, or business application builder. The Console should make runtime execution, deployment, governance, observability, quality, and operations trustworthy for users who bring their own agent code.

## Product Rule

Every Console workflow must name:

| Required link | Meaning |
|---|---|
| User role | Who is trying to complete the job. |
| User job | The operational outcome the user needs. |
| Decision | What the user must decide before acting. |
| Risk | What can go wrong if the action is wrong or incomplete. |
| Pre-action context | What must be visible before the user can decide. |
| Success feedback | How the user knows the action finished. |
| Failure recovery | What the user can retry, undo, roll back, or escalate. |

Generic CRUD coverage is not enough. A workflow is not complete unless it gives the user enough context to make a safe decision and recover from failure.

## Primary Roles

| Role | Primary responsibility | Typical scope | Production concern |
|---|---|---|---|
| Platform operator | Keep runtime infrastructure, workers, queues, deployments, providers, and environments healthy. | Tenant, project, environment, deployment, worker pool. | Unsafe changes, queue pressure, duplicate execution, failed dependencies, capacity exhaustion. |
| Agent developer | Register packages, validate versions, deploy changes, submit test tasks, inspect runs, and replay failures. | Agent, version, deployment, task, run, replay, dataset. | Broken package, invalid runtime config, failed rollout, missing secrets, regression after change. |
| Governance/security reviewer | Review policy impact, approvals, tool/model/secret access, identity changes, and dangerous actions. | Policy, approval, role, service account, secret ref, gateway route, audit record. | Bypass, over-permission, unreviewed high-risk action, missing audit reason, self-lockout. |
| Incident responder | Triage failed runs, unhealthy deployments, stuck tasks, alerts, incidents, dead letters, and restore drills. | Incident, run, task, attempt, event, worker, backup, restore job. | Slow recovery, incomplete evidence, destructive restore, unresolved customer impact. |
| Auditor | Verify what happened, who acted, why it was allowed, what changed, and whether evidence is complete. | Audit log, policy decision, approval, deployment change, run evidence, identity event. | Missing provenance, exposed sensitive payload, inconsistent records, unsupported compliance claim. |

## Job Matrix

| Job | Primary roles | Decision to support | Main risks |
|---|---|---|---|
| First-run setup | Platform operator, agent developer | Is the environment ready to run a real agent safely? | Missing dependency, unsafe dev default, wrong scope, no service account, no runnable example. |
| Daily monitoring | Platform operator, incident responder | Is the runtime healthy enough to accept work? | Queue backlog, stale worker heartbeat, rising failure rate, budget or provider issue. |
| Deploy or change | Agent developer, platform operator, governance reviewer | Should this version/config change be promoted now? | Invalid package, missing secret, active run disruption, no rollback path, policy deny. |
| Failed-run triage | Agent developer, incident responder | Is this an input, code, dependency, policy, capacity, or platform failure? | Hidden root cause, repeated retry storm, lost artifact, incorrect replay target. |
| Approval decision | Governance/security reviewer | Should the requested action proceed, be rejected, or require more context? | Approving dangerous action without impact, missing audit reason, requester spoofing. |
| Audit review | Auditor, governance/security reviewer | Is there enough evidence to explain a change or runtime event? | Redacted evidence too weak, missing policy decision, inconsistent actor/scope. |
| Rollback | Agent developer, platform operator, incident responder | Is rollback safer than forward fix, and what will it affect? | Rollback to invalid version, active task conflict, unresolved data or schema dependency. |
| Key rotation | Governance/security reviewer, platform operator | Can this service account or credential rotate without breaking dependent resources? | Orphaned deployment, leaked credential, self-lockout, no last-used visibility. |
| Restore dry-run | Incident responder, platform operator, auditor | Can restore complete for the selected scope without destructive surprise? | Wrong backup, partial restore, object-store mismatch, missing validation proof. |

## Pre-Action Context

Every workflow must show the following context before the user can perform a high-risk or state-changing action.

| Context | Required display |
|---|---|
| Current scope | Tenant, project, environment, and resource identifier. |
| Resource health | Current status, last heartbeat or update, relevant dependency health, and known blocking conditions. |
| Last change | Last actor, timestamp, change reason, previous state, and link to audit evidence. |
| Permissions | Whether the current actor can act, required permission, and disabled reason when unavailable. |
| Risk | Risk category, policy warnings, affected runtime surface, and blast radius. |
| Affected resources | Deployments, surfaces, workers, runs, tasks, keys, policies, datasets, or backups that may change. |
| Audit requirement | Whether an audit reason, approval, comment, or ticket/reference is required. |
| Rollback path | Previous known-good state, rollback target, validation requirement, and blocked rollback reason. |

## Job Details

### First-Run Setup

Users need a guided path from empty environment to first successful runtime inspection.

| Field | Requirement |
|---|---|
| User roles | Platform operator, agent developer. |
| Success outcome | A real example agent is registered, validated, deployed, invoked, and inspected in Console. |
| Decision | Whether dependencies, scope, credentials, and runtime mode are ready. |
| Pre-action context | Dependency status for server, worker, database, Redis, object storage, Console API, selected scope, and service-account/API-key status. |
| Success feedback | Deployment is active, task completes, run detail has attempts/events/artifacts, and the quickstart points to the same evidence. |
| Failure recovery | Show the failing step, exact command or configuration to fix, retry affordance, and link to logs or health check. |

### Daily Monitoring

Users need a runtime command center, not a table of unrelated resources.

| Field | Requirement |
|---|---|
| User roles | Platform operator, incident responder. |
| Success outcome | User can determine whether work is healthy, degraded, or blocked within one page. |
| Decision | Whether to drain workers, scale capacity, pause deployments, investigate incidents, or leave the system alone. |
| Pre-action context | Queue depth, active/running/failed tasks, worker heartbeat age, deployment health, provider health, incidents, pending approvals, and cost/budget warnings. |
| Success feedback | Recommended action changes state, affected counters update, and audit evidence is linked. |
| Failure recovery | Failed control action shows retryability, current state after failure, and escalation path. |

### Deploy Or Change

Users need promotion evidence and rollback confidence before changing runtime behavior.

| Field | Requirement |
|---|---|
| User roles | Agent developer, platform operator, governance/security reviewer. |
| Success outcome | A candidate version or config is promoted, paused, resumed, drained, stopped, restarted, or rolled back with audit evidence. |
| Decision | Whether the candidate is valid, governed, compatible, and safer than the current state. |
| Pre-action context | Candidate validation, version diff, active runs, queued tasks, policy decision, required approval, traffic/exposure impact, and rollback target. |
| Success feedback | Desired status, runtime status, rollout reason, audit ID, and next verification link are visible. |
| Failure recovery | Partial change is explicit, retry is scoped, rollback target remains visible, and policy denied actions explain next steps. |

### Failed-Run Triage

Users need a single evidence view for failure classification.

| Field | Requirement |
|---|---|
| User roles | Agent developer, incident responder, auditor. |
| Success outcome | User can classify the failure and choose retry, replay, dataset capture, incident escalation, or code/config fix. |
| Decision | Whether the failure is deterministic, transient, governed, dependency-related, capacity-related, or caused by a recent change. |
| Pre-action context | Input/output visibility rules, error, attempts, events, artifacts, trace ID, policy decisions, cost, deployment/version, and last change. |
| Success feedback | Chosen action records the new task/replay/dataset/incident and links it back to the source run. |
| Failure recovery | Failed replay/retry preserves source evidence, explains non-retryable state, and suggests the next diagnostic artifact. |

### Approval Decision

Users need enough impact context to approve or reject dangerous actions.

| Field | Requirement |
|---|---|
| User roles | Governance/security reviewer, auditor. |
| Success outcome | Requested action is approved, rejected, or commented with decision provenance and runtime resume result. |
| Decision | Whether policy, permissions, requester identity, risk, and affected resources justify the action. |
| Pre-action context | Requested action, requester, policy match, risk reason, resource diff, affected scope, prior approvals, and required audit reason. |
| Success feedback | Decision, actor, timestamp, comment, policy decision ID, and resumed runtime result are visible. |
| Failure recovery | If resume fails, decision remains auditable, retry/resume status is explicit, and escalation route is shown. |

### Audit Review

Users need evidence that can explain system behavior without exposing sensitive payloads.

| Field | Requirement |
|---|---|
| User roles | Auditor, governance/security reviewer, incident responder. |
| Success outcome | User can reconstruct who did what, why it was allowed, what changed, and where runtime evidence lives. |
| Decision | Whether evidence is complete enough for compliance, incident review, or release approval. |
| Pre-action context | Actor, scope, request ID, policy decision, permission summary, before/after diff, redaction state, and linked runtime events. |
| Success feedback | Exportable or linkable evidence bundle is available where the product supports it. |
| Failure recovery | Missing or redacted fields explain why they are unavailable and where stronger evidence might exist. |

### Rollback

Users need an impact preview before reversing production behavior.

| Field | Requirement |
|---|---|
| User roles | Agent developer, platform operator, incident responder, governance/security reviewer. |
| Success outcome | A deployment, asset, policy, setting, or route returns to a selected previous state with audit evidence. |
| Decision | Whether rollback is safer than remediation and whether it affects active work. |
| Pre-action context | Previous known-good target, active runs, queued tasks, compatibility, policy decision, dependency changes, and expected status after rollback. |
| Success feedback | New active state, previous state, rollback reason, audit ID, and verification action are visible. |
| Failure recovery | Failed rollback shows unchanged state, partial state if any, retryability, and escalation steps. |

### Key Rotation

Users need dependency visibility before rotating credentials.

| Field | Requirement |
|---|---|
| User roles | Governance/security reviewer, platform operator, auditor. |
| Success outcome | API key, service-account key, or secret reference rotates without breaking dependent runtime resources. |
| Decision | Whether dependencies are ready and whether old credentials can be revoked. |
| Pre-action context | Last-used time, used-by graph, dependent deployments/routes/providers, permissions, expiration, and audit requirement. |
| Success feedback | New key metadata, old key status, dependent resource checks, and audit evidence are visible. |
| Failure recovery | If rotation fails, old credential status is explicit and rollback/retry guidance avoids exposure of secret values. |

### Restore Dry-Run

Users need proof before destructive recovery.

| Field | Requirement |
|---|---|
| User roles | Incident responder, platform operator, auditor. |
| Success outcome | Restore plan is validated against database and object-store artifacts without destructive changes. |
| Decision | Whether the selected backup can restore the intended scope and whether a real restore should be allowed. |
| Pre-action context | Backup timestamp, scope, checksum/manifest, affected resources, object-store match, migration compatibility, and destructive confirmation requirement. |
| Success feedback | Dry-run report lists validated objects, missing objects, estimated impact, and next safe action. |
| Failure recovery | Failed dry-run blocks destructive restore, lists missing evidence, and provides retry or escalation steps. |

## High-Risk Action Feedback And Recovery

Every high-risk action must produce an explicit result model.

| Action class | What changed | What did not change | Where to verify | Retryable | Escalation trigger |
|---|---|---|---|---|---|
| Promote deployment | Desired version/config and rollout audit record. | Source version, historical runs, unrelated deployments. | Deployment detail, run creation, audit log. | Yes, with same idempotency key semantics where supported. | Candidate active state diverges from desired state. |
| Pause/resume/drain worker or deployment | Runtime acceptance of new work and worker/deployment control state. | Existing completed run evidence. | Runtime overview, task queue, worker heartbeat, audit log. | Yes if current state allows transition. | Active attempt cannot finish or cancel within timeout. |
| Approve/reject action | Human task decision and policy decision trail. | Original request evidence. | Approval detail, audit log, resumed run/task. | Resume may be retryable; decision reversal requires a separate audited action. | Runtime resume fails after approval. |
| Rotate key or secret ref | Credential metadata and active binding. | Secret value visibility remains blocked. | Identity/service-account detail, used-by checks, audit log. | Yes if old credential still valid or provider supports retry. | Dependent deployment/provider fails validation. |
| Rollback | Active resource state returns to selected target. | Evidence for failed version/change remains retained. | Resource detail, diff, audit log, affected runtime checks. | Yes if rollback target remains valid. | Rollback target fails validation or active work is blocked. |
| Restore | Data/object scope changes only after dry-run and confirmation. | Unselected scope and immutable audit evidence. | Restore job detail, backup manifest, validation report, audit log. | Dry-run yes; destructive restore depends on job state. | Missing backup objects, migration mismatch, or partial restore. |

## Workflow Design Guardrails

- Prefer backend-derived action availability and disabled reasons over hidden frontend-only logic.
- Show impact preview before dangerous writes.
- Require audit reason for high-risk changes.
- Keep secret values, hidden run payloads, and redacted audit payloads undisclosed.
- Treat generic admin pages as partial coverage unless they implement domain validation, policy/audit behavior, success feedback, failure recovery, and browser evidence.
- Do not introduce low-code builder, drag-and-drop workflow canvas, prompt design platform, generic ITSM, ticket routing, or business application builder scope.
