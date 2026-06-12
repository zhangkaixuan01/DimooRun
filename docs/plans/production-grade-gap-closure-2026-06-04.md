# DimooRun Production Grade Gap Closure Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current DimooRun implementation from a production-like foundation into a production-grade, operator-trustworthy Agent Runtime / Ops / Control Plane.

**Architecture:** Keep the current three-plane architecture from `docs/reference/design-spec.md`: Control Plane, Runtime Plane, Agent Plane, plus the Vue Console. The work should harden existing boundaries instead of replacing them: typed Native API, SQLAlchemy durable runtime, Redis scheduler, adapter-first execution, admin APIs, and Console live workflows.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, Redis, PostgreSQL, MinIO/S3-compatible object storage, Vue 3, Vite, TypeScript, Pinia, ECharts, Docker Compose, Helm/Kubernetes, pytest, ruff, mypy, vue-tsc, Playwright, axe accessibility checks.

---

## 1. Current Maturity Assessment

### Overall Verdict

DimooRun is no longer a paper design or a simple MVP. The repository has a real backend, durable SQLAlchemy runtime path, native API surface, worker execution loop, adapter contracts, auth/session flows, Docker/Helm assets, and a live Console wired to backend APIs.

It is still not a "perfect production-grade project." The remaining gap is not one missing feature. It is a set of production confidence gaps:

- core product workflows are present as routes and CRUD surfaces, but many are not yet complete domain workflows;
- several Console pages are broad management shells rather than polished, task-oriented operator tools;
- frontend logic is page-local and fragile in large pages, with hand-written JSON editing and repeated error/loading/mutation state;
- backend services expose many model records before the corresponding product semantics are complete;
- real end-to-end environment verification is incomplete;
- frontend browser verification exists, but only as smoke coverage rather than workflow confidence;
- several enterprise services are provider boundaries or in-memory implementations, not fully integrated runtime services;
- production defaults still contain dev credentials and permissive behavior;
- operational guarantees such as migrations, rollout, backup, restore, tracing, metrics, and incident response need executable proof;
- SDK, release, CI/CD, security scanning, and compatibility governance are not complete enough for external production users.

### Correction After Deeper Product Audit

The gap is broader than production deployment and operations testing. A stricter reading of `docs/reference/design-spec.md` against `apps/console/src/**` and `apps/server/dimoo_run/**` shows three additional categories of missing work:

1. **Feature coverage gaps:** Many surfaces exist, but they are not full feature workflows. For example, policies, model gateways, secrets, tools, datasets, experiments, replay jobs, notifications, backups, restore jobs, semantic stores, exporters, sandbox policies, and container pool policies are mostly exposed through generic collection CRUD instead of domain-specific flows.
2. **Frontend experience gaps:** The Console can navigate and call APIs, but it does not yet feel like a mature operations product. Several pages are very large (`AgentsPage.vue` about 41KB, `DeploymentsPage.vue` about 28KB, `AdminCollectionPage.vue` about 27KB, `PublishedSurfacesPage.vue` about 25KB, identity pages above 14-25KB). These pages mix table rendering, form state, JSON editing, API mutation, error display, selection, confirmation, and business rules in one file.
3. **Frontend logic gaps:** Runtime state is not modeled as reusable client-side workflows. There is repeated manual parsing with `JSON.parse`, local list mutation after writes, scattered loading/error flags, no request cancellation, no stale response guard, no route-level data loader abstraction, no optimistic update strategy, no server pagination contract, and no shared mutation state machine.

So the correct status is:

```text
Production deployment hardening is one gap.
Product functionality completeness is a separate and larger gap.
Frontend UX and frontend state logic are also separate and material gaps.
```

### Distance From Production

| Area | Current Level | Distance To Excellent Production Grade |
|---|---:|---|
| Core domain model and migrations | Medium-high | Medium |
| Native runtime API | Medium-high | Medium |
| Durable worker execution | Medium | Medium-high |
| Scheduler, retries, leases, quotas | Medium | Medium |
| Adapter contracts | Medium | Medium-high |
| Governance and admin surfaces | Medium | Medium-high |
| Product workflow completeness | Low-medium | High |
| Console information architecture | Medium | Medium-high |
| Console interaction quality | Low-medium | High |
| Frontend state management | Low-medium | High |
| Frontend testing | Low-medium | Medium-high |
| Observability and metrics | Low-medium | High |
| Security defaults and hardening | Medium | High |
| Deployment assets | Medium | Medium-high |
| CI/CD and release engineering | Low-medium | High |
| SDKs and external developer experience | Low-medium | High |
| Disaster recovery | Low-medium | High |

### Main Evidence Reviewed

- `docs/reference/design-spec.md`
- `docs/pre_execution_plans/00-master-execution-plan.md`
- `docs/history/implementation-update-2026-06-01.md`
- `docs/superpowers/plans/*.md`
- `apps/server/dimoo_run/**`
- `apps/worker/dimoo_run_worker/main.py`
- `apps/console/src/**`
- `apps/console/playwright.config.ts`
- `apps/console/tests/e2e/console-smoke.spec.ts`
- `tests/**`
- `deploy/docker/**`
- `deploy/helm/dimoorun/**`
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `pyproject.toml`
- `apps/console/package.json`

---

## 2. Non-Negotiable Production Definition

DimooRun should not be called production-grade until all of these are true:

- A clean machine can run server, worker, console, Postgres, Redis, and MinIO from Docker Compose, execute a real LangGraph example, inspect the run in Console, and shut down cleanly.
- A Kubernetes smoke environment can render and deploy Helm manifests, pass health checks, execute one real task, and scale worker replicas without duplicate execution.
- Every write API has stable request IDs, idempotency where required, authorization, audit trail, validation, and predictable error codes.
- Worker execution survives process crash, lease expiry, retry, dead-letter, cancellation, and adapter errors without losing task state or duplicating runs.
- Runtime events, attempts, artifacts, audit logs, traces, and metrics are queryable, redacted where required, and exported to standard observability targets.
- Console workflows are tested in a real browser for create, edit, archive, deploy, invoke, replay, approve/reject, filter, empty state, error state, keyboard flow, and responsive layout.
- Security defaults fail closed in production mode. No default credentials, permissive CORS, memory stores, plain secret handling, or dev-only API keys are accepted in production.
- Migrations are reversible or explicitly irreversible with guardrails, and upgrade compatibility is tested against a realistic previous database snapshot.
- SDKs and OpenAPI are generated, versioned, contract-tested, and documented.
- Release artifacts are reproducible, scanned, tagged, and deployed by CI/CD.

---

## 3. Competitive Product Direction

The product should become competitive by being an excellent Agent Runtime / Ops / Control Plane, not by expanding into unrelated product categories.

Strengthen these areas aggressively:

- **Governed runtime exposure:** Agent Gateway, Published Surfaces, Ingress Routes, request logs, route testing, traffic control, and revocation.
- **Migration confidence:** LangGraph and Agent Protocol compatibility explorer, migration report, golden compatibility tests, and native resource mapping.
- **Runtime operations:** worker health, agent instances, queue pressure, capacity recommendations, drain/quarantine, and failure drilldown.
- **Governance by default:** policy simulation, permission summaries, role matrix, machine identity, service-account key rotation, approval context, and audit comparison.
- **Commercial operations:** model/runtime cost attribution, budgets, anomalies, and usage drilldown without implementing wallet, recharge, or full billing.
- **Quality loop:** dataset capture, experiment execution, quality gates, feedback, online sampling, and promotion evidence.
- **Versioned assets:** catalog, tool/MCP metadata, Prompt/Config/Template assets, dependency graph, validation, approval, publish, deprecate, and rollback.
- **Operational trust:** platform settings, provider status, dangerous-change preflight, backup/restore dry-run, incidents, alerts, and runbooks.
- **Product soft power:** product-grade README, information architecture, guided quickstart, realistic examples, screenshots, demo scripts, architecture diagrams, trust/security docs, contribution path, changelog, roadmap, release notes, and comparison material.

Do not build these as primary products:

- low-code Agent Builder;
- drag-and-drop workflow canvas;
- prompt design platform;
- business application builder;
- full billing, wallet, recharge, or provider balance system;
- business memory semantics layer;
- custom model provider gateway when a professional gateway such as New API should be integrated.

The competitive promise is:

```text
Users bring their agent code and business tools.
DimooRun makes runtime execution, exposure, migration, governance, observability, quality, and operations trustworthy.
```

### Product Function Coverage Review

Current product coverage is broad, but "perfect product" requires the product to be judged by end-to-end jobs rather than menu count. The plan now covers the right product domains, but several domains need stronger cross-resource workflows, better default guidance, and more competitive operator experience.

Coverage verdict:

| Product area | Coverage direction | Perfect-level gap |
|---|---|---|
| Agent lifecycle | Agent package, version readiness, deployment promotion, rollback | Needs a single guided path from package import to first successful production run, with blockers and next actions visible at every step |
| Runtime execution | Runs, tasks, attempts, events, replay, scheduled, batch | Needs one runtime workbench that unifies live run, stream, timeline, artifacts, traces, replay, and compare |
| Debug and replay | Run triage, replay comparison, dataset capture | Needs reproducible replay bundles, baseline/candidate diff, regression classification, and shareable debug evidence |
| Governance | Policy, human approval, model/tool/secret governance | Needs one action-risk model across all dangerous actions, with simulation, impact preview, and decision provenance |
| External exposure | Published Surface, Ingress, Agent Gateway | Needs traffic, auth, policy, request logs, route test, abuse signals, and rollback in one publishing workflow |
| Compatibility | LangGraph and Agent Protocol migration/explorer | Needs migration score, unsupported capability inventory, native-resource mapping, golden tests, and SDK compatibility matrix |
| Operations | Workers, agent instances, incidents, alerts, backup/restore | Needs operational command center for queue pressure, worker health, active incidents, pending approvals, backup status, and recommended actions |
| Identity | Users, roles, permissions, sessions, machine identity | Needs effective permission explorer, self-lockout prevention, service account dependency graph, and key/session rotation workflows |
| Quality | Datasets, experiments, evaluation, quality gates, feedback | Needs closed loop from production run to dataset to experiment to promotion gate to rollout decision |
| Cost | Usage attribution, budgets, anomalies | Needs cost per agent/deployment/run/provider tied to quality, failure rate, and deployment change history |
| Catalog and assets | Catalog, tools, MCP, Prompt/Config/Template assets | Needs governed asset lifecycle with version diff, dependency graph, approval, used-by impact, and rollback |
| Platform settings | Provider status, runtime settings, danger zone | Needs environment-scoped settings, provider health, preflight, read-only production mode, and audited dangerous changes |
| Developer experience | SDK, CLI, quickstart, examples | Needs first-run success path that works through CLI, API, Console, SDK, and docs with the same mental model |
| Product soft power | README, docs, examples, trust assets | Needs product-grade narrative, comparison, diagrams, screenshots, demo script, security posture, and contribution path |

Optimization backlog:

- **Guided activation path:** Add a first-run product path from "connect runtime dependencies" to "register package" to "validate version" to "deploy" to "submit task" to "inspect run" to "promote safely." This should become the default Console and README happy path.
- **Runtime workbench:** Consolidate run detail, task state, timeline, stream, attempts, artifacts, trace, logs, cost, policy decisions, and replay into a single operator workbench instead of scattering diagnostics across pages.
- **Action center:** Add a global pending-actions surface for approvals, failed validations, stuck tasks, unhealthy workers, expiring keys, failed backups, budget threshold breaches, and incident follow-ups.
- **Resource graph:** Add cross-resource navigation and dependency views: agent -> version -> deployment -> surface -> run -> event -> artifact -> audit, plus service account -> keys -> deployments -> published surfaces.
- **Impact preview everywhere:** Every high-risk action should show affected resources, policy decision, required permission, expected audit record, rollback path, and disabled-action reason.
- **Compare and diff as a product primitive:** Use diff workflows for deployment promotion, version changes, replay candidate output, policy changes, role permission changes, asset versions, and settings changes.
- **Saved operational views:** Add saved filters for runs, incidents, costs, audit logs, worker health, and request logs so operators can return to the same investigative lens.
- **Evidence bundles:** Let users export or link an evidence bundle for incidents, failed runs, replay comparisons, policy decisions, compatibility gaps, and deployment promotions.
- **Feedback capture:** Add human rating, correction, and issue labeling from Run Detail and Replay so quality datasets grow from real production evidence.
- **Integration health center:** Centralize provider health for model gateway, secret provider, object store, Redis, Postgres, notification transport, webhook transport, observability exporter, and compatibility endpoints.
- **Environment promotion lanes:** Make dev/staging/production scope visible in deployment, settings, gateway, policy, and quality workflows; promotion should require environment-aware checks.
- **Product telemetry:** Track product usage signals such as failed activation step, most common error recovery path, abandoned high-risk action, slow page load, and browser workflow failures without collecting secret or prompt payloads. Telemetry must be tenant/project-scoped, configurable, sampled where appropriate, redacted by default, retention-bound, documented in trust/security materials, and possible to disable.
- **Collaboration notes:** Add operator notes and audit-linked comments for incidents, replay investigations, approvals, and deployment changes, without turning the product into a ticketing system. Notes must bind to runtime evidence and must not add generic project management, task assignment, kanban, SLA ticket routing, or enterprise ITSM replacement scope.
- **Capability explainers:** For each adapter and compatibility path, show supported capabilities, unsupported capabilities, test proof, and recommended workaround.
- **Polished empty states:** Empty states should guide the next correct action for each role and scope, not just report that the collection is empty.

These optimizations should be implemented only when they reinforce runtime control, operational trust, migration confidence, governance, quality, or developer activation. If an optimization cannot be mapped to one of those product values, remove it from this plan or move it to a later-ideas section outside the production-grade roadmap.

---

## 4. Highest-Risk Gaps

### P0. Product Workflows Are Not Complete Enough

The current project has many product surfaces, but many of them are "resource coverage" rather than "workflow coverage." A route, a table, and generic create/edit/delete do not equal a production-ready feature.

Concrete examples:

