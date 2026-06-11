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
- Durable runtime and worker hardening foundations.
- Durable native idempotency now persists through `idempotency_records` in SQLAlchemy mode and replays completed task creation after runtime restart.
- Governance, audit, service account, policy, tool/model/secret boundaries.
- Production startup guards now fail closed on SQLite, in-memory runtime store, dev CORS origins, default object-store credentials, missing secret provider config, and dev API key mode.
- Console route and API coverage for many product areas.
- Docker, Helm, OpenAPI, CLI, and SDK foundations.

## Known Gaps

- Many Console pages remain partial product workflows rather than complete operator tools.
- Browser evidence is broadening but does not yet cover every workflow acceptance path.
- Clean-machine Compose and ephemeral Kubernetes smoke proof are not complete.
- SDKs, release workflow, trust/security docs, examples, and screenshots are incomplete.
- Cost, budget, scheduled/batch, catalog, and some gateway/runtime hardening
  workflows are not complete yet.

## Claim Policy

Do not claim DimooRun is production-ready or externally GA-ready until the gap closure plan definition of done is satisfied and the scorecard proves it.

