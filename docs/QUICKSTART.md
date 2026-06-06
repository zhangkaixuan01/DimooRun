# Quickstart

This quickstart describes the intended 15-minute local path. Treat it as a guided baseline, not proof that the project is externally production-ready.

## Working Directory

Use the repository root unless a step says otherwise.

```text
D:\codes\DimooRun
```

## Start The Stack

Working directory: repository root.

```bash
uv run python scripts/compose_smoke.py
```

Expected result: the Compose smoke contract passes for server, worker, Console, Postgres, Redis, and MinIO. This is a static contract check; it does not start containers.

Working directory: repository root.

```bash
uv run python scripts/compose_runtime_smoke.py
```

Expected result: the Compose stack starts, the server `/healthz` endpoint and Console root page respond, `docker compose ps` prints service state, and the stack is torn down. If this fails, record the failure in [Production Readiness Scorecard](PRODUCTION_READINESS_SCORECARD.md) instead of treating the happy path as proven.

Current local evidence is tracked in [Compose Smoke Report](COMPOSE_SMOKE_REPORT.md).

Working directory: repository root.

```bash
docker compose up --build
```

Expected result: server, worker, Console, Postgres, Redis, and MinIO containers start. Current maturity note: clean-machine Compose smoke still needs attached evidence in [Production Readiness Scorecard](PRODUCTION_READINESS_SCORECARD.md).

## Open The Console

Open the Console URL printed by Compose or Vite. Use the local operator account from `README.md`.

Expected result: the Console shell loads with selected tenant, project, and environment scope.

## Register And Deploy An Agent

Use the package/version workflow once Phase 0A is complete. Until then, use the existing Native API and Console package surfaces as partial workflow evidence.

Expected path:

1. Register an example package.
2. Validate its manifest and adapter.
3. Create a deployment.
4. Promote the deployment when validation allows it.

## Submit A Task

Submit a task through the deployment workflow or Native API.

Expected result: a task and run are created with request identity and runtime evidence.

## Verify The Run

Inspect the run in Console:

- status;
- attempts;
- events;
- artifacts;
- deployment and version;
- error summary if failed;
- replay or triage next action where available.

## Stop The Stack

Working directory: repository root.

```bash
docker compose down
```

Record any mismatch in the readiness scorecard before calling the path complete.