- **Policies:** `PoliciesPage.vue` delegates to `AdminCollectionPage`. Missing policy authoring model, condition builder, simulation, dry-run, conflict detection, activation workflow, impact preview, versioning, rollback, and audit comparison.
- **Model gateways:** Generic CRUD exists. Missing provider health, model catalog, routing rules, budget preview, fallback simulation, per-tenant quota, token/cost charts, provider error drilldown, and safe credential binding.
- **Tools:** Generic CRUD exists. Missing tool schema preview, risk classification workflow, approval policy binding, dry-run execution, permission impact, and runtime usage history.
- **Secrets:** Generic CRUD exists. Missing external provider sync, rotation workflow, secret reference validation, last-used visibility, access audit, and blocked value display rules.
- **Human tasks:** Basic list and approve/reject exist. Missing assignment, SLA, escalation, decision context, diff view, bulk queue, requester identity, and resume outcome tracking.
- **Replay/debug:** Basic replay exists. Missing structured diff, replay job queue, batch replay, dataset capture, candidate comparison, output comparison, regression signal, and replay provenance.
- **Datasets/experiments/evaluations:** Mostly generic admin resources. Missing dataset item curation, run-to-dataset capture, experiment execution, quality gate results, evaluator config UX, score distribution, and promotion gate.
- **Published surfaces/ingress:** More specialized than generic CRUD, but still missing request logs, auth mode validation, route test, rollout state, traffic split, revocation, and deployment binding health.
- **Backup/restore/notifications/incidents:** Generic admin surfaces exist. Missing runbooks embedded in product, restore dry-run UX, delivery attempts, incident timeline, acknowledge/resolve flow, and notification test send.
- **Compatibility:** `CompatibilityPage.vue` is informational only. Missing assistant/thread/run explorer, request builder, stream tester, golden compatibility result, and migration helper.
- **Settings:** `SettingsPage.vue` only covers theme and language. Missing runtime settings, organization defaults, API endpoint status, token/session controls, environment scope defaults, and dangerous production settings visibility.

Production impact:

- Operators see menu coverage but cannot safely complete complex workflows.
- Backend records can be created in invalid or semantically weak states because the Console does not guide or validate domain intent.
- The project may appear feature-complete in screenshots while still failing real operator tasks.

### P0. Frontend UX Is Too CRUD-Oriented For An Ops Console

The Console should behave like a runtime control plane, not a generic database admin tool. Current UX patterns expose too much raw JSON and internal model shape to the user.

Frontend design must start from the user's job, not from the database resource. The primary users are operators, platform engineers, developers shipping agents, security/governance reviewers, and incident responders. Each Console workflow should answer: what is the user trying to decide or complete, what risk are they carrying, what context do they need before acting, what feedback proves the action succeeded, and how do they recover when the backend rejects or delays the action.

Missing:

- Task-first flows for "register package", "validate version", "promote deployment", "triage failed run", "approve risky tool", "replay with candidate", "create quality gate", "rotate key", and "restore dry-run".
- User-centered workflow maps for each role: first-run setup, normal daily monitoring, deployment change, incident triage, approval review, audit review, and rollback.
- Decision support before high-risk actions: impact preview, affected resources, last known health, required permissions, audit reason, and expected rollback path.
- Post-action confirmation that matches user intent: deployment promoted, task submitted, policy simulated, approval resumed, secret rotation scheduled, restore dry-run passed.
- Progressive disclosure for complex resources: summary, health, configuration, risk, audit, events, and advanced JSON should be separated.
- Inline validation before submit, especially for JSON payloads, manifests, package URIs, policy conditions, route paths, secret refs, model gateway refs, and deployment config.
- Rich empty states that offer the correct next action per resource, not generic "backend returned empty collection" text.
- Domain-specific detail pages for high-risk resources instead of table plus drawer JSON.
- Cross-resource navigation: agent -> versions -> deployments -> runs -> events -> artifacts -> audit.
- Operator-friendly copy for error recovery: what failed, why it matters, what can be retried, and what requires admin action.
- Better information density control: current large pages mix too much in one viewport without enough filtering, grouping, or saved views.

Production impact:

- Users can technically click through flows but are likely to make configuration mistakes.
- Runtime incidents will be hard to diagnose because context is scattered across pages.
- The UI does not yet earn operator trust for high-risk production actions.

### P0. Frontend State Logic Is Fragile

Several pages implement their own state machines directly in Vue SFC files. This works for an MVP but becomes brittle when workflows become async, paginated, permissioned, and failure-prone.

Evidence:

- `AgentsPage.vue`, `DeploymentsPage.vue`, `PublishedSurfacesPage.vue`, `AdminCollectionPage.vue`, `MachineIdentityPage.vue`, and `OperatorsPage.vue` are large enough that state, UI, and business rules are tightly coupled.
- Repeated manual `JSON.parse` and `JSON.stringify` are used as primary editing mechanisms.
- Data loading uses local `onMounted` calls without shared cancellation, stale response guards, retry policy, or route-level loader model.
- Mutations often update local arrays manually, which can drift from server truth when backend side effects are broader than the changed item.
- `CursorPage<T>` exists on the frontend, but backend list APIs mostly return arrays, so pagination is a UI fiction rather than an API contract.
- Permission checks are mostly local `canWrite` style guards after data reaches the page. There is no central capability model that drives available actions per resource and actor.
- Error state is page-level and not field-level enough for complex forms.

Missing:

- A resource/query client layer with request keys, abort controllers, stale response protection, retry rules, and cache invalidation.
- Shared mutation primitives for create/update/delete/control actions.
- Typed form models per domain workflow.
- A JSON editor component with schema validation, parse error location, formatting, and recovery.
- Central permission/capability derivation for actions.
- Route-aware data loading and reload behavior when tenant/project/environment scope changes.
- Optimistic updates only where safe, otherwise canonical reload after mutations.

Production impact:

- Race conditions and stale views become likely as soon as the Console is used heavily.
- Field-level errors and validation will be inconsistent.
- Adding features will become slower because each page repeats its own async and mutation logic.

### P0. Backend Product Semantics Are Behind The Data Model

The backend has many domain models and generic admin collection support, but several product features are still closer to "record management" than "domain service."

Concrete gaps:

- `api/admin/router.py` centralizes many resource types in one generic router. This is useful for coverage, but it is not enough for production semantics.
- Several services are still in-memory or provider-boundary oriented: replay service, evaluation service, secret provider, model gateway provider, policy audit sinks, notification transport, webhook transport, and compatibility runtime.
- LangGraph compatibility runtime uses in-memory run/task/audit primitives, so it is not aligned with the durable native runtime path.
- Model records such as BackupPlan, RestoreJob, Experiment, EvaluationResult, NotificationChannel, AlertRule, SemanticStoreProvider, and ObservabilityExporter exist, but end-to-end product behavior is limited.
- Policy, model gateway, tool gateway, secret, approval, sandbox, artifact, and runtime execution are not yet consistently enforced as one runtime decision pipeline.

Missing:

- Domain services for high-value resources, not only generic CRUD.
- Typed APIs for workflow actions: validate, simulate, activate, test, rotate, promote, rollback, dry-run, acknowledge, resolve, compare, export.
- State machines for policies, deployments, replay jobs, experiments, restore jobs, incidents, notification deliveries, and package validation.
- Durable compatibility runtime backed by the same SQLAlchemy/Redis runtime primitives.
- Cross-resource integrity checks before state transitions.
- Backend-side derived views that the Console can use directly, instead of reconstructing product meaning from raw rows.

Production impact:

- The backend can store data that the runtime does not actually honor.
- The Console cannot present reliable health or next actions because the backend does not yet expose domain-level facts.
- Compatibility and native paths may diverge in behavior.

### P0. Real Environment Smoke Is Not Proven

The docs mention Docker/Helm smoke gaps. The repository has Docker Compose and Helm assets, but the current verification evidence is mostly unit/API/static tests and focused local commands.

Missing:

- Docker Compose healthy smoke in CI or a reproducible local script.
- Real Postgres + Redis + MinIO execution path test.
- Worker long-running mode under Compose with at least one real agent package.
- Helm render and Kubernetes deployment smoke in an actual cluster or KinD/K3d.
- Database migration execution in container startup for production mode.
- Console container runtime environment injection proof.

Production impact:

- A project can pass local tests while failing as soon as services are separated into containers.
- Misconfigured environment variables, volumes, network names, CORS, or service health checks can remain hidden.

### P0. Frontend Is Not Sufficiently Browser-Verified

The Console now has a basic Playwright browser test harness, a production-build e2e command, and an axe critical accessibility smoke check. This is an important baseline, but it is not enough for a production control plane.

Current verified baseline:

- `@playwright/test` and `@axe-core/playwright` are installed in `apps/console`.
- `apps/console/playwright.config.ts` runs against the production preview server with the local Chrome channel.
- `npm run test:e2e` builds the Console and runs browser tests.
- `apps/console/tests/e2e/console-smoke.spec.ts` verifies anonymous redirect to login, seeded authenticated dashboard shell rendering, and no critical login-page accessibility violations.
- Verified locally on 2026-06-04: `npm run test:e2e` passed with 3 Playwright tests.

Missing:

- Browser workflow coverage beyond smoke tests.
- Accessibility checks for keyboard navigation, focus traps, focus restore, dialogs/drawers, data tables, and chart summaries.
- Responsive viewport screenshots.
- Visual regression or screenshot diff for key pages.
- API failure and loading state interaction tests.
- Real browser test against mocked API and against a live local backend.
- Modal/drawer escape behavior, focus restore, and scroll locking.

Production impact:

- Contract tests can assert strings exist while the actual UI is unusable, clipped, inaccessible, or broken after state changes.
- Production operators need dependable workflows under pressure.

### P0. Production Security Defaults Are Too Permissive

Current config still defaults to dev mode, SQLite, local object store, default object store credentials, and default CORS origins. Docker Compose also includes obvious development credentials.

Missing:

- Production mode startup guard that rejects default secrets, memory stores, SQLite, permissive CORS, and dev auth shortcuts.
- Secret provider integration beyond in-memory provider boundaries.
- Password policy with lockout, throttling, session rotation, and optional MFA/SAML/OIDC path.
- API key hashing and rotation policy verified across all machine identity flows.
- Security headers for Console and API edge.
- CSRF stance for cookie-based console auth, if cookies remain supported.
- Rate limiting for auth, admin writes, invoke endpoints, and replay endpoints.
- Dependency vulnerability scanning and container image scanning in CI.

Production impact:

- A deployment can look successful while running with unsafe defaults.
- Operator identity and machine identity flows are central control-plane attack surfaces.

### P0. Runtime Guarantees Need Full End-To-End Proof

The durable worker has meaningful tests, but production-grade means proving the whole state machine through real service boundaries.

Missing:

- Multi-worker duplicate execution prevention test against real Redis/Postgres.
- Crash-after-lease and crash-after-event persistence tests.
- Retry exhaustion and dead-letter recovery from a separate worker process.
- Pub/sub cancel across worker replicas in a real Redis-backed environment.
- Backpressure behavior under queue pressure.
- Long-running stream interruption and reconnect behavior with persisted events.
- Worker graceful shutdown semantics.
- Agent package load isolation and cleanup after failure.

Production impact:

- Runtime platforms fail at the edges: duplicate work, stuck leases, lost events, and impossible-to-debug partial runs.

---

## 5. Backend Gap Inventory

### 4.1 API Surface and Contract Governance

Current strengths:

- Native APIs exist for agents, versions, deployments, runs, tasks, events, attempts, and deployment tasks.
- OpenAPI export and diff scripts exist.
- Stable error shape is present in many endpoints.

Gaps:

- Admin router is very large and generic. It needs stronger typed service boundaries and per-resource validation.
- Cursor pagination, filtering, sorting, and time-range semantics are incomplete or inconsistent.
- Some list endpoints return bounded or unbounded arrays without a stable paging contract.
- Error codes need a generated registry and contract test coverage for every route.
- Idempotency is memory-backed through `IdempotencyStore` even in SQLAlchemy native runtime, despite an `idempotency_records` table existing.
- Request validation should constrain status values, environment names, version strings, package URIs, JSON payload size, and manifest shape.
- API versioning strategy is not operationalized beyond route naming and OpenAPI.

Required work:

- [ ] Split admin API into typed routers by domain: identity, governance, observability, enterprise ops, published surfaces.
- [ ] Add typed service methods behind each admin router.
- [ ] Add cursor pagination models for all list APIs.
- [ ] Add route-level OpenAPI contract tests that assert auth, request ID, error response, and pagination metadata.
- [ ] Replace in-memory idempotency storage with SQLAlchemy-backed idempotency records in production mode.
- [ ] Add payload-size limits and structured `request_payload_too_large` errors.
- [ ] Add status enum validation for Agent, AgentVersion, Deployment, Task, Run, HumanTask, and admin resources.

### 4.2 Persistence and Migrations

Current strengths:

- SQLAlchemy models and Alembic migrations exist.
- Migration tests compare ORM metadata with Alembic-created schemas.
- Soft delete and audit fields are present across many models.

Gaps:

- Placeholder metadata tables remain intentionally incomplete.
- Migration tests are mostly schema-level, not upgrade-from-real-previous-state tests.
- No seeded production baseline data migration is defined.
- No explicit data retention, archival, partitioning, or pruning jobs are wired for high-volume tables.
- No online migration strategy is documented for large tables.
- No backup/restore execution test against an actual Postgres dump.

Required work:

- [ ] Replace placeholder metadata tables with finalized first-class domain models or explicitly mark them as non-production features.
- [ ] Add upgrade tests from a fixture database generated at revision `0009` to `head`.
- [ ] Add data backfill tests for nullable-to-not-nullable transitions.
- [ ] Add retention jobs for events, attempts, audit logs, artifacts, idempotency records, and dead-letter tasks.
- [ ] Add partitioning strategy for events and audit logs.
- [ ] Add Postgres backup and restore smoke using Docker Compose.

### 4.3 Scheduler and Worker Runtime

Current strengths:

- SQLAlchemy task backend, Redis backend tests, quotas, leases, heartbeat, reaper, fencing, retry, dead-letter, and worker executor tests exist.
- Worker one-shot mode can execute durable tasks.

Gaps:

- Worker long-running mode is a simple loop around `run_once`.
- Worker runtime specs are rebuilt from AgentVersion rows and do not yet include resolved secrets, sandbox policy, model gateway, tool gateway, execution profile, or deployment config.
- No production plugin/adapter loading isolation beyond Python process loading.
- No per-run resource limits are enforced by the worker process.
- No structured worker readiness and liveness endpoints.
- No worker drain protocol for deployment rolling updates.
- Queue fairness and priority scheduling are not fully specified.

Required work:

- [ ] Add a `WorkerRuntimeConfigResolver` that combines AgentVersion manifest, Deployment config, ExecutionProfile, SandboxPolicy, SecretProvider, and ModelGateway.
- [ ] Add worker graceful shutdown: stop leasing, finish active attempt or cancel by timeout, update heartbeat.
- [ ] Add worker readiness/liveness endpoints or heartbeat table semantics consumable by orchestration.
- [ ] Add multi-worker integration test using two worker processes and one shared Postgres/Redis environment.
- [ ] Add crash recovery integration test: kill worker mid-attempt, run reaper, assert retry or dead-letter.
- [ ] Add queue priority and fairness policy if multiple tenants/projects share workers.
- [ ] Add worker metrics: lease latency, execution latency, retry count, dead-letter count, active attempts, heartbeat age.

### 4.4 Adapter and Agent Package System

Current strengths:

