# Current Maturity

## Current Status

DimooRun is a production-shaped foundation. It has meaningful backend runtime,
deployment, governance, identity, observability, worker, Docker, Helm, SDK,
CLI, and Console foundations.

It is not yet an externally production-grade platform. Product workflows,
hardening proof, browser evidence, production defaults, smoke environments,
hosted trust verification, release engineering, and SDK compatibility still
need work.

Use the same shorthand as the readiness scorecard:

```text
Production-shaped foundation: yes.
External production-grade platform: not yet.
```

Authoritative status:

- [Production Readiness Scorecard](scorecard.md)
- [Product Documentation](../product/README.md)
- [Repository README](../../README.md)

## What You Can Evaluate Today

- the local Compose runtime path
- real agent publish, deploy, and task submission through API/SDK
- Console inspection of deployments, runs, tasks, approvals, and admin surfaces
- control-plane and runtime-plane architecture shape

## What Is Strong

- Adapter-first architecture around LangGraph, LangChain Agent, and DeepAgents.
- Native runtime API and task/run concepts.
- Durable runtime and worker hardening foundations, including verified graceful worker shutdown, multi-worker lease fencing, expired-lease recovery, Redis cancel pub/sub coverage, and persisted worker snapshots.
- Runtime observability now exposes queue depth, running tasks, worker heartbeat age, dead letters, retries, runtime latency percentiles, active incidents, Prometheus scrape output, and trace/request correlation fields through shared backend semantics.
- Durable native idempotency now persists through `idempotency_records` in SQLAlchemy mode and replays completed task creation after runtime restart.
- Production-path package execution now enforces validated `ready` agent versions at worker runtime, rejects unsafe local/file package URIs outside `dev`, and resolves execution profile, sandbox, model gateway, tool gateway, container pool, and secret-ref bindings into runtime config before adapter load.
- Governance now reaches the durable worker path: runtime execution can consume injected secret, model gateway, and tool governance services that enforce DB-backed policy, write audit logs, persist model usage, and create approval-backed human tasks.
- Production startup guards now fail closed on SQLite, in-memory runtime store, dev CORS origins, default object-store credentials, missing secret provider config, dev API key mode, and missing or default bootstrap admin passwords.
- Deployment assets now include startup-ordered Compose migration flow, backup/restore runtime smoke, and Helm production guards for migration hooks, NetworkPolicy, PodDisruptionBudget, ServiceMonitor, and resource defaults, with a dedicated hosted integration workflow contract.
- Console route and API coverage for many product areas, now backed by a 58-test local browser suite that covers workflow interactions, critical accessibility checks, and responsive screenshot evidence.
- Shared Console control-plane primitives now centralize drawers, dense tables, skeleton loading states, and runtime chart accessibility semantics across the largest operator pages.
- Docker, Helm, OpenAPI, SDK, CLI, and release-contract foundations now cover package validation, publish, deployment task submission, run replay/watch, and reproducible release checks.
- The production CLI path now also covers deployment creation and `doctor production`, so release-oriented operator workflows can be preflighted and scripted without reaching into page-local Console flows.

## Known Gaps

- Many Console pages remain partial product workflows rather than complete operator tools.
- Hosted/default-browser proof is still incomplete even though the local browser suite now covers 58 workflow, accessibility, and responsive tests plus a focused 9-test Phase 7 accessibility verifier.
- Clean-machine Compose and ephemeral Kubernetes smoke proof are not complete, even though the stronger runtime and Helm smoke scripts plus hosted diagnostics contracts are now in place.
- Local exporter validation proof exists; hosted monitoring-stack verification remains incomplete.
- Hosted package publishing proof, release attestation evidence, generated
  screenshots, and externally hosted trust verification are incomplete.
- Cost and budget workflows now have backend attribution, Console
  explorer/budget-preview pages, persisted budget policy CRUD/preview,
  persisted saved cost views with Console reapply flows, deployment-task
  runtime enforcement for persisted `reject` and `require_approval` policies,
  operator-visible delivery-attempt recording for triggered policies,
  deployment quality overlays inside the cost explorer, and local browser
  proof, but hosted/default-browser evidence is still not complete.
- Scheduled/batch runtime now has first-class backend APIs, dedicated Console
  pages, and local browser proof through both the direct spec and
  `npm run test:e2e:0n` wrapper for schedule preview/pause-resume-trigger
  plus batch partial-failure/retrying/cancel-summary flows. The backend now
  also proves due schedule firing for `skip`, `run_once`, and `catch_up`
  policies plus batch retry/dead-letter/completion summary recomputation from
  durable task state. Hosted/default-browser evidence is still incomplete.
- Catalog asset lifecycle now has backend lifecycle APIs, dedicated Console
  list/detail/diff pages, targeted backend tests, and local browser proof
  through both the direct `catalog-assets.spec.ts` flow and the dedicated
  `npm run test:e2e:0o` wrapper, which now covers prompt lifecycle actions
  plus catalog shapes for `mcp_endpoint`, `semantic_store`, and
  `runtime_component`. Hosted/default-browser evidence is still incomplete.

## Claim Policy

Do not claim DimooRun is production-ready or externally GA-ready until the gap
closure plan definition of done is satisfied and the scorecard proves it.


