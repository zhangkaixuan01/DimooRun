# DimooRun

DimooRun is an adapter-first runtime control plane for teams that already have
agent code and need a safer way to ship, operate, and inspect it.

It is built for the gap between "the agent works on my laptop" and "we can run,
govern, replay, and explain this in a real environment."

## Why Teams Use DimooRun

- Bring LangGraph, LangChain Agent, or DeepAgents code instead of rewriting
  business logic into a new platform.
- Publish versions, create deployments, and submit work through a runtime API
  and control plane instead of ad-hoc scripts.
- Inspect runs, attempts, events, artifacts, approvals, and audit evidence when
  something fails or needs review.
- Keep governance, model/tool/secret controls, and compatibility surfaces in
  the runtime layer instead of pushing them into app code.

Core boundary:

```text
Business logic is a black box.
Runtime behavior is a white box.
```

## First 10 Minutes

The fastest real path today is:

1. Start the local Compose stack.
2. Publish the `examples/langgraph/support-agent` example with productized CLI.
3. Deploy the ready version to `local`.
4. Submit a task and inspect the run evidence in Console.
5. Tear the stack down cleanly.

Working directory: repository root.

```bash
cp .env.example .env
docker compose up --build
```

Working directory: repository root.

```bash
uv run dimoorun publish examples/langgraph/support-agent
uv run dimoorun deploy support-agent --env local
uv run dimoorun run support-agent --env local --input-json "{\"message\":\"customer refund request for order 42\"}" --watch --show-events
uv run dimoorun open --run-id <RUN_ID>
```

Working directory: repository root.

```bash
uv run dimoorun run watch --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --run-id <RUN_ID> --show-events
```

For a single command that prepares demo data, use:

```bash
uv run dimoorun demo seed --watch
```

Working directory: repository root.

```bash
docker compose down --remove-orphans --volumes
```

The full evaluator walkthrough, Console checkpoints, and expected results are in
[docs/start/quickstart.md](docs/start/quickstart.md).

## Core Workflows

- Agent package validation, version registration, and readiness checks
- Deployment activation, pause, resume, drain, restart, and rollback
- Task submission, run inspection, retry, replay, and failure triage
- Human approval, policy enforcement, model/tool/secret governance
- Runtime evidence review across events, artifacts, traces, and audit records

## Architecture Signal

DimooRun keeps separate product planes so runtime control does not leak into
agent business logic:

```mermaid
flowchart LR
    Console[Console] --> Control[Control Plane API]
    Control --> Runtime[Runtime Plane]
    Runtime --> Worker[Worker Loop]
    Worker --> Agent[Agent Adapter]
    Control --> Governance[Policy and Identity]
    Runtime --> Evidence[Events Artifacts Replay]
```

More detailed diagrams for control plane, runtime plane, worker loop,
governance, compatibility, and observability live in
[docs/architecture/overview.md](docs/architecture/overview.md).

## Screenshot Evidence

Generated product evidence is indexed in
[docs/readiness/evidence-gallery.md](docs/readiness/evidence-gallery.md).
Hosted/public screenshots are still incomplete unless the gallery row links to a
current artifact.

- Readiness status: [docs/readiness/scorecard.md](docs/readiness/scorecard.md).

## Supported Modes

- Native runtime APIs for agents, versions, deployments, tasks, runs, replay,
  metrics, governance, and admin surfaces
- Console operator workflow for deployments, runs, tasks, approvals, settings,
  identity, observability, and enterprise ops
- CLI workflow for package validation, agent publish, deployment task submit,
  replay, and run watch
- Python and TypeScript SDK surfaces for the same runtime path
- Compatibility path for LangGraph ecosystem-style integration without bypassing
  native governance

## Current Maturity

DimooRun has a production-shaped foundation, not a completed production-grade
product.

Use the same shorthand as the readiness scorecard:

```text
Production-shaped foundation: yes.
External production-grade platform: not yet.
```

- Strong today: adapter-first runtime model, durable worker/task foundations,
  deployment control, policy/governance surfaces, runtime observability, Console
  live backend, CLI/SDK workflow, Compose/Helm assets, and local proof for cost,
  scheduled/batch, and catalog workflows.
- Still incomplete: broad screenshot evidence, clean hosted smoke proof, some
  operator workflows, release proof, and externally hosted trust verification.

Use these before making any maturity claim:

- [Current Maturity](docs/readiness/current-maturity.md)
- [Production Readiness Scorecard](docs/readiness/scorecard.md)
- [Docs Home](docs/README.md)

## What DimooRun Is Not

DimooRun is not:

- a low-code agent builder
- a drag-and-drop workflow canvas
- a prompt IDE
- a business app generator
- a replacement for your agent framework
- a guarantee that arbitrary agent code becomes safe to ship to production once
  it is imported

## Documentation Map

- [Docs Home](docs/README.md)
- [Product Overview](docs/start/product-overview.md)
- [Getting Started](docs/start/getting-started.md)
- [Quickstart](docs/start/quickstart.md)
- [Concepts](docs/reference/concepts.md)
- [Architecture Overview](docs/architecture/overview.md)

## Local Verification

Working directory: repository root.

```bash
uv run pytest -q
uv run ruff check apps tests packages/sdk-python scripts migrations
uv run mypy apps/server tests packages/sdk-python scripts
```
