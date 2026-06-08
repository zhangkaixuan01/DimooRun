# Getting Started

This guide explains the intended first successful runtime path. Some steps depend on environment verification that is still marked partial in [Production Readiness Scorecard](../readiness/scorecard.md).

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

## Where To Verify Status

- Readiness: [Production Readiness Scorecard](../readiness/scorecard.md)
- Workflow coverage: [Product Workflow Coverage Matrix](../product/workflow-coverage-matrix.md)
- UX acceptance: [Console Experience Acceptance](../product/console-experience-acceptance.md)
- Quick commands: [Quickstart](quickstart.md)