- LangGraph, LangChain Agent, and DeepAgents adapter classes exist.
- Manifest parsing and compatibility tests exist.
- Example packages exist for LangGraph.

Gaps:

- LangChain and DeepAgents examples are only placeholder README-level entries.
- Adapter tests use fake framework objects heavily. That is useful, but not enough.
- Agent package loading does not yet prove safe dependency isolation.
- No signed package, checksum, provenance, or allowlist policy.
- No upload/registry workflow in Console.
- No package vulnerability scan.
- No clear distinction between local file package URIs and production artifact/package URIs.

Required work:

- [ ] Add runnable LangChain Agent and DeepAgents example packages equivalent to the LangGraph support examples.
- [ ] Add adapter smoke tests using real framework packages from the locked dependency set.
- [ ] Add package validation service that verifies manifest, entrypoint, checksum, dependency policy, and required secrets before activation.
- [ ] Add package storage abstraction for uploaded agent packages.
- [ ] Add package provenance metadata: uploader, checksum, source, build time, framework version, dependency lock hash.
- [ ] Add Console package registration and validation UX.
- [ ] Add a production rule that rejects `file://` package URIs unless explicitly enabled for dev/local mode.

### 4.5 Governance, Policy, Secrets, and Model Gateway

Current strengths:

- Policy engine, tool gateway, secret provider, model gateway provider, sandbox policy, and human task service boundaries exist.
- Admin CRUD surfaces expose many governance resources.

Gaps:

- Many governance services are in-memory or boundary-only.
- Runtime execution path does not fully enforce all governance services during real agent execution.
- Secret values are not integrated with an external KMS or Kubernetes Secret provider implementation.
- Model gateway provider is not a real proxy/client path with budget metering and provider telemetry.
- Tool gateway is not fully wired into adapter execution for arbitrary tools.
- Approval workflows exist, but production resume semantics through real agent frameworks need stronger proof.

Required work:

- [ ] Add production `SecretProvider` implementation for Kubernetes Secret and environment-backed dev mode, with audit logging.
- [ ] Add model gateway execution wrapper with provider selection, budget policy, fallback policy, timeout, retry, and token/cost accounting.
- [ ] Add tool gateway integration into runtime context so agent tool calls can be observed and governed.
- [ ] Add policy decision persistence for every deny, approve, and fallback decision.
- [ ] Add approval resume integration tests for LangGraph interrupt/resume through a real worker.
- [ ] Add Console policy simulation view before policy activation.

### 4.6 Observability, Audit, Metrics, and Tracing

Current strengths:

- Event model, audit log model, artifact stores, metrics registry, notification service, run graph projection, and external exporter boundaries exist.
- Run events and attempts are visible through native API and Console.

Gaps:

- No production `/metrics` endpoint or OpenTelemetry exporter is wired into FastAPI and worker.
- Event API still has limited querying, retention, and export semantics.
- Dashboard metrics are mostly derived in Console instead of backend runtime metrics endpoints.
- Trace correlation between request ID, run ID, task ID, attempt ID, event ID, audit ID, and artifact ID needs a uniform model.
- Redaction and sampling policies are not obviously enforced across every event source.
- Incident and alerting services need live delivery proofs.

Required work:

- [ ] Add backend runtime metrics API: dashboard summary, queue metrics, worker metrics, deployment health, cost, latency percentiles.
- [ ] Add Prometheus-compatible metrics endpoint.
- [ ] Add OpenTelemetry instrumentation for FastAPI requests, worker attempts, adapter calls, model gateway calls, and tool calls.
- [ ] Add event query API with cursor, time range, run ID, deployment ID, event type, visibility level, and actor filters.
- [ ] Add trace correlation fields to API responses and logs.
- [ ] Add redaction policy tests against real runtime event writes.
- [ ] Add notification delivery tests using local webhook receiver.

### 4.7 Security and Compliance

Gaps:

- No CI security scanning found in the repository.
- No SAST/dependency/container image scan pipeline.
- No documented threat model.
- No per-endpoint rate limiting.
- No production secret default rejection.
- No security headers and Content Security Policy for the Console container.
- No audit immutability or tamper-evidence plan.
- No data classification policy for payloads, outputs, artifacts, and logs.

Required work:

- [ ] Add `docs/THREAT_MODEL.md` covering Console, API, worker, agent package loading, secrets, model gateway, tool gateway, and artifact store.
- [ ] Add production startup guard for unsafe defaults.
- [ ] Add rate limiting middleware keyed by actor, API key, tenant, project, and endpoint class.
- [ ] Add security headers for API and Console: CSP, HSTS where TLS terminates in-app, X-Content-Type-Options, Referrer-Policy, Frame-Options or frame ancestors.
- [ ] Add dependency scan and container scan in CI.
- [ ] Add secret scanning in CI.
- [ ] Add audit log hash chaining or immutable external sink option.

---

## 6. Frontend Console Gap Inventory

### 5.1 Product UX and Information Architecture

Current strengths:

- Console has real runtime routes and broad management coverage.
- Major workflows exist: agents, versions, deployments, tasks, runs, events, replay, published surfaces, identity, governance, admin collections.
- Offline and loading states exist through `ApiState`.

Gaps:

- Several workflows are dense and page-local, especially `AgentsPage.vue`, `DeploymentsPage.vue`, `PublishedSurfacesPage.vue`, and `AdminCollectionPage.vue`.
- Generic admin CRUD is useful for coverage but not polished enough for high-risk production operations.
- The Console lacks guided onboarding for first production setup.
- There is no global command/search behavior beyond a visual search input.
- Tables likely need server-side pagination and filtering once data volume grows.
- Error recovery is mostly page-level text, not structured retry/action guidance.
- Operator workflow for package validation, deployment promotion, rollback, and incident triage is incomplete.

Required work:

- [ ] Replace generic CRUD for high-risk domains with domain-specific pages, starting with policies, model gateways, secrets, tools, replay jobs, experiments, incidents, and backup/restore.
- [ ] Split large pages into focused components: list table, detail panel, forms, drawers, confirm dialogs, state mappers.
- [ ] Add first-run setup flow: create tenant/project/environment, create service account/API key, register first agent, create deployment, submit test task.
- [ ] Add global command/search behavior or remove the nonfunctional search field until implemented.
- [ ] Add server-side pagination/filter UI for runs, tasks, events, audit logs, and admin collections.
- [ ] Add deployment promotion and rollback UX.
- [ ] Add incident triage view combining events, attempts, audit trail, artifacts, and worker/deployment metrics.
- [ ] Add package validation UX with manifest preview, missing secrets, dependency warnings, and runtime compatibility result.

### 5.1.1 Required Product Workflow Closure

These workflows should be treated as product features, not admin-table entries:

- [ ] **Agent package registration:** Upload or reference package, parse manifest, validate entrypoint, show framework compatibility, show missing secrets, block readiness until validation passes.
- [ ] **Agent version release:** Draft -> validate -> ready -> disabled/archived with explicit status reasons and immutable release facts.
- [ ] **Deployment promotion:** Create draft deployment, activate, pause, resume, drain, stop, restart, promote candidate version, rollback to previous version, inspect active config.
- [ ] **Run triage:** Open failed run, see input/output/error/events/attempts/artifacts/audit in one incident-style view, retry/replay/cancel with context.
- [ ] **Replay comparison:** Select source run and candidate version, create replay, compare input/output/events/latency/errors, save to dataset or experiment.
- [ ] **Policy authoring:** Build policy condition, simulate against a resource/action, preview matched resources, activate with audit reason, rollback.
- [ ] **Human approval:** Queue assignment, decision detail, requested action, risk reason, approve/reject/comment, resume result.
- [ ] **Model gateway:** Configure provider, validate credential ref, test model call, define budget/fallback, inspect usage and provider failures.
- [ ] **Tool governance:** Register tool schema, classify risk, bind approval policy, dry-run tool call, inspect tool call history.
- [ ] **Secret management:** Register external secret ref, validate access, rotate, show last-used metadata, never expose value.
- [ ] **Quality loop:** Capture run to dataset, create experiment, execute evaluator, inspect score distribution, enforce quality gate before promotion.
- [ ] **Incident and notification:** Define alert, test notification, see delivery attempts, acknowledge incident, resolve with audit note.
- [ ] **Backup/restore:** Configure plan, run dry-run restore, inspect validation results, block destructive restore without confirmation and scope proof.

### 5.2 Frontend Engineering Quality

Gaps:

- No Vitest unit tests.
- No component tests.
- Playwright E2E exists only as a smoke baseline.
- Accessibility automation exists only as a critical login-page axe check.
- No visual regression.
- No network mock layer for deterministic UI tests.
- No generated API client drift check in frontend CI.
- No lint script in `apps/console/package.json`.
- No shared query/mutation abstraction.
- No typed form/schema validation layer for complex Console forms.
- No route-level loader and scope-change invalidation model.

Required work:

- [ ] Add `vitest` for pure mapping and composable tests.
- [x] Add Playwright for browser smoke workflows.
- [x] Add axe critical accessibility smoke check for the login page.
- [ ] Add MSW or equivalent API mocking for Console tests.
- [ ] Expand axe accessibility checks to dashboard, admin tables, drawers, dialogs, forms, charts, and destructive confirmations.
- [ ] Add screenshot tests for desktop and mobile viewports.
- [ ] Add frontend lint and format checks.
- [ ] Add generated client drift check against `openapi/dimoorun.openapi.json`.
- [ ] Add a `useQueryResource` composable for loading, aborting, retrying, stale response protection, and scope-change reloads.
- [ ] Add a `useMutationAction` composable for create/update/delete/control actions with busy state, error normalization, canonical reload, and audit metadata.
- [ ] Add typed form validators for AgentVersion, Deployment, Policy, ModelGateway, Tool, Secret, Replay, Experiment, BackupPlan, and RestoreJob.

### 5.3 Frontend Accessibility and Interaction Details

Gaps:

- Drawers and dialogs need focus trap, Escape close, focus restore, and scroll lock verification.
- Keyboard table row selection exists on several pages, but full tab order and screen reader semantics need review.
- Loading states use panels rather than skeletons for dense tables.
- Some visible text remains hard-coded in Chinese or English in templates.
- Iconography uses glyph/text in places instead of a consistent icon library.
- Charts need richer accessible summaries, not only `role="img"`.

Required work:

- [ ] Add a shared Drawer component with focus trap, Escape behavior, aria labels, and focus restore.
- [ ] Add a shared DataTable component with keyboard navigation, selected row semantics, empty/loading/error slots, and responsive behavior.
- [ ] Add skeleton states for dashboard cards, tables, and detail panels.
- [ ] Add an i18n hard-coded-copy scan.
- [ ] Add chart summary tables for screen readers and low-vision users.
- [ ] Add responsive tests for 375px, 768px, 1280px, and 1440px widths.

---

## 7. Deployment, Operations, and Release Gaps

### 6.1 Docker Compose

Gaps:

- Compose uses development credentials.
- The production compose path does not clearly run Alembic migrations before server start.
- Console container uses Vite preview/dev style assets rather than a hardened static server contract.
- No smoke script asserts the whole system can execute a real agent run.

Required work:

- [ ] Add `scripts/compose_smoke.py` that runs build, up, health checks, migration, seed, agent registration, deployment creation, task submission, worker completion, Console API reachability, and down.
- [ ] Add production compose override with secrets passed through environment or Docker secrets.
- [ ] Add migration command to server startup or an explicit init service.
- [ ] Add Console static server health check.
- [ ] Add MinIO bucket initialization.

### 6.2 Helm and Kubernetes

Gaps:

- Helm chart is small and mostly static.
- No real `helm template` command verification was run in the reviewed history.
- No KinD/K3d deployment smoke.
- No network policies, pod disruption budgets, service monitors, or secret templates beyond references.
- No migration Job or pre-upgrade hook.
- No separate worker queue configuration.

Required work:

- [ ] Add Helm unit/static tests for all templates.
- [ ] Add KinD smoke script that deploys chart with Postgres/Redis/MinIO test dependencies or external test services.
- [ ] Add migration Job template.
- [ ] Add PodDisruptionBudget for server and worker.
- [ ] Add NetworkPolicy templates.
- [ ] Add ServiceMonitor/PodMonitor templates for Prometheus.
- [ ] Add separate values for queues, worker concurrency, and sandbox mode.

### 6.3 CI/CD and Release

Gaps:

- No `.github/workflows` or equivalent CI directory found.
- No release automation.
- No image build/push pipeline.
- No signed tags, changelog, or artifact provenance.
- No matrix across Python versions, Node versions, and DB backends.

Required work:

- [ ] Add CI workflow: backend lint, mypy, tests, migration tests, frontend test/build, OpenAPI diff.
- [ ] Add integration workflow: Docker Compose smoke with Postgres, Redis, MinIO.
- [ ] Add security workflow: dependency scan, secret scan, container scan.
- [ ] Add release workflow: version bump, changelog, image build, SBOM, signed artifacts.
- [ ] Add nightly workflow for full E2E and Helm/KinD smoke.

---

## 8. SDK and Developer Experience Gaps

Current strengths:

- Python SDK exists with a small client.
- TypeScript SDK package exists as a placeholder.
- OpenAPI JSON exists.
- CLI entrypoint exists.

Gaps:

- JS SDK is not implemented.
- Python SDK is thin and not fully generated or contract-tested across all stable APIs.
- CLI does not cover production workflows deeply enough: deploy, invoke, logs, replay, doctor against live stack, package validate/upload.
- Docs are design-heavy but lack operator runbooks and external user guides.

Required work:

- [ ] Generate Python and TypeScript SDKs from OpenAPI or enforce hand-written SDK contract parity.
- [ ] Add SDK integration tests against local FastAPI test app and Docker Compose.
- [ ] Add CLI commands for `agent register`, `version publish`, `deployment create`, `task submit`, `run watch`, `run replay`, `package validate`, and `doctor production`.
- [ ] Add quickstart guide that starts Compose, registers example agent, submits task, and inspects Console.
- [ ] Add operator runbooks for stuck tasks, dead letters, failed deployments, replay, key rotation, backup, restore, and incident response.

---

## 9. Detailed Execution Roadmap

### Roadmap Execution Rules

Every phase below must be treated as a shippable slice, not as a loose theme. Before implementation starts for any phase, the implementing agent should add or confirm these fields in the phase-specific execution plan:

- **User value:** the exact user job, decision, risk, and success signal.
- **Non-goals:** what the phase must not become, especially no low-code builder, no workflow canvas, no prompt design platform, no full billing system, and no Policy Engine bypass.
- **Read model:** the backend-derived view the Console consumes instead of reconstructing product meaning from raw rows.
- **Action model:** create/update/control actions, disabled-action reasons, policy decision, audit note, and rollback/recovery path.
- **Browser evidence:** Playwright workflow test, critical accessibility check, desktop/mobile screenshot, and API error-state proof.
- **Exit metric:** one or more measurable checks such as tests passed, smoke command passed, axe critical violations equal zero, or OpenAPI diff accepted.

