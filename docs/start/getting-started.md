# Getting Started

This guide explains the intended first successful runtime path. The goal is not
to prove external production readiness; it is to get one real agent through the
publish, deploy, submit, inspect cycle with honest caveats.

## Prerequisites

- Python 3.11 or newer.
- Node.js 20 or newer.
- uv.
- Docker with Compose for the full local stack.
- A shell started at the repository root.

Working directory:

```text
D:\codes\DimooRun
```

## First Runtime Path

The intended evaluator path is:

1. Start the server, worker, Console, Postgres, Redis, and object store.
2. Sign in to the Console with the local operator account.
3. Register an example agent package.
4. Validate the package version.
5. Create or promote a deployment.
6. Submit a task.
7. Inspect the run, attempts, events, artifacts, and audit evidence.
8. Try replay or failure triage if the run fails.

This path is the product activation target. It is not yet fully proven by clean-machine Compose evidence.

## Evaluation Checkpoints

After the happy path, verify these before moving on:

- the deployment is visible in Console
- the run reaches a terminal state
- events and attempt data are readable
- the agent version and deployment IDs are visible in run detail
- current caveats in [Current Maturity](../readiness/current-maturity.md) still match what you observed

## Local Development Path

Working directory: repository root.

```bash
uv run uvicorn dimoo_run.server:app --reload --host 127.0.0.1 --port 8000
```

Working directory: `apps/console`.

```bash
npm run dev
```

## Full Stack Path

Working directory: repository root.

```bash
docker compose up --build
```

Use this path for the product happy path once Compose smoke evidence is attached to the readiness scorecard.

## API And SDK Path

If you want scriptable evaluation instead of manual API calls, use:

- Python SDK for validate, publish, create deployment, submit task, replay
- CLI for run watch and deployment task submission
- Console for visual inspection and operator workflows

## Where To Verify Status

- Readiness: [Production Readiness Scorecard](../readiness/scorecard.md)
- Workflow coverage: [Product Workflow Coverage Matrix](../product/workflow-coverage-matrix.md)
- UX acceptance: [Console Experience Acceptance](../product/console-experience-acceptance.md)
- Quick commands: [Quickstart](quickstart.md)

