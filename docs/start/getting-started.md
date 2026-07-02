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
<repository-root>
```

## First Runtime Path

The intended evaluator path is:

1. Start the server, worker, Console, Postgres, Redis, and object store.
2. Sign in to the Console with the local operator account.
3. Publish the example agent with `uv run dimoorun publish examples/langgraph/support-agent`.
4. Deploy it with `uv run dimoorun deploy support-agent --env local`.
5. Submit work with `uv run dimoorun run support-agent --env local --watch`.
6. Inspect the run, attempts, events, artifacts, and audit evidence.
7. Try replay or failure triage if the run fails.

This path is the product activation target. It proves local activation only, not
external production readiness.
The local Compose activation path is proven by the integration workflow artifact
`compose-evidence-index`.

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

Use this path for the product happy path covered by the readiness scorecard.

## API And SDK Path

If you want scriptable evaluation instead of manual API calls, use:

- Productized CLI for publish, deploy, run, open, and demo seed.
- Explicit CLI commands for package validation, deployment task submission,
  run watch, and replay.
- Python SDK for lower-level automation.
- Console for visual inspection and operator workflows.

## Where To Verify Status

- Readiness: [Production Readiness Scorecard](../readiness/scorecard.md)
- Product surface: [Product Documentation](../product/README.md)
- Current caveats: [Current Maturity](../readiness/current-maturity.md)
- Quick commands: [Quickstart](quickstart.md)