### Phase -3: User Task And Experience Baseline

**Goal:** Define the Console from user jobs, decisions, risks, and recovery paths before adding more screens or workflow APIs.

**Files:**

- Create: `docs/product/console-user-task-model.md`
- Create: `docs/product/console-experience-acceptance.md`
- Modify: `docs/plans/production-grade-gap-closure-2026-06-04.md`

Tasks:

- [x] Define primary user roles: platform operator, agent developer, governance/security reviewer, incident responder, and auditor.
- [x] For each role, document the top jobs: first-run setup, daily monitoring, deploy/change, failed-run triage, approval decision, audit review, rollback, key rotation, and restore dry-run.
- [x] For each job, document what the user needs before acting: current scope, resource health, last change, permissions, risk, affected resources, audit requirement, and rollback path.
- [x] Define success feedback and failure recovery for every high-risk action: what changed, what did not change, where to verify it, what can be retried, and what requires escalation.
- [x] Add UX acceptance criteria for each core workflow: task completion, visible system status, field validation, empty state, loading state, error state, keyboard flow, and responsive behavior.
- [ ] Commit as `docs(console): define user task model and experience acceptance`.

Acceptance:

- Product work cannot start from database resources alone. Every workflow phase must point to a user job, decision, risk, and recovery path.

### Phase -2: Product Workflow Spec Reconciliation

**Goal:** Convert the broad design spec into an explicit product workflow backlog so implementation work stops counting generic CRUD as feature completion.

**Files:**

- Create: `docs/product/workflow-coverage-matrix.md`
- Create: `docs/PRODUCT_WORKFLOW_ACCEPTANCE.md`
- Create: `docs/product/function-coverage-review.md`
- Create: `docs/product/optimization-backlog.md`
- Modify: `docs/readiness/scorecard.md`
- Modify: `docs/plans/production-grade-gap-closure-2026-06-04.md`

Tasks:

- [x] Create a matrix with rows for Agent Package, Agent Version, Deployment, Published Surface, Ingress Route, Agent Gateway, Run Triage, Replay, Scheduled Run, Batch Run, Worker, Agent Instance, Policy, Human Approval, Model Gateway, Tool Gateway, Secret, Dataset, Experiment, Catalog, Prompt Asset, Config Asset, Template Asset, Incident, Notification, Backup, Restore, Compatibility, Identity, Cost, Budget, and Settings.
- [x] For each row, mark backend model, backend domain service, typed API, Console page, Console workflow, tests, and production semantics as `complete`, `partial`, or `missing`.
- [x] Mark generic `AdminCollectionPage` coverage as `partial` unless the feature has domain-specific validation and workflow actions.
- [x] Add acceptance criteria for each workflow from the user task model: user goal, pre-action context, domain validation, policy/audit behavior, success feedback, failure recovery, and browser test coverage.
- [x] Map each workflow to design guardrails: Runtime Control Plane, business black box / runtime white box, no low-code builder, no prompt designer, no workflow builder, no Policy Engine bypass.
- [x] Create `docs/product/function-coverage-review.md` with coverage verdicts for agent lifecycle, runtime execution, debug/replay, governance, external exposure, compatibility, operations, identity, quality, cost, catalog/assets, platform settings, developer experience, and product soft power.
- [x] Create `docs/product/optimization-backlog.md` with prioritized optimization items for guided activation, runtime workbench, action center, resource graph, impact preview, compare/diff, saved views, evidence bundles, feedback capture, integration health, environment promotion lanes, product telemetry, collaboration notes, capability explainers, and polished empty states.
- [x] For each optimization, record priority, target user, product value, product risk, engineering risk, effort size, dependency, boundary guardrail, affected phases, required backend read model, required Console workflow, and browser test evidence.
- [x] Use a priority table with these columns: `Priority`, `User`, `Value`, `Risk`, `Effort`, `Dependency`, `Phase`, `Read Model`, `Console Workflow`, `Browser Evidence`, and `Non-goal Guardrail`.
- [x] Mark items `P0` only when they unblock activation, runtime trust, governance safety, compatibility confidence, or production recovery.
- [x] Define backlog budget rules: `P0` must be completed before External GA, `P1` belongs to Competitive Excellence, and `P2` stays in later roadmap unless it removes a proven activation or recovery blocker.
- [x] Define backlog exit rules: remove or defer any optimization that cannot map to runtime control, operational trust, migration confidence, governance, quality, or developer activation.
- [x] For telemetry-related optimizations, require tenant/project scoping, redaction, sampling, retention policy, opt-out/disable behavior, and documentation in `docs/TRUST_AND_SECURITY.md`.
- [x] For collaboration-related optimizations, require evidence-bound notes only and explicitly reject project management, task assignment, kanban, SLA ticket routing, or ITSM replacement scope.
- [ ] Commit as `docs(product): define workflow coverage matrix`.

Acceptance:

- The team can no longer confuse resource CRUD coverage with product workflow completion.

### Phase -1A: Frontend Test Harness Baseline

**Goal:** Put deterministic frontend tests in place before building complex workflows.

**Files:**

- Modify: `apps/console/package.json`
- Create: `apps/console/vitest.config.ts`
- Create: `apps/console/tests/fixtures/api.ts`
- Create: `apps/console/tests/e2e/workflow-shell.spec.ts`
- Create: `apps/console/tests/e2e/accessibility.spec.ts`
- Test: `apps/console/tests/unit/query.test.ts`

Tasks:

- [x] Install and configure Vitest for pure TypeScript/composable tests with a `test:unit` script.
- [x] Add deterministic API mocking for Playwright using route interception or MSW, choosing the smallest approach that fits the current Vite/Vue setup.
- [x] Extend `npm run test:e2e` to cover smoke tests plus the mocked API workflow shell.
- [x] Add e2e fixtures for authenticated operator session, scoped tenant/project/environment, API error responses, empty pages, and slow loading states.
- [x] Add axe checks for dashboard, one dense table page, one drawer/dialog flow, and one high-risk confirmation.
- [ ] Commit as `test(console): add deterministic frontend workflow harness`.

Acceptance:

- New Console workflow phases can write browser tests before UI implementation.
- Frontend unit tests and e2e tests run independently and can be added to CI.

### Phase -1B: Frontend State Architecture Baseline

**Goal:** Stabilize frontend logic before adding more complex product workflows.

**Files:**

- Create: `apps/console/src/api/query.ts`
- Create: `apps/console/src/api/mutations.ts`
- Create: `apps/console/src/forms/jsonForm.ts`
- Create: `apps/console/src/forms/validators.ts`
- Create: `apps/console/src/components/JsonSchemaEditor.vue`
- Modify: `apps/console/src/api/client.ts`
- Modify: `apps/console/src/api/types.ts`
- Test: `apps/console/tests/console-contract.test.mjs`
- Test: `apps/console/tests/unit/query.test.ts`
- Test: `apps/console/tests/unit/mutations.test.ts`
- Test: `apps/console/tests/unit/jsonForm.test.ts`

Tasks:

- [x] Add a typed query composable with abort controller, loading/error/data states, request version guard, retry, and reload.
- [x] Add mutation helper with busy/error states, audit reason support, canonical reload, and conflict error normalization.
- [x] Add JSON editor helper that validates parse errors before submit and reports exact error location.
- [x] Add schema validators for high-risk forms: AgentVersion, Deployment config, Policy condition, ModelGateway, Tool schema, Secret ref, Replay request, Experiment, BackupPlan, RestoreJob.
- [x] Replace one page, preferably `DeploymentsPage.vue`, with the shared query/mutation layer as the reference implementation.
- [ ] Commit as `refactor(console): add shared query and form state primitives`.

Acceptance:

- New Console workflows do not implement ad hoc loading/error/mutation/JSON parsing state.

### Phase -1C: Console Aggregate And Permission API Contract

**Goal:** Give the Console stable read models and action availability contracts instead of making pages reconstruct product meaning from raw resources.

**Files:**

- Create: `apps/server/dimoo_run/api/console/router.py`
- Create: `apps/server/dimoo_run/api/console/schemas.py`
- Create: `apps/server/dimoo_run/api/console/service.py`
- Modify: `apps/server/dimoo_run/api/router.py`
- Modify: `apps/console/src/api/client.ts`
- Modify: `apps/console/src/api/generated/dimoorun.ts`
- Test: `tests/api/test_console_aggregate_api.py`
- Test: `apps/console/tests/e2e/workflow-shell.spec.ts`

Tasks:

- [x] Add `/v1/console/dashboard-summary`, `/v1/console/runtime-overview`, `/v1/console/deployment-health`, `/v1/console/worker-health`, `/v1/console/recent-failures`, and `/v1/console/pending-actions`.
- [x] Add `/v1/console/action-summary` returning per-resource action availability, disabled reasons, required permissions, policy warnings, and audit requirements.
- [x] Ensure aggregate APIs filter by tenant/project/environment and never expose unauthorized run input/output, secret values, or hidden audit payloads.
- [x] Generate/update the TypeScript client and route all dashboard/runtime shell reads through the Console aggregate API.
- [x] Add e2e assertions that disabled actions explain why they are unavailable and that hidden actions are not used as authorization.
- [ ] Commit as `feat(console): add aggregate read models and action summary`.

Acceptance:

- Console pages use stable product read models and backend-derived action availability.
- Policy Engine remains the authority; frontend permission state is display guidance and never the enforcement source.

### Phase 0A: Agent Package And Version Readiness Workflow

**Goal:** Let an agent developer register a package, validate it, and move a version to `ready` only when runtime compatibility is proven.

**Files:**

- Create: `apps/server/dimoo_run/api/native/packages.py`
- Create: `apps/server/dimoo_run/packages/validation.py`
- Create: `apps/console/src/pages/packages/PackageRegistrationPage.vue`
- Modify: `apps/console/src/router/index.ts`
- Modify: `apps/console/src/layouts/AppShell.vue`
- Test: `tests/api/test_package_workflow.py`
- Test: `apps/console/tests/e2e/package-version-workflow.spec.ts`

Tasks:

- [x] Add package validation API: validate manifest, entrypoint, runtime pair, required secrets, package URI policy, and framework compatibility.
- [x] Add AgentVersion readiness gate: only validated versions can become `ready`.
- [x] Build Package Registration page with manifest preview, missing secret refs, dependency warnings, capability result, validation errors, and next action.
- [x] Add browser tests for valid package, invalid manifest, missing secret, unsupported capability, and readiness gate.
- [ ] Commit as `feat(product): add package validation workflow`.

Acceptance:

- A real developer can validate a package and understand exactly why a version can or cannot become runnable.

### Phase 0B: Deployment Promotion And Rollback Workflow

**Goal:** Let an operator activate, promote, pause, resume, drain, stop, and rollback deployments with impact preview and audit evidence.

**Files:**

- Create: `apps/server/dimoo_run/api/native/promotion.py`
- Modify: `apps/server/dimoo_run/api/native/deployments.py`
- Modify: `apps/console/src/pages/deployments/DeploymentsPage.vue`
- Create: `apps/console/src/pages/deployments/DeploymentDetailPage.vue`
- Test: `tests/api/test_deployment_promotion.py`
- Test: `apps/console/tests/e2e/deployment-promotion.spec.ts`

Tasks:

- [x] Add deployment promotion API: candidate version, previous version, rollout reason, rollback target, idempotency key, and promotion audit.
- [x] Add backend impact preview: affected deployment, current desired/runtime status, active runs, queued tasks, candidate validation status, and rollback path.
- [x] Add Console workflow with pre-action impact, confirmation, audit reason, progress state, success feedback, and rollback affordance.
- [x] Add browser tests for promote, rollback, pause/resume, policy denied action, and stale deployment conflict.
- [ ] Commit as `feat(product): add deployment promotion workflow`.

Acceptance:

- A production operator can change deployment state without guessing impact or losing rollback context.

### Phase 0C: Run Triage And Replay Comparison Workflow

**Goal:** Let an incident responder diagnose a failed run, create replay, compare candidate output, and preserve provenance.

**Files:**

- Create: `apps/server/dimoo_run/api/native/replay_jobs.py`
- Modify: `apps/server/dimoo_run/api/native/runtime.py`
- Create: `apps/console/src/pages/runs/RunTriagePage.vue`
- Create: `apps/console/src/pages/replay/ReplayComparisonPage.vue`
- Modify: `apps/console/src/router/index.ts`
- Test: `tests/api/test_replay_comparison.py`
- Test: `apps/console/tests/e2e/run-triage-replay.spec.ts`

Tasks:

- [x] Add replay comparison API: source run, candidate version, replay config, output/event/error diff, latency/cost comparison, and replay provenance.
- [x] Build Run Triage page that combines input/output/error/events/attempts/artifacts/audit in one incident-style view.
- [x] Build Replay Comparison page with source/candidate comparison, diff states, save-to-dataset action, and regression signal.
- [x] Add browser tests for failed run triage, replay creation, comparison, dataset capture, and immutable historical run behavior.
- [ ] Commit as `feat(product): add run triage and replay comparison`.

Acceptance:

- A responder can explain why a run failed and whether a candidate version improves it without leaving the Console.

### Phase 0D: Policy And Human Approval Workbench

**Goal:** Let governance reviewers author, simulate, activate, approve, reject, and audit policy-controlled actions.

**Files:**

- Create: `apps/server/dimoo_run/api/admin/policies.py`
- Modify: `apps/server/dimoo_run/api/admin/router.py`
- Create: `apps/console/src/pages/policies/PolicyWorkbenchPage.vue`
- Modify: `apps/console/src/pages/governance/HumanTasksPage.vue`
- Test: `tests/api/test_policy_workbench.py`
- Test: `apps/console/tests/e2e/policy-approval.spec.ts`

Tasks:

- [x] Add policy simulation API: draft policy, resource/action sample, matched resources, decision result, audit preview, and conflict warnings.
- [x] Add activation API with version, audit reason, rollback target, and conflict detection.
- [x] Expand Human Tasks with assignment, decision context, requester, risk reason, diff, approve/reject/comment, and resume outcome.
- [x] Add browser tests for simulate, activate, rollback, approve, reject, policy denied, and approval resume visibility.
- [ ] Commit as `feat(governance): add policy and approval workbench`.

Acceptance:

- A reviewer can make and defend governance decisions from visible context, not raw JSON.

### Phase 0E: Gateway, Tool, And Secret Governance Workflow

**Goal:** Make model, tool, and secret resources safe to configure because every high-risk path has validation, dry-run, and audit feedback.

**Files:**

