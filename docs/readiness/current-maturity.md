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
- Governance, audit, service account, policy, tool/model/secret boundaries.
- Console route and API coverage for many product areas.
- Docker, Helm, OpenAPI, CLI, and SDK foundations.

## Known Gaps

- Many Console pages remain partial product workflows rather than complete operator tools.
- Browser evidence is broadening but does not yet cover every workflow acceptance path.
- Clean-machine Compose and ephemeral Kubernetes smoke proof are not complete.
- Production mode fail-closed checks and unsafe default rejection need stronger executable proof.
- SDKs, release workflow, trust/security docs, examples, and screenshots are incomplete.
- Cost, budget, settings, scheduled/batch, catalog, capacity, gateway, and compatibility workflows are not complete.

## Claim Policy

Do not claim DimooRun is production-ready or externally GA-ready until the gap closure plan definition of done is satisfied and the scorecard proves it.

