# Current Maturity

## Current Status

DimooRun is a production-shaped foundation. It has meaningful backend runtime, deployment, governance, identity, observability, worker, Docker, Helm, SDK, CLI, and Console foundations.

It is not yet an externally production-grade platform. Product workflows, hardening proof, browser evidence, production defaults, smoke environments, trust assets, release engineering, and SDK compatibility still need work.

Authoritative status:

- [Production Readiness Scorecard](scorecard.md)
- [Product Function Coverage Review](../product/function-coverage-review.md)
- [Product Workflow Coverage Matrix](../product/workflow-coverage-matrix.md)

## What Is Strong

- Adapter-first architecture around LangGraph, LangChain Agent, and DeepAgents.
- Native runtime API and task/run concepts.
- Durable runtime and worker hardening foundations, including verified graceful worker shutdown, multi-worker lease fencing, expired-lease recovery, Redis cancel pub/sub coverage, and persisted worker snapshots.
- Runtime observability now exposes queue depth, running tasks, worker heartbeat age, dead letters, retries, runtime latency percentiles, active incidents, Prometheus scrape output, and trace/request correlation fields through shared backend semantics.
- Durable native idempotency now persists through `idempotency_records` in SQLAlchemy mode and replays completed task creation after runtime restart.
- Production-path package execution now enforces validated `ready` agent versions at worker runtime, rejects unsafe local/file package URIs outside `dev`, and resolves execution profile, sandbox, model gateway, tool gateway, container pool, and secret-ref bindings into runtime config before adapter load.
- Governance now reaches the durable worker path: runtime execution can consume injected secret, model gateway, and tool governance services that enforce DB-backed policy, write audit logs, persist model usage, and create approval-backed human tasks.
- Production startup guards now fail closed on SQLite, in-memory runtime store, dev CORS origins, default object-store credentials, missing secret provider config, and dev API key mode.
- Deployment assets now include startup-ordered Compose migration flow, backup/restore runtime smoke, and Helm production guards for migration hooks, NetworkPolicy, PodDisruptionBudget, ServiceMonitor, and resource defaults, with a dedicated hosted integration workflow contract.
- Console route and API coverage for many product areas, now backed by a 58-test local browser suite that covers workflow interactions, critical accessibility checks, and responsive screenshot evidence.
- Shared Console control-plane primitives now centralize drawers, dense tables, skeleton loading states, and runtime chart accessibility semantics across the largest operator pages.
- Docker, Helm, OpenAPI, SDK, CLI, and release-contract foundations now cover package validation, publish, deployment task submission, run replay/watch, and reproducible release checks.

## Known Gaps

- Many Console pages remain partial product workflows rather than complete operator tools.
- Hosted/default-browser proof is still incomplete even though the local browser suite now covers 58 workflow, accessibility, and responsive tests plus a focused 9-test Phase 7 accessibility verifier.
- Clean-machine Compose and ephemeral Kubernetes smoke proof are not complete, even though the runtime and Helm smoke scripts plus `integration.yml` contract are now in place.
- Hosted Prometheus/OTel exporter proof and live monitoring-stack verification are not complete yet, even though the Phase 5 observability API and Console surfaces are now implemented and locally verified.
- OCI package retrieval and live production package execution proof are not complete yet, even though the runtime now blocks unsafe package paths, validates runtime bindings before worker execution, and injects enforced governance services into the durable worker path.
- Hosted package publishing proof, release attestation evidence, trust/security docs, examples, and screenshots are incomplete.
- Cost, budget, scheduled/batch, catalog, and some gateway/runtime hardening
  workflows are not complete yet.

## Claim Policy

Do not claim DimooRun is production-ready or externally GA-ready until the gap closure plan definition of done is satisfied and the scorecard proves it.