- Create: `apps/server/dimoo_run/api/admin/model_gateways.py`
- Create: `apps/server/dimoo_run/api/admin/tools.py`
- Create: `apps/server/dimoo_run/api/admin/secrets.py`
- Create: `apps/console/src/pages/governance/ModelGatewayWorkbenchPage.vue`
- Create: `apps/console/src/pages/governance/ToolGatewayWorkbenchPage.vue`
- Create: `apps/console/src/pages/governance/SecretRotationPage.vue`
- Test: `tests/api/test_gateway_governance_workflows.py`
- Test: `apps/console/tests/e2e/gateway-governance.spec.ts`

Tasks:

- [x] Add model gateway test API: credential ref validation, safe health probe, budget preview, fallback preview, provider error normalization.
- [x] Add tool dry-run API: schema validation, risk classification, policy preview, approval requirement, and usage-history link.
- [x] Add secret validation and rotation API without exposing values, including last-used metadata and access audit.
- [x] Build Console workbench pages with field-level validation, dry-run results, disabled action reasons, and audit notes.
- [ ] Commit as `feat(governance): add gateway and secret workflows`.

Acceptance:

- Operators can validate model/tool/secret configuration before runtime execution depends on it.

### Phase 0F: Quality, Dataset, And Experiment Workflow

**Goal:** Turn replay and evaluation records into a usable quality loop before deployment promotion.

**Files:**

- Create: `apps/server/dimoo_run/api/admin/datasets.py`
- Create: `apps/server/dimoo_run/api/admin/experiments.py`
- Create: `apps/console/src/pages/quality/DatasetsPage.vue`
- Create: `apps/console/src/pages/quality/ExperimentsPage.vue`
- Create: `apps/console/src/pages/quality/QualityGatePage.vue`
- Test: `tests/api/test_quality_workflows.py`
- Test: `apps/console/tests/e2e/quality-loop.spec.ts`

Tasks:

- [x] Add run-to-dataset capture API with redaction, provenance, scope, and duplicate handling.
- [x] Add experiment execution API with evaluator config, candidate version, score distribution, and promotion gate result.
- [x] Add quality gate summary for deployment promotion decisions.
- [x] Add browser tests for capture, experiment run, failed gate, passed gate, and promotion gate visibility.
- [ ] Commit as `feat(quality): add dataset experiment workflow`.

Acceptance:

- Promotion can depend on visible quality evidence instead of manual inspection.

### Phase 0G: Incident, Notification, Backup, And Restore Workflow

**Goal:** Make enterprise operations usable from runbooks and workflow screens, not generic resource tables.

**Files:**

- Create: `apps/server/dimoo_run/api/admin/incidents.py`
- Create: `apps/server/dimoo_run/api/admin/notifications.py`
- Create: `apps/server/dimoo_run/api/admin/backups.py`
- Create: `apps/console/src/pages/incidents/IncidentTriagePage.vue`
- Create: `apps/console/src/pages/ops/BackupRestorePage.vue`
- Test: `tests/api/test_enterprise_ops_workflows.py`
- Test: `apps/console/tests/e2e/enterprise-ops.spec.ts`

Tasks:

- [x] Add incident acknowledge/resolve API with audit note, timeline, linked runs/tasks/events, and notification delivery attempts.
- [x] Add notification test-send API and delivery-attempt visibility.
- [x] Add backup dry-run and restore dry-run workflow with scope proof, validation result, and destructive confirmation.
- [x] Add browser tests for acknowledge, resolve, notification test, backup dry-run, restore dry-run, and blocked destructive restore.
- [ ] Commit as `feat(ops): add incident and recovery workflows`.

Acceptance:

- Operators can respond to incidents and recovery actions with evidence, audit, and guardrails.

### Phase 0H: Published Surface, Ingress, And Agent Gateway Workflow

**Goal:** Make external runtime exposure a governed product workflow, not a generic published-surface record.

**Product stance:** `PublishedSurface` and Agent Gateway are runtime entry points. They must not become an app builder, low-code designer, or business routing DSL.

**Files:**

- Create: `apps/server/dimoo_run/api/admin/published_surfaces.py`
- Create: `apps/server/dimoo_run/api/admin/ingress_routes.py`
- Create: `apps/server/dimoo_run/api/ingress.py`
- Create: `apps/server/dimoo_run/api/console/published.py`
- Create: `apps/server/dimoo_run/gateway/route_tester.py`
- Create: `apps/console/src/pages/published/PublishedSurfacesPage.vue`
- Test: `tests/api/test_published_surface_workflows.py`
- Test: `apps/console/tests/e2e/published-surfaces.spec.ts`
- Evidence: `apps/console/scripts/published-surface-live-smoke.mjs`
- Evidence: `apps/console/scripts/run-live-e2e.mjs`
- Evidence: `apps/console/scripts/start-live-backend.mjs`
- Evidence: `apps/console/scripts/verify-live-e2e-report.mjs`

Implementation note:

- `PublishedSurfacesPage.vue` now serves both the collection view and the `/published-surfaces/:surfaceId` governed detail workflow.
- The route tester is implemented as an embedded detail-panel workflow inside `PublishedSurfacesPage.vue` rather than a separate `IngressRouteTester.vue` file.

Tasks:

- [x] Add publish validation API that checks route path, auth mode, deployment binding, environment scope, CORS policy, rate limit policy, and policy-engine enforcement.
- [x] Add publish-time active policy-engine enforcement that blocks denied publishes before creating surface or rollout history.
- [x] Add publish and live ingress require-approval policy handling with approval-required evidence.
- [x] Add live ingress allow-with-redaction and allow-with-limit policy decision evidence in responses, request logs, and evidence bundles.
- [x] Add policy composition for live ingress allow-with-limit plus allow-with-redaction effects through the shared PolicyEngine path.
- [x] Add route test API that submits a synthetic request and returns matched deployment, auth decision, policy decision, expected runtime task shape, and blocked reasons.
- [x] Add live ingress policy-engine evaluation for published route invocation, including policy-denied 403 request-log evidence.
- [x] Add live ingress rate-limit enforcement proof with 429 request-log evidence.
- [x] Add live ingress traffic split and shadow-mode decision evidence in responses and request logs.
- [x] Add rollback live route-binding verification evidence for restored published surfaces.
- [x] Add live exposure-health read model from real ingress request logs and blocked surface state.
- [x] Add request log read model with status, latency, auth result, policy result, run/task linkage, trace ID, and redacted request metadata.
- [x] Add evidence-bundle metadata to request logs and rollout history with stable bundle IDs, resource references, redaction policy, decision summaries, and audit scope.
- [x] Add Console evidence-bundle catalog listing with export links and immutable AuditLog-backed recorded status.
- [x] Add dedicated durable evidence-bundle store with recorded/exported lifecycle state.
- [x] Add evidence-bundle retention/archive lifecycle state with retained-until metadata and immutable archive audit records.
- [x] Add redacted evidence-bundle export by bundle ID for request-log and rollout evidence.
- [x] Add immutable AuditLog records for evidence-bundle export actions with redacted payload summaries.
- [x] Add immutable AuditLog indexing for created evidence bundles.
- [x] Add rollout controls for enable, disable, revoke, traffic split, route shadow mode, and rollback to previous surface version.
- [x] Add Console workflow with surface summary, deployment binding health, request logs, route tester, rollout history, and dangerous-action confirmation.
- [x] Add browser tests for publish, blocked invalid route, route test, request-log drilldown, revoke, traffic split, and rollback.
- [ ] Commit as `feat(gateway): add governed published surface workflow`.

Acceptance:

- A platform engineer can safely expose an agent runtime endpoint, prove the route before traffic, inspect real requests, and revoke exposure with audit evidence.

Current status note on 2026-06-09:

- Local real-terminal `npm run test:e2e:live:local` evidence is now green for
  the governed browser path.
- Phase 0H still stays `partial` in the readiness scorecard until hosted CI
  proves the default Playwright-managed Chromium path and publishes the
  dedicated artifact.

### Phase 0I: Compatibility Migration And Runtime Explorer Workflow

**Goal:** Turn LangGraph and Agent Protocol compatibility from an informational page into a migration and runtime confidence product.

**Product stance:** Compatibility API is an ecosystem entry and migration bridge. Native DimooRun semantics remain the source of truth, and compatibility must not bypass tenant, policy, secrets, model gateway, tool gateway, audit, or runtime state machines.

**Files:**

- Create: `apps/server/dimoo_run/api/console/compatibility.py`
- Create: `apps/server/dimoo_run/compatibility/migration_report.py`
- Create: `apps/server/dimoo_run/compatibility/golden_runner.py`
- Create: `apps/console/src/pages/compatibility/CompatibilityExplorerPage.vue`
- Create: `apps/console/src/pages/compatibility/CompatibilityRequestBuilder.vue`
- Create: `apps/console/src/pages/compatibility/MigrationReportPanel.vue`
- Test: `tests/api/test_compatibility_console_workflows.py`
- Test: `tests/compatibility/test_golden_runtime_alignment.py`
- Test: `apps/console/tests/e2e/compatibility-explorer.spec.ts`

Tasks:

- [x] Add Console APIs for LangGraph assistants, threads, runs, run cancel, run join, stream status, and last-event replay mapped onto native Agent/Run/Task/Event records.
- [x] Add migration report API that checks unsupported capabilities, required DimooRun config, adapter contract version, checkpoint requirements, streaming mode support, and governance implications.
- [x] Add request builder and stream tester for core compatibility calls with response mapping, native resource links, and capability-not-supported explanations.
- [x] Add golden compatibility runner that records request, expected third-party semantics, DimooRun response, native resources created, and divergence reason.
- [x] Add browser tests for assistant create/list, thread create, run create, stream reconnect, cancel, join, migration report, and unsupported capability explanation.
- [ ] Commit as `feat(compat): add migration and runtime explorer`.

Acceptance:

- A LangGraph user can evaluate migration effort, run a compatible workflow, see the native DimooRun resources it creates, and understand any semantic divergence.

### Phase 0J: Worker, Agent Instance, And Capacity Operations Workflow

**Goal:** Give operators a runtime capacity cockpit for worker health, agent instances, queue pressure, drain, and scaling decisions.

**Files:**

- Create: `apps/server/dimoo_run/api/console/workers.py`
- Create: `apps/server/dimoo_run/api/console/agent_instances.py`
- Create: `apps/server/dimoo_run/runtime/capacity.py`
- Create: `apps/console/src/pages/runtime/WorkersPage.vue`
- Create: `apps/console/src/pages/runtime/AgentInstancesPage.vue`
- Create: `apps/console/src/pages/runtime/CapacityPage.vue`
- Test: `tests/api/test_worker_capacity_console.py`
- Test: `apps/console/tests/e2e/runtime-capacity.spec.ts`

Tasks:

- [x] Add worker health read model with heartbeat age, active attempts, queues, drain status, version, capacity, last error, and liveness/readiness interpretation.
- [x] Add agent instance read model with deployment, version, active runs, recent failures, assigned worker, concurrency limit, and runtime config hash.
- [x] Add capacity summary with queue backlog, time-to-drain estimate, saturation, retry pressure, dead-letter pressure, and recommended operator action.
- [x] Add drain, undrain, quarantine, and restart-request actions with audit reason, permission summary, and disabled-action reasons when unsafe.
- [x] Add Console workflows for capacity overview, worker detail, agent instance detail, queue pressure drilldown, and safe drain confirmation.
- [x] Add browser tests for worker health drilldown, capacity recommendation, drain blocked by active critical attempt, successful drain, and agent instance failure navigation.
- [ ] Commit as `feat(runtime): add worker capacity operations workflow`.

Acceptance:

- Operators can answer whether the runtime has enough capacity, which worker or instance is unhealthy, what is safe to drain, and what action was taken.
- Worker drain, undrain, quarantine, and restart-request actions remain
  scope-safe even when the same `worker_id` is reused across environments.
- Local proof now includes `uv run pytest -q tests/api/test_worker_capacity_console.py tests/api/test_console_aggregate_api.py`,
  `uv run ruff check apps/server/dimoo_run/runtime/capacity.py apps/server/dimoo_run/api/console/workers.py apps/server/dimoo_run/domain/models.py apps/server/dimoo_run/api/native/runtime.py tests/api/test_worker_capacity_console.py migrations/versions/0001_baseline.py`,
  `npm run test`, `npm run test:unit`, `npm run build:e2e`, `npx playwright test tests/e2e/runtime-capacity.spec.ts --project=chrome --output test-results-0j`,
  and `npm run test:e2e:0j`. Regressions now also cover reused `worker_id`
  values across environments so queue pressure, active attempts, and worker
  control actions stay isolated to the requested scope. See
  `docs/readiness/phase-0j-evidence.md`.

### Phase 0K: Identity, Role, Permission, Session, And Machine Identity Workflow

**Goal:** Make access governance complete enough for production teams and external users.

**Files:**

- Create: `apps/server/dimoo_run/api/admin/identity_workflows.py`
- Create: `apps/server/dimoo_run/api/console/identity.py`
- Create: `apps/server/dimoo_run/identity/permission_matrix.py`
- Create: `apps/console/src/pages/identity/RolePermissionMatrixPage.vue`
- Create: `apps/console/src/pages/identity/UserAccessDetailPage.vue`
- Create: `apps/console/src/pages/identity/ServiceAccountDetailPage.vue`
- Test: `tests/api/test_identity_workflows.py`
- Test: `apps/console/tests/e2e/identity-governance.spec.ts`

Tasks:

- [x] Add role permission matrix API with effective permission preview, changed permission diff, affected users/service accounts, and policy-conflict warnings.
- [x] Add user access detail API with assigned roles, inherited permissions, active sessions, API keys created by the user, recent audit actions, and disable impact.
- [x] Add service account workflow with key creation, key rotation, disable/enable, scope diff, last-used timestamp, and dependent published surfaces or deployments.
- [x] Add session and token controls for revoke own session, revoke user sessions, rotate service account key, and force API key expiry.
- [x] Add Console role matrix with search, grouped permissions, diff before save, audit reason, and disabled-action explanations.
- [x] Add browser tests for role edit diff, blocked self-lockout, service account rotation, session revoke, and effective permission preview.
- [ ] Commit as `feat(identity): add production access governance workflow`.

Acceptance:

- Admins can change access safely, see who is affected, avoid self-lockout, rotate machine credentials, and prove all access changes through audit logs.

### Phase 0L: Platform Settings, Providers, And Dangerous Configuration Workflow

**Goal:** Turn Settings from theme/language preferences into a production platform configuration surface.

**Files:**

- Create: `apps/server/dimoo_run/api/console/settings.py`
- Create: `apps/server/dimoo_run/platform/settings_snapshot.py`
- Create: `apps/server/dimoo_run/platform/provider_status.py`
- Create: `apps/console/src/pages/settings/PlatformSettingsPage.vue`
- Create: `apps/console/src/pages/settings/ProviderStatusPage.vue`
- Create: `apps/console/src/pages/settings/DangerZonePage.vue`
- Test: `tests/api/test_platform_settings_workflows.py`
- Test: shared browser proof in `apps/console/tests/e2e/runtime-capacity.spec.ts`
- Verify: `apps/console/scripts/verify-phase-0l-proof.mjs`

