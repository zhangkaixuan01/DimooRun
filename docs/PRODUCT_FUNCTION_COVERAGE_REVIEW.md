# Product Function Coverage Review

This review summarizes product-level coverage by user-visible capability area. It complements `docs/PRODUCT_WORKFLOW_COVERAGE_MATRIX.md`; the matrix is the row-level source of truth, while this document explains product gaps and judgment.

## Verdict

DimooRun has broad route, model, and Console surface coverage, but most product areas remain `partial` because many workflows still depend on generic collection CRUD or page-local logic. The project is production-shaped, but not yet production-grade for external users.

| Product area | Coverage verdict | Current strength | Perfect-level gap |
|---|---|---|---|
| Agent lifecycle | partial | Agent/version/deployment surfaces and native APIs exist. | Guided path from package import to validated version, deployment, task, evidence, and promotion blocker resolution. |
| Runtime execution | partial | Runs, tasks, attempts, events, worker execution, and run detail exist. | Unified runtime workbench with live timeline, artifacts, traces, retry/replay, policy, cost, and recovery actions. |
| Debug and replay | partial | Replay service/page and run evidence exist. | Reproducible replay bundles, baseline/candidate diff, regression classification, dataset capture, and shareable evidence. |
| Governance | partial | Policies, human tasks, audit, permissions, service accounts, tools, model gateways, and secrets exist as surfaces. | One action-risk model with policy simulation, impact preview, decision provenance, and backend-derived action summary everywhere. |
| External exposure | partial | Published surfaces and ingress routes exist. | Governed publishing workflow with traffic, auth validation, route test, request logs, abuse signals, rollback, and revocation. |
| Compatibility | partial | Compatibility page/API and migration modules exist. | Explorer, stream tester, migration score, unsupported capability inventory, native-resource mapping, and golden compatibility tests. |
| Operations | partial | Incidents, alerts, notifications, backup/restore, workers, and deployment health concepts exist. | Command center for queue pressure, worker health, incidents, approvals, backup status, drain/quarantine, and recommended actions. |
| Identity | partial | Operators, scopes, roles, permissions, service accounts, and API keys exist. | Effective permission explorer, self-lockout prevention across role changes, service-account used-by graph, key/session rotation workflows. |
| Quality | partial | Datasets, experiments, evaluations, feedback, and replay concepts exist. | Closed loop from production run to dataset to experiment to promotion gate and rollout decision. |
| Cost | missing | No first-class cost workflow found. | Cost per agent/deployment/run/provider with budgets, anomalies, quality/failure overlays, and deployment-change correlation. |
| Catalog and assets | partial | Catalog, prompt/config/template assets, tools, sandbox, and container policy surfaces exist. | Version lifecycle, diff, dependency graph, validation, approval, publish, deprecate, rollback, and used-by impact. |
| Platform settings | partial | Personal settings and generic settings resources exist. | Environment/provider/runtime settings, integration health, preflight, read-only production mode, and audited dangerous changes. |
| Developer experience | partial | README, examples, native API, SDK package, OpenAPI, and CLI foundations exist. | One first-run success path through CLI, API, Console, SDK, and docs with consistent names and commands. |
| Product soft power | partial | Design spec and implementation notes exist. | Product-grade docs, screenshots, trust/security, runbooks, comparisons, roadmap, demo script, contribution assets, and release notes. |

## Product Risks

| Risk | Evidence | Required correction |
|---|---|---|
| Menu coverage can be mistaken for workflow completeness. | Many important surfaces route to `AdminCollectionPage`. | Keep generic CRUD marked `partial` until domain workflows exist. |
| High-risk actions can lack enough decision context. | Policies, model gateways, secrets, tools, backup/restore, and settings are not fully domain-specific. | Add impact preview, permission summary, policy decision, audit reason, and rollback/recovery path. |
| Operators must assemble evidence across pages. | Runs, events, artifacts, audit logs, replay jobs, incidents, and worker state are separate. | Build runtime workbench and action center read models. |
| Frontend workflow confidence is too narrow. | Browser harness currently proves shell/login/accessibility only. | Expand Playwright by workflow group with success, loading, empty, error, permission, destructive confirmation, and responsive evidence. |
| Production claims can outpace proof. | Readiness scorecard and docs quality gates are not yet present. | Add readiness scorecard, docs claim guardrails, and executable smoke tests. |

## Required Updates By Milestone

| Milestone | Product function expectation |
|---|---|
| Internal Alpha | User task model, workflow coverage matrix, frontend harness, readiness scorecard, truthful README/quickstart, and one local runtime path. |
| Production Beta | Core runtime, deployment, governance, operations, package validation, production startup guards, idempotency, worker failure paths, and browser workflow confidence. |
| External GA | Published surfaces, compatibility, capacity, identity, settings, cost, scheduled/batch, catalog/assets, deployment smoke, SDK/CLI, and trust assets. |
| Competitive Excellence | Guided activation, runtime workbench, action center, resource graph, evidence bundles, feedback capture, integration health, and product telemetry used to reduce friction. |

## Review Maintenance Rule

Update this review whenever a workflow moves from `missing` to `partial`, from `partial` to `complete`, or when a new route/page/API could make the product look more complete than it is. Product function status must match executable evidence, not implementation intent.