Tasks:

- [x] Add settings snapshot API for runtime mode, database mode, queue backend, object store, secret provider, model gateway provider, artifact retention, trace retention, CORS, and production safety status.
- [x] Add provider status API for Postgres, Redis, MinIO/S3, secret provider, model gateway, webhook transport, notification transport, and observability exporter.
- [x] Add scoped configuration update workflow for organization defaults, project defaults, environment defaults, and runtime read-only production settings.
- [x] Add dangerous configuration workflow with preflight check, typed confirmation, affected-resource preview, rollback notes, and audit reason.
- [x] Add Console pages that separate personal preferences from platform settings, provider health, and danger zone.
- [x] Add browser tests for readonly production settings, provider outage display, environment default change, dangerous action blocked by failed preflight, and successful audited change.
- [ ] Commit as `feat(settings): add platform configuration workflow`.

Current status on 2026-06-11:

- Backend workflow coverage is locally proven through
  `uv run pytest -q tests/api/test_platform_settings_workflows.py tests/production_foundation/test_ci_workflow.py`
  and `uv run mypy apps/server tests scripts`.
- Console contract/unit/build proof is locally green through `npm run test`,
  `npm run test:unit`, and `npm run build:e2e`.
- Shared browser proof is locally green through `npm run test:e2e:0j`, which
  now executes the 0L readonly-settings, provider-outage, blocked-preflight,
  and successful dangerous-apply cases in the same runner as 0J.
- Dedicated phase verification now passes through `npm run test:e2e:0l`, which
  validates the shared runner proof marker and emits the 0L phase report.
- Dedicated CI wiring exists for `npm run test:e2e:0l` with
  `PLAYWRIGHT_HTML_REPORT=playwright-report-0l` and
  `console-playwright-0l-report`.
- Successful hosted CI run `27347574486` on 2026-06-11 now proves the default
  Playwright-managed Chromium path and publishes the dedicated
  `console-playwright-0l-report` artifact, so the readiness blocker for this
  phase is closed.

Acceptance:

- Operators can understand what mode the platform is running in, which providers are healthy, what can be changed, what is dangerous, and how to recover.

### Phase 0M: Cost, Budget, And Usage Attribution Workflow

**Goal:** Make model and runtime usage commercially useful without turning DimooRun into a billing system.

**Product stance:** DimooRun should integrate model gateway billing and expose operational cost attribution. It should not implement wallet, recharge, full invoicing, or provider-balance systems.

**Files:**

- Create: `apps/server/dimoo_run/api/console/costs.py`
- Create: `apps/server/dimoo_run/costs/attribution.py`
- Create: `apps/server/dimoo_run/costs/budget_policy.py`
- Create: `apps/console/src/pages/observability/CostsPage.vue`
- Create: `apps/console/src/pages/observability/BudgetsPage.vue`
- Test: `tests/api/test_cost_usage_workflows.py`
- Test: `apps/console/tests/e2e/costs-budgets.spec.ts`

Tasks:

- [ ] Add cost attribution read model by tenant, project, environment, agent, deployment, run, model provider, model, tool, and time window.
- [ ] Add budget policy workflow with threshold, scope, reset window, notification channel, action mode, and dry-run impact preview.
- [ ] Add anomaly detection summary for sudden token/cost spikes, provider error-cost correlation, high-cost failed runs, and top regressions after deployment.
- [ ] Add Console cost explorer with breakdown, filters, saved view, linked runs, linked deployments, and quality/failure overlays.
- [ ] Add browser tests for cost breakdown, budget dry-run, threshold notification preview, anomaly drilldown, and blocked budget action without permission.
- [ ] Commit as `feat(costs): add usage attribution and budget workflow`.

Acceptance:

- Platform teams can explain where spend comes from, catch cost regressions, set guardrails, and connect cost to runtime quality.

### Phase 0N: Scheduled And Batch Runtime Workflow

**Goal:** Cover scheduled and batch runtime as first-class task shapes without creating a business workflow builder.

**Product stance:** Scheduled, Batch, and Replay are runtime task forms. They are not a user-facing orchestration DSL and must stay within runtime control semantics.

**Files:**

- Create: `apps/server/dimoo_run/api/admin/schedules.py`
- Create: `apps/server/dimoo_run/api/admin/batches.py`
- Create: `apps/server/dimoo_run/runtime/scheduled_runs.py`
- Create: `apps/server/dimoo_run/runtime/batch_runs.py`
- Create: `apps/console/src/pages/runtime/ScheduledRunsPage.vue`
- Create: `apps/console/src/pages/runtime/BatchRunsPage.vue`
- Test: `tests/api/test_scheduled_batch_runtime.py`
- Test: `apps/console/tests/e2e/scheduled-batch.spec.ts`

Tasks:

- [ ] Add scheduled run API with cron/interval validation, timezone, next fire time, deployment binding, input template, pause/resume, backfill policy, missed-run policy, and audit reason.
- [ ] Add batch run API with dataset/input source, concurrency, retry policy, cancel policy, progress summary, partial failure handling, and artifact/output linkage.
- [ ] Add runtime state machines for scheduled run firing, batch task expansion, cancellation, retry, dead-letter, and completion summary.
- [ ] Add Console workflows for schedule preview, next-run timeline, pause/resume, manual trigger, batch progress, failed item drilldown, and cancel confirmation.
- [ ] Add browser tests for valid schedule preview, invalid timezone, missed-run policy, batch create, progress drilldown, partial failure, and cancel.
- [ ] Commit as `feat(runtime): add scheduled and batch workflows`.

Acceptance:

- Operators can safely run periodic and batch agent workloads while preserving runtime governance, audit, cancellation, and observability.

### Phase 0O: Catalog And Versioned Asset Lifecycle Workflow

**Goal:** Make reusable platform assets discoverable and governable without becoming a prompt design platform or visual builder.

**Product stance:** Catalog, Prompt, Config, and Template are versioned control-plane assets. They support runtime governance and reuse, not business content authoring as a standalone product.

**Files:**

- Create: `apps/server/dimoo_run/api/admin/catalog.py`
- Create: `apps/server/dimoo_run/api/admin/assets.py`
- Create: `apps/server/dimoo_run/catalog/asset_lifecycle.py`
- Create: `apps/console/src/pages/catalog/CatalogPage.vue`
- Create: `apps/console/src/pages/catalog/AssetDetailPage.vue`
- Create: `apps/console/src/pages/catalog/AssetVersionDiffPage.vue`
- Test: `tests/api/test_catalog_asset_lifecycle.py`
- Test: `apps/console/tests/e2e/catalog-assets.spec.ts`

Tasks:

- [ ] Add catalog item workflow for tools, MCP endpoints, prompts, configs, templates, semantic stores, and approved runtime components.
- [ ] Add asset version lifecycle with draft, validate, approve, publish, deprecate, archive, rollback, dependency graph, and audit comparison.
- [ ] Add asset validation for schema, references, secret refs, model gateway refs, policy refs, environment scope, and compatibility with agent/deployment usage.
- [ ] Add Console asset detail with version history, diff, dependencies, used-by resources, risk flags, approval status, and rollback action.
- [ ] Add browser tests for asset create, validation failure, version diff, approve/publish, deprecate blocked by active deployment, and rollback.
- [ ] Commit as `feat(catalog): add versioned asset lifecycle workflow`.

Acceptance:

- Teams can reuse governed assets across agents and environments with validation, versioning, dependency visibility, and rollback.

### Phase 1: Production Truth Baseline

**Goal:** Stop relying on status tables and create executable proof of current behavior.

**Files:**

- Create: `docs/readiness/scorecard.md`
- Create: `scripts/compose_smoke.py`
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `docs/history/implementation-update-2026-06-01.md`

Tasks:

- [ ] Create a readiness scorecard with each DESIGN_SPEC production requirement marked `done`, `partial`, `missing`, or `deferred`.
- [ ] Add a smoke script that exercises server, worker, database, Redis, MinIO, and one real example agent.
- [ ] Add CI workflow for current passing checks: `uv run pytest`, `uv run ruff check`, `uv run mypy`, `npm run test`, `npm run build`.
- [ ] Document any known failures as explicit gaps, not as completed work.
- [ ] Commit as `docs(readiness): add production readiness baseline`.

Acceptance:

- A new contributor can run one command and see which production guarantees are proven.
- CI has at least one green path for backend and frontend unit/static verification.

### Phase 2: Production Startup Guards

**Goal:** Make production mode fail closed.

**Files:**

- Modify: `apps/server/dimoo_run/core/config.py`
- Modify: `apps/server/dimoo_run/server.py`
- Create: `apps/server/dimoo_run/core/startup_checks.py`
- Test: `tests/server/test_startup_checks.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`

Tasks:

- [x] Add `validate_production_settings(settings)` that rejects SQLite, memory runtime store, default object store credentials, dev CORS origins, missing secret provider config, and dev API key mode when `DIMOORUN_RUNTIME_MODE=production`.
- [x] Call startup validation from `create_app`.
- [x] Add tests for each rejected unsafe default.
- [x] Add documented environment variables for secure production startup.
- [ ] Commit as `fix(config): fail closed on unsafe production settings`.

Acceptance:

- `DIMOORUN_RUNTIME_MODE=production` cannot boot with local defaults.

Verification:

- `uv run pytest -q tests/server/test_config.py tests/server/test_startup_checks.py tests/api/test_platform_settings_workflows.py tests/api/test_native_api.py`
- `uv run ruff check apps/server/dimoo_run/core/config.py apps/server/dimoo_run/core/startup_checks.py apps/server/dimoo_run/platform/settings_snapshot.py apps/server/dimoo_run/server.py tests/server/test_config.py tests/server/test_startup_checks.py tests/api/test_platform_settings_workflows.py tests/api/test_native_api.py`

### Phase 3: Durable Idempotency and API Contracts

**Goal:** Make write APIs safe under retries and client timeouts.

**Files:**

- Create: `apps/server/dimoo_run/runtime/sqlalchemy_idempotency.py`
- Modify: `apps/server/dimoo_run/api/native/dependencies.py`
- Modify: `apps/server/dimoo_run/api/native/runtime.py`
- Test: `tests/runtime/test_sqlalchemy_idempotency.py`
- Test: `tests/api/test_native_api.py`

Tasks:

- [x] Implement SQLAlchemy-backed idempotency reservation and completion using `idempotency_records`.
- [x] Use it when `DIMOORUN_NATIVE_RUNTIME_STORE=sqlalchemy`.
- [x] Add tests for same key same payload replay, same key different payload conflict, and completed response replay after process restart.
- [x] Add route tests for agent task and deployment task idempotency.
- [ ] Commit as `fix(runtime): persist native idempotency records`.

Acceptance:

- Idempotency survives process restart in SQLAlchemy mode.

Verification:

- `uv run pytest -q tests/runtime/test_idempotency.py tests/runtime/test_sqlalchemy_idempotency.py tests/api/test_native_api.py tests/production_foundation/test_native_api_durable_runtime.py`
- `uv run ruff check apps/server/dimoo_run/runtime/idempotency.py apps/server/dimoo_run/runtime/sqlalchemy_idempotency.py apps/server/dimoo_run/api/native/dependencies.py apps/server/dimoo_run/api/native/runtime.py tests/runtime/test_sqlalchemy_idempotency.py tests/api/test_native_api.py`

### Phase 4: Runtime End-To-End Hardening

**Goal:** Prove multi-worker durable execution through real service boundaries.

**Files:**

- Create: `tests/e2e/test_runtime_compose_smoke.py`
- Modify: `apps/worker/dimoo_run_worker/main.py`
- Modify: `apps/server/dimoo_run/worker/loop.py`
- Modify: `apps/server/dimoo_run/worker/durable.py`
- Modify: `apps/server/dimoo_run/scheduler/sqlalchemy_backend.py`
- Test: `tests/worker/test_worker_shutdown.py`
- Test: `tests/worker/test_multi_worker_fencing.py`

Tasks:

- [x] Add worker shutdown/drain behavior.
- [x] Add multi-worker duplicate prevention tests.
- [x] Add crash recovery tests for expired lease and retry.
- [x] Add real Redis pub/sub cancel integration test.
- [x] Add worker metrics snapshot API.
- [ ] Commit as `feat(worker): harden durable multi-worker execution`.

Acceptance:

- Two workers cannot execute the same leased task.
- A killed worker leaves recoverable state.

Verification:

- `uv run pytest -q tests/worker/test_worker_shutdown.py tests/worker/test_multi_worker_fencing.py tests/worker/test_worker_loop_durable_backend.py tests/worker/test_durable_worker_execution.py tests/scheduler/test_sqlalchemy_backend.py tests/e2e/test_runtime_compose_smoke.py`
- `uv run pytest -q tests/scheduler/test_redis_backend.py -k cancel`
- `uv run pytest -q tests/api/test_worker_capacity_console.py -k "worker_snapshots_persist_across_registry_instances"`
- `uv run ruff check apps/server/dimoo_run/runtime/capacity.py apps/server/dimoo_run/scheduler/sqlalchemy_backend.py apps/server/dimoo_run/worker/loop.py apps/worker/dimoo_run_worker/main.py tests/scheduler/test_sqlalchemy_backend.py tests/worker/test_multi_worker_fencing.py tests/worker/test_worker_shutdown.py tests/e2e/test_runtime_compose_smoke.py`
- `uv run mypy apps/server tests scripts`

Notes:

- Redis cancel proof now includes both scheduler-boundary publish/subscribe coverage in `tests/scheduler/test_redis_backend.py -k cancel` and worker-loop integration coverage in `tests/worker/test_worker_loop_durable_backend.py`, where a real `RedisTaskBackend.cancel()` publish is consumed by `RedisCancelSubscriber` and forwarded through `WorkerLoop` to the cancel handler.
- Worker metrics snapshot coverage is satisfied by the existing persisted worker snapshot and capacity read-model path from Phase 0J, with the Phase 4 shutdown/drain changes now preserving those records during worker lifecycle transitions.

### Phase 5: Real Observability

**Goal:** Make production operations visible from API, Console, and standard monitoring tools.

**Files:**

- Create: `apps/server/dimoo_run/api/native/metrics.py`
- Create: `apps/server/dimoo_run/observability/otel.py`
- Modify: `apps/server/dimoo_run/api/router.py`
- Modify: `apps/server/dimoo_run/worker/executor.py`
- Modify: `apps/console/src/pages/dashboard/DashboardPage.vue`
- Modify: `apps/console/src/api/client.ts`
- Test: `tests/api/test_metrics_api.py`
- Test: `apps/console/tests/console-contract.test.mjs`

Tasks:

- [x] Add runtime metrics endpoints for machine-readable operational facts: queue depth, running tasks, worker heartbeat age, dead letters, retries, p95/p99 latency, and active incidents.
- [x] Add Prometheus metrics endpoint.
- [x] Add trace correlation fields in structured logs and runtime events.
- [x] Wire Dashboard to the Console aggregate API from Phase -1C, not to raw database fields or ad hoc frontend derivation.
- [x] Ensure Prometheus/OTel metrics and Console read models share source semantics but remain separate API contracts.
- [x] Add tests for redaction and event query filters.
- [x] Commit as `feat(observability): expose runtime metrics and traces`.

Acceptance:

- Operators can answer queue depth, active workers, failed runs, p95 latency, and dead letters from backend APIs.

Verification:

- `uv run pytest -q tests/api/test_metrics_api.py tests/api/test_console_aggregate_api.py tests/runtime/test_worker_executor.py tests/worker/test_durable_worker_execution.py tests/worker/test_worker_loop_durable_backend.py`
- `uv run pytest -q tests/api/test_native_api.py tests/api/test_worker_capacity_console.py`
- `uv run ruff check apps/server/dimoo_run/api/native/metrics.py apps/server/dimoo_run/observability/otel.py apps/server/dimoo_run/api/console/service.py apps/server/dimoo_run/api/console/schemas.py apps/server/dimoo_run/worker/executor.py apps/server/dimoo_run/api/router.py tests/api/test_metrics_api.py tests/runtime/test_worker_executor.py`
- `uv run mypy apps/server tests`
- `npm run test`
- `npm run build:e2e`

Notes:

- `apps/server/dimoo_run/api/native/metrics.py` is now the shared runtime metrics snapshot source for both `/v1/runtime/metrics/summary` and the Console runtime overview aggregation path, which keeps Prometheus-style metrics and Console read models semantically aligned without collapsing them into one API contract.
- `apps/server/dimoo_run/observability/otel.py` centralizes trace/request correlation field attachment, runtime event redaction, and Prometheus text rendering, while `apps/server/dimoo_run/worker/executor.py` now emits those correlation fields in both structured logs and replay-buffer runtime events.
- The Dashboard now reads backend-provided runtime summary and trend points instead of deriving trend slices ad hoc from recent failures on the frontend.

### Phase 6: Frontend Browser Workflow Expansion

**Goal:** Expand the existing Playwright smoke baseline into workflow-level browser confidence.

**Files:**

- Modify: `apps/console/README.md`
- Existing: `apps/console/playwright.config.ts`
- Existing: `apps/console/tests/e2e/console-smoke.spec.ts`
- Existing: `apps/console/tests/fixtures/api.ts`
- Create: `apps/console/tests/e2e/console-runtime.spec.ts`
- Create: `apps/console/tests/e2e/accessibility.spec.ts`
- Create: `apps/console/tests/e2e/responsive-snapshots.spec.ts`
- Modify: `.github/workflows/ci.yml`

Tasks:

- [x] Install and configure Playwright and axe for smoke browser testing.
- [x] Add `npm run test:e2e` and `npm run test:e2e:headed`.
- [x] Add smoke coverage for login redirect, seeded dashboard shell rendering, and critical login-page accessibility.
- [x] Add deterministic API fixture baseline in Phase -1A.
- [x] Test login, agent create, version create, deployment create, deployment task submit, run detail inspect, replay, and destructive confirmation.
- [x] Test offline, loading, empty, and API error states.
- [x] Add axe accessibility checks for key pages.
- [x] Add mobile and desktop screenshots for key workflows.
- [x] Commit as `test(console): add browser workflow coverage`.

Acceptance:

- Contract tests no longer stand alone as the only frontend proof.
- Browser tests fail if core workflows are visually or interactively broken.

Verification:

- `npm run test`
- `npm run test:unit`
- `npm run build:e2e`
- `npx playwright test --project=chrome --output test-results-phase6-final`

Notes:

- `apps/console/tests/e2e/console-runtime.spec.ts` now provides a dedicated browser proof for login, Agent registration, AgentVersion creation, Deployment creation, Deployment task submission, Run detail inspection, replay comparison, destructive confirmation, and offline/loading/empty/error state handling.
- `apps/console/tests/e2e/accessibility.spec.ts` now covers dashboard, dense table, drawer flow, high-risk confirmation, deployment task workflow, run detail diagnostics, and a mobile viewport drawer with axe critical checks.
- `apps/console/tests/e2e/responsive-snapshots.spec.ts` now captures desktop and mobile workflow screenshots as Playwright report attachments, so responsive layout evidence is produced by the same browser proof run instead of being described only in docs.
- `.github/workflows/ci.yml` now includes a dedicated Phase 6 browser workflow step and `console-playwright-6-report` artifact wiring; hosted CI proof still remains a separate readiness concern until a current successful run is recorded.

### Phase 7: Console Component Hardening

**Goal:** Replace page-local UI complexity with reusable, accessible product components.

**Files:**

- Create: `apps/console/src/components/AppDrawer.vue`
- Create: `apps/console/src/components/DataTable.vue`
- Create: `apps/console/src/components/SkeletonBlock.vue`
- Modify: `apps/console/src/pages/agents/AgentsPage.vue`
- Modify: `apps/console/src/pages/deployments/DeploymentsPage.vue`
- Modify: `apps/console/src/pages/published/PublishedSurfacesPage.vue`
- Modify: `apps/console/src/pages/admin/AdminCollectionPage.vue`
- Test: `apps/console/tests/e2e/accessibility.spec.ts`

Tasks:

- [x] Extract shared drawer with focus trap and Escape close.
- [x] Extract shared data table with keyboard row selection and responsive behavior.
- [x] Replace generic loading panels on dense pages with skeletons.
- [x] Add hard-coded copy scan and move remaining user-visible copy into i18n.
- [x] Add chart accessible summaries.
- [ ] Commit as `refactor(console): harden shared control-plane components`.

Acceptance:

- Large Console pages are easier to maintain and pass keyboard/accessibility tests.

Verification note on 2026-06-12:

- Local `apps/console` proof now includes `npm run test`, `npm run build:e2e`, and `npx playwright test tests/e2e/accessibility.spec.ts --project=chrome --output test-results-phase7-a11y`.
- The focused accessibility verifier passes 9 tests, including shared drawer Escape/focus restore and shared data-table keyboard selection coverage.

### Phase 8: Package, Adapter, and Sandbox Production Path

**Goal:** Make user agent execution safe and repeatable.

**Files:**

- Create: `apps/server/dimoo_run/packages/validation.py`
- Create: `apps/server/dimoo_run/packages/registry.py`
- Modify: `apps/server/dimoo_run/worker/durable.py`
- Modify: `apps/server/dimoo_run/worker/executor.py`
- Modify: `apps/server/dimoo_run/adapters/langchain_agent/adapter.py`
- Modify: `apps/server/dimoo_run/adapters/deepagents/adapter.py`
- Create: `examples/langchain-agent/support-agent/**`
- Create: `examples/deepagents/support-agent/**`
- Test: `tests/adapters/test_real_framework_smoke.py`
- Test: `tests/packages/test_package_validation.py`

Tasks:

- [x] Add real LangChain Agent and DeepAgents examples.
- [x] Add package validation before AgentVersion can become `ready`.
- [x] Reject unsafe local package URIs in production mode.
- [x] Resolve secrets, model gateway, tool gateway, sandbox policy, and execution profile into worker runtime config.
- [x] Add real framework smoke tests for each supported adapter.
- [x] Commit as `feat(runtime): validate production agent packages`.

Acceptance:

- A production AgentVersion cannot run without passing manifest, dependency, secret, and runtime compatibility checks.

Implemented evidence:

- `apps/server/dimoo_run/packages/registry.py` now resolves `AgentVersion` + `Deployment`
  into a runtime-safe `AgentRuntimeSpec`, enforces `ready` status plus validation token,
  rejects non-OCI package URIs outside `dev`, and materializes execution profile, model
  gateway, tool gateway, sandbox policy, container pool policy, and secret bindings.
- `apps/server/dimoo_run/worker/durable.py` now resolves runtime specs per run instead of
  using an empty shared `runtime_config={}`, and `apps/server/dimoo_run/worker/executor.py`
  now passes resolved runtime config, secret refs, and runtime metadata into execution
  context and adapter load paths.
- `examples/langchain-agent/support-agent` and `examples/deepagents/support-agent` now
  provide runnable deterministic package examples for real adapter smoke coverage.
- Local proof now includes `uv run pytest -q tests/runtime/test_worker_executor.py
  tests/adapters/test_langchain_agent_adapter.py tests/adapters/test_deepagents_adapter.py
  tests/worker/test_durable_worker_execution.py tests/packages/test_package_validation.py
  tests/adapters/test_real_framework_smoke.py`, plus targeted `uv run mypy` and `uv run
  ruff check` over the Phase 8 files.

### Phase 9: Governance Integration

**Goal:** Move governance services from boundaries into enforced runtime behavior.

**Files:**

- Modify: `apps/server/dimoo_run/secrets/provider.py`
- Modify: `apps/server/dimoo_run/model_gateway/provider.py`
- Modify: `apps/server/dimoo_run/tools/gateway.py`
- Modify: `apps/server/dimoo_run/runtime/run_manager.py`
- Modify: `apps/server/dimoo_run/worker/executor.py`
- Test: `tests/governance/test_runtime_governance_integration.py`
- Test: `tests/api/test_admin_api.py`

Tasks:

- [ ] Add persistent secret provider implementation.
- [ ] Add model gateway call wrapper with policy, telemetry, timeout, and cost tracking.
- [ ] Add tool call observation and approval enforcement.
- [ ] Persist policy decisions and approvals in audit logs.
- [ ] Add Console policy simulation and approval resume tests.
- [ ] Commit as `feat(governance): enforce runtime policy services`.

Acceptance:

- Real agent execution cannot bypass declared secret, model, tool, and approval policies.

### Phase 10: Deployment and Operations Hardening

**Goal:** Make Compose and Kubernetes deployable with production checks.

**Files:**

- Modify: `docker-compose.yml`
- Modify: `deploy/helm/dimoorun/templates/*.yaml`
- Modify: `deploy/helm/dimoorun/values.yaml`
- Create: `deploy/helm/dimoorun/templates/migration-job.yaml`
- Create: `deploy/helm/dimoorun/templates/networkpolicy.yaml`
- Create: `deploy/helm/dimoorun/templates/pdb.yaml`
- Create: `.github/workflows/integration.yml`
- Test: `tests/enterprise/test_cloud_native_manifests.py`
- Test: `scripts/helm_smoke.py`

Tasks:

- [ ] Add migration Job and startup ordering.
- [ ] Add NetworkPolicy, PodDisruptionBudget, ServiceMonitor, and resource default templates.
- [ ] Add KinD/K3d smoke script.
- [ ] Add Compose smoke to CI.
- [ ] Add backup/restore smoke against Postgres and MinIO.
- [ ] Commit as `feat(deploy): add production smoke and kubernetes guards`.

Acceptance:

- Production deploy assets are verified by executable smoke tests, not only static inspection.

### Phase 11: SDK, CLI, And Release Engineering

**Goal:** Make DimooRun scriptable, integrable, and releasable by external teams.

**Files:**

- Modify: `packages/sdk-python/dimoorun/client.py`
- Create: `packages/sdk-js/src/**`
- Modify: `apps/server/dimoo_run/cli/main.py`
- Create: `.github/workflows/release.yml`
- Create: `scripts/release_check.py`

Tasks:

- [ ] Generate or complete Python SDK coverage for stable Native APIs.
- [ ] Implement TypeScript SDK.
- [ ] Add SDK contract tests.
- [ ] Add CLI production commands for package validation, agent publish, deployment task submit, run watch, and replay.
- [ ] Add release workflow with changelog generation, image build, SBOM, vulnerability scans, provenance attestation, package publishing, and smoke verification.
- [ ] Add release check script that validates version consistency, OpenAPI generation, SDK generation, changelog entry, migration status, and required docs links.
- [ ] Commit as `feat(sdk): complete production developer workflow`.

Acceptance:

- A new user can automate the production workflow through SDK or CLI, and maintainers can cut a reproducible release with traceable artifacts.

### Phase 12A: Product Narrative Baseline

**Goal:** Give early users and contributors a truthful product entry point before the full trust/documentation suite is complete.

**Product stance:** The baseline README and docs must be accurate, modest about maturity, and aligned with the design intent. They should explain why DimooRun exists, what it does better than generic agent frameworks, what it deliberately does not do, and how to complete the first successful runtime path.

**Files:**

- Modify: `README.md`
- Create: `docs/README.md`
- Create: `docs/start/product-overview.md`
- Create: `docs/start/getting-started.md`
- Create: `docs/reference/concepts.md`
- Create: `docs/architecture/overview.md`
- Create: `docs/start/quickstart.md`
- Create: `docs/readiness/current-maturity.md`
- Create: `docs/readiness/screenshots.md`
- Create: `docs/architecture/adrs/0001-runtime-control-plane.md`
- Create: `scripts/docs_quality.py`
- Test: `tests/docs/test_docs_quality.py`

Tasks:

- [ ] Rewrite `README.md` as a product-grade entry point with positioning, first-screen value, architecture signal, quickstart, core workflows, screenshots or screenshot placeholders generated by Playwright, supported modes, current maturity, and clear "not a builder" boundaries.
- [ ] Add docs information architecture with a docs homepage, getting started path, concept guide, architecture guide, quickstart, API/SDK pointers, maturity status, and known gaps.
- [ ] Add a 15-minute quickstart that starts Compose, registers a real example agent, creates a deployment, submits a task, inspects Console, watches a run, and tears down cleanly.
- [ ] Add architecture diagrams or Mermaid diagrams for control plane, runtime plane, agent plane, worker loop, governance decision path, compatibility path, and observability path.
- [ ] Add baseline docs quality tests for required files, required sections, internal links, command blocks with declared working directory, broken image references, and forbidden unsupported claims such as "production-ready" before DoD is satisfied.
- [ ] Commit as `docs(product): add narrative baseline`.

Acceptance:

- A serious evaluator can understand the product, run the happy path, and see current maturity without reverse-engineering the repository.

### Phase 12B: Product Trust Assets, Examples, Demo, And Community

**Goal:** Make DimooRun feel like a polished, trustworthy, contributor-friendly product.

**Product stance:** Product soft power must remain accurate and testable. Trust assets should make operation, contribution, comparison, and security posture easier to evaluate without marketing claims that outpace executable proof.

**Files:**

- Create: `docs/OPERATIONS_RUNBOOK.md`
- Create: `docs/THREAT_MODEL.md`
- Create: `docs/TRUST_AND_SECURITY.md`
- Create: `docs/COMPARISONS.md`
- Create: `docs/ROADMAP.md`
- Create: `docs/FAQ.md`
- Create: `docs/DEMO_SCRIPT.md`
- Create: `examples/langgraph/support-agent/README.md`
- Create: `examples/langchain-agent/support-agent/README.md`
- Create: `examples/deepagents/support-agent/README.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/pull_request_template.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CHANGELOG.md`
- Modify: `scripts/docs_quality.py`
- Test: `tests/docs/test_docs_quality.py`

Tasks:

- [ ] Add realistic examples for LangGraph, LangChain Agent, and DeepAgents, each with manifest, expected commands, expected Console result, troubleshooting, and production caveats.
- [ ] Add trust assets: threat model, trust/security overview, security reporting policy, dependency/security scanning expectations, data retention model, secret handling model, audit model, and production safety defaults.
- [ ] Add community and contributor assets: contribution guide, issue templates, PR template, coding standards, test expectations, release process, changelog policy, and roadmap boundaries.
- [ ] Add product comparison material that explains DimooRun versus plain LangGraph app, LangGraph Platform-style compatibility, generic workflow engines, and model gateways without making unverifiable marketing claims.
- [ ] Add demo script for maintainers to record or present the product: setup, agent publish, deployment promote, run inspect, replay, policy approval, gateway route test, incident triage, and cost drilldown.
- [ ] Extend docs quality tests for stale maturity wording, comparison claim evidence, missing security policy links, missing changelog entries, and missing demo prerequisites.
- [ ] Commit as `docs(product): add trust assets and examples`.

Acceptance:

- A serious evaluator can inspect realistic examples, trust the security posture, compare alternatives, and contribute or report issues without reverse-engineering the repository.

---

## 10. Release Milestones

Use milestones to keep the 30-plus phases executable. A milestone can ship only when its exit criteria are met; later phases should not be used to excuse missing proof in earlier milestones.

### Milestone A: Internal Alpha

**Goal:** Prove the product has a truthful baseline and one complete local runtime path.

Required phases:

- Phase -3: User Task And Experience Baseline
- Phase -2: Product Workflow Spec Reconciliation
- Phase -1A: Frontend Test Harness Baseline
- Phase -1B: Frontend State Architecture Baseline
- Phase -1C: Console Aggregate And Permission API Contract
- Phase 1: Production Truth Baseline
- Phase 12A: Product Narrative Baseline

Exit criteria:

- [ ] Current readiness scorecard exists and does not claim missing work as complete.
- [ ] CI has a green backend/frontend baseline.
- [ ] Compose smoke is specified, even if it initially documents failures.
- [ ] README and quickstart describe the real maturity status.
- [ ] Browser smoke and critical accessibility baseline pass.

### Milestone B: Production Beta

**Goal:** Make the core runtime, deployment, governance, and operations paths safe enough for controlled production pilots.

Required phases:

- Phase 0A through Phase 0G
- Phase 2: Production Startup Guards
- Phase 3: Durable Idempotency and API Contracts
- Phase 4: Runtime End-To-End Hardening
- Phase 5: Real Observability
- Phase 6: Frontend Browser Workflow Expansion
- Phase 8: Package, Adapter, and Sandbox Production Path
- Phase 9: Governance Integration

Exit criteria:

- [ ] Production mode fails closed for unsafe defaults.
- [ ] A real agent package can be registered, validated, deployed, invoked, inspected, replayed, and governed.
- [ ] Worker crash, retry, cancellation, dead-letter, and duplicate-prevention paths are proven end-to-end.
- [ ] Core Console workflows have browser tests for success, loading, empty, API error, permission denial, and destructive confirmation.

### Milestone C: External GA

**Goal:** Make the product usable by external teams with governed exposure, migration, capacity, identity, settings, release, and docs.

Required phases:

- Phase 0H through Phase 0O
- Phase 7: Console Component Hardening
- Phase 10: Deployment and Operations Hardening
- Phase 11: SDK, CLI, And Release Engineering
- Phase 12B: Product Trust Assets, Examples, Demo, And Community

Exit criteria:

- [ ] Published surfaces, compatibility, capacity, identity, settings, cost, scheduled/batch, and catalog workflows have typed APIs, Console workflows, audit behavior, and browser evidence.
- [ ] Docker Compose smoke passes from a clean checkout.
- [ ] Kubernetes smoke passes in an ephemeral cluster.
- [ ] SDK, CLI, README, quickstart, examples, trust docs, and release workflow are coherent and versioned.

### Milestone D: Competitive Excellence

**Goal:** Move from feature completeness to strong product differentiation.

Required work:

- [ ] Prioritize and implement P0/P1 items from `docs/product/optimization-backlog.md`.
- [ ] Add guided activation, runtime workbench, action center, resource graph, evidence bundles, feedback capture, and integration health center.
- [ ] Use product telemetry and browser evidence to remove the most common activation and recovery friction.

Exit criteria:

- [ ] A new evaluator can reach first successful run without private assistance.
- [ ] Operators can diagnose and recover the top production failure modes from Console.
- [ ] Product comparison material is backed by executable proof, not unsupported claims.

### Stop-The-Line Criteria

Pause new feature phases and fix the blocking issue first when any of these happen:

- [ ] Production mode can boot with unsafe defaults that should be rejected.
- [ ] Compose smoke cannot start the core server, worker, console, Postgres, Redis, and object store path.
- [ ] A declared stable API has an undeclared OpenAPI breaking change.
- [ ] Core browser smoke fails on login, scope selection, dashboard shell, or critical accessibility checks.
- [ ] Worker duplicate execution, crash recovery, cancellation, or dead-letter tests regress.
- [ ] A high-risk action can execute without permission summary, policy decision, audit record, or confirmation where required.
- [ ] README, quickstart, CLI help, SDK example, or Console screenshot claims a capability that the readiness scorecard marks missing.

---

## 11. Recommended Implementation Order

Do not start with deployment polish or generic visual polish. The highest risk is false product completeness: many menus and APIs exist, but several workflows are not yet production-usable. Use this order, aligned to the release milestones:

1. Phase -3: user task and experience baseline.
2. Phase -2: product workflow coverage matrix.
3. Phase -1A: frontend test harness baseline.
4. Phase -1B: frontend state architecture baseline.
5. Phase -1C: Console aggregate and permission API contract.
6. Phase 1: production truth baseline and CI.
7. Phase 12A: product narrative baseline.
8. Phase 0A: agent package and version readiness workflow.
9. Phase 0B: deployment promotion and rollback workflow.
10. Phase 0C: run triage and replay comparison workflow.
11. Phase 0D: policy and human approval workbench.
12. Phase 0E: gateway, tool, and secret governance workflow.
13. Phase 0F: quality, dataset, and experiment workflow.
14. Phase 0G: incident, notification, backup, and restore workflow.
15. Phase 2: production startup guards.
16. Phase 3: durable idempotency.
17. Phase 4: worker/runtime E2E hardening.
18. Phase 5: observability metrics and traces.
19. Phase 6: frontend browser workflow expansion.
20. Phase 8: package/adapter/sandbox production path.
21. Phase 9: governance integration.
22. Phase 7: Console component hardening.
23. Phase 0H: published surface, ingress, and Agent Gateway workflow.
24. Phase 0I: compatibility migration and runtime explorer workflow.
25. Phase 0J: worker, agent instance, and capacity operations workflow.
26. Phase 0K: identity, role, permission, session, and machine identity workflow.
27. Phase 0L: platform settings, providers, and dangerous configuration workflow.
28. Phase 0M: cost, budget, and usage attribution workflow.
29. Phase 0N: scheduled and batch runtime workflow.
30. Phase 0O: catalog and versioned asset lifecycle workflow.
31. Phase 10: deployment and operations hardening.
32. Phase 11: SDK, CLI, and release engineering.
33. Phase 12B: product trust assets, examples, demo, and community.

Rationale:

- First define who the Console serves, what jobs they need to complete, what decisions they make, and how they recover from failure.
- Then define what "feature complete" actually means at workflow level.
- Then put deterministic browser/unit testing and shared frontend state primitives in place so workflow work is testable from the first commit.
- Then add Console aggregate read models and permission summaries so pages do not reconstruct product meaning from raw records.
- Then establish production truth and a truthful product narrative before large product expansion.
- Then build product workflows in small, independently testable slices that replace generic admin CRUD for high-value domains.
- Then fail closed in production, protect runtime correctness, add observability, and expand browser coverage before advanced GA product surfaces.
- Then harden shared Console components so advanced surfaces reuse a consistent product vocabulary.
- Then add competitive control-plane workflows: governed external ingress, migration explorer, capacity operations, access governance, platform settings, cost attribution, scheduled/batch runtime, and versioned assets.
- Then complete deployment, SDK, release, trust assets, examples, and community maturity.
- Then polish product soft power so README, docs, examples, demos, trust material, contribution flow, and release narrative match the quality of the runtime.

---

## 12. Definition of Done For This Plan

This plan is complete only when:

- [ ] All phases have passing tests in CI.
- [ ] Milestone A, B, C, and D have explicit exit status in `docs/readiness/scorecard.md`.
- [ ] Every core workflow maps to a named user role, job, decision, risk, success feedback, and failure recovery path.
- [ ] At least three user-role walkthroughs are recorded for guided activation, deployment promotion, failed-run triage, approval decision, and incident recovery; each walkthrough produces a friction log and follow-up backlog items.
- [ ] Generic CRUD coverage is no longer counted as complete unless a workflow has domain validation, action availability, audit behavior, and browser coverage.
- [ ] Product function coverage review exists and is kept current for all major product areas, including lifecycle, runtime, governance, exposure, compatibility, operations, identity, quality, cost, assets, settings, developer experience, and soft power.
- [ ] Product optimization backlog exists, is prioritized, and maps each enhancement to user value, design guardrail, implementation phase, read model, Console workflow, and browser evidence.
- [ ] Product optimization backlog has exit rules that remove or defer items not tied to runtime control, operational trust, migration confidence, governance, quality, or developer activation.
- [ ] Product telemetry is tenant/project-scoped, redacted by default, retention-bound, configurable or disableable, and documented in trust/security materials without collecting secret or prompt payloads.
- [ ] Collaboration notes are evidence-bound to runtime, deployment, approval, replay, or incident records and do not introduce project management, kanban, task assignment, SLA ticket routing, or ITSM replacement scope.
- [ ] Console pages use aggregate read models and backend-derived action summaries for high-value workflows.
- [ ] Published Surface, Ingress, and Agent Gateway can be validated, tested, exposed, monitored, rolled back, and revoked through governed workflows.
- [ ] Compatibility workflows let LangGraph and Agent Protocol users run, inspect, migrate, and understand semantic gaps without bypassing native governance.
- [ ] Workers, agent instances, queues, capacity, drain, and quarantine are visible and actionable from Console with audit and permission checks.
- [ ] Identity workflows cover role matrix, effective permissions, user lifecycle, service accounts, API key rotation, session revocation, and self-lockout prevention.
- [ ] Platform Settings separates personal preferences from environment/provider/runtime configuration and blocks dangerous changes without preflight, explicit confirmation, and audit reason.
- [ ] Cost and budget workflows explain usage by agent, deployment, run, provider, tenant, project, and environment, with anomaly and budget guardrails.
- [ ] Scheduled Run and Batch Run are first-class runtime task shapes with validation, state machines, cancellation, replay, audit, and browser coverage.
- [ ] Catalog, Prompt, Config, and Template assets have version lifecycle, validation, dependency visibility, approval, rollback, and used-by impact.
- [ ] Docker Compose smoke passes from a clean checkout.
- [ ] Kubernetes smoke passes in an ephemeral cluster.
- [ ] Browser E2E tests cover core Console workflows.
- [ ] Playwright covers at least these workflow groups: login/scope, agent/version, deployment/task, run detail, replay, policy/approval, gateway route test, worker capacity, identity, settings, cost, scheduled/batch, catalog asset, incident/recovery, and docs screenshot generation.
- [ ] Critical axe accessibility violations are zero on login, dashboard, one dense table, one drawer/dialog, one high-risk confirmation, and one mobile viewport.
- [ ] Desktop and mobile screenshots exist for the dashboard, agent detail, deployment workflow, run workbench, gateway route tester, approval queue, settings danger zone, and docs quickstart path.
- [ ] Production mode rejects unsafe defaults.
- [ ] Production startup guard tests cover SQLite, in-memory runtime store, default object store credentials, permissive CORS, missing secret provider, dev API key mode, and missing production secret.
- [ ] Runtime duplicate execution, retry, dead-letter, cancel, crash recovery, and replay are proven end-to-end.
- [ ] Observability includes metrics, traces, events, audit, and artifacts with redaction.
- [ ] OpenAPI diff has no undeclared breaking changes, and generated SDK contract tests pass for Python and TypeScript.
- [ ] Every high-risk action has a backend-derived disabled-action reason, permission summary, policy decision, audit record, and browser test for blocked and successful paths.
- [ ] SDKs and CLI can drive the production workflow.
- [ ] The README clearly explains positioning, core value, architecture, quickstart, screenshots, maturity status, and product boundaries without unsupported claims.
- [ ] Docs include product overview, getting started, concepts, architecture, quickstart, operations runbook, threat model, trust/security, comparisons, roadmap, FAQ, screenshots, demo script, ADRs, and readiness scorecard.
- [ ] README, quickstart, CLI help, SDK examples, OpenAPI docs, Console screenshots, and readiness scorecard describe the same supported workflows, command names, environment variables, maturity status, and known gaps.
- [ ] Examples are realistic, runnable, documented, and mapped to Console outcomes for LangGraph, LangChain Agent, and DeepAgents.
- [ ] Community and maintainer assets include contribution guide, security policy, issue templates, PR template, changelog, release process, and docs quality checks.
- [ ] Release workflow builds, scans, signs or attests, and publishes artifacts.

---

## 13. Short Answer: Is It Far From Perfect Production Grade?

Not far in architecture. The design is ambitious and the repository already has many right boundaries.

Still far in product completeness, frontend experience, frontend logic, proof, hardening, and operational maturity. A production-grade platform is not just code paths, database tables, generic CRUD pages, and tests around individual services. It needs domain workflows that users can complete safely, backend services that enforce real product semantics, a Console that guides operators through high-risk actions, executable confidence under real deployment conditions, safe defaults, browser-proven workflows, runtime failure recovery, observability, security, and release discipline.

The current project is best described as:

```text
Production-shaped foundation: yes
Production-ready for controlled internal alpha: plausible for core runtime paths, not for the full product surface
Production-grade for external customers: not yet
Perfect production-grade platform: still several hardening phases away
```

More specifically:

```text
Backend core runtime: partially strong
Backend product semantics: incomplete
Frontend route/API coverage: broad
Frontend task experience: incomplete
Frontend state architecture: fragile at current scale
Deployment/ops proof: incomplete
```
