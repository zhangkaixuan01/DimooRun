# Quickstart

This quickstart describes the intended 10-minute local path. Treat it as a
guided baseline, not proof that the project is externally production-ready.

Current maturity shorthand:

```text
Production-shaped foundation: yes.
External production-grade platform: not yet.
```

## Working Directory

Use the repository root unless a step says otherwise.

```text
<repository-root>
```

## Start The Stack

Working directory: repository root.

```bash
cp .env.example .env
docker compose up --build
```

Expected result: server, worker, Console, Postgres, Redis, and MinIO start. If
Compose fails in your environment, treat the path as unproven and compare the
result with [Current Maturity](../readiness/current-maturity.md).

Working directory: repository root.

```bash
uv run python scripts/compose_runtime_smoke.py
```

Expected result: the smoke script can reach server `/healthz` and the Console
root page, then validate the example package, create a ready agent version,
create an active deployment, submit a task, wait for the run to reach a
terminal state, and write local activation evidence. Current failures are still
valid evidence; do not hide them.

The local Compose activation path is proven by the integration workflow artifact
`compose-evidence-index`.

Current readiness status is tracked in
[Production Readiness Scorecard](../readiness/scorecard.md).

## Publish The Example Agent

Use the real `examples/langgraph/support-agent` package. The command below
validates the package, creates or reuses the agent, and publishes a ready
version.

Working directory: repository root.

```bash
uv run dimoorun publish examples/langgraph/support-agent
```

Expected result: you get `agent_id`, `agent_version_id`, `validation_token`, and
a next command for deployment.

## Deploy The Agent

Working directory: repository root.

```bash
uv run dimoorun deploy support-agent --env local
```

Expected result: you get a `deployment_id`, `agent_version_id`, desired status
`active`, and a Console deep link.

## Open The Console

Open `http://127.0.0.1:8080`. Use the local operator account:

```text
email: admin@local.dimoorun
password: admin12345
```

Expected result: the Console shell loads with the default scope `tenant_id=1`,
`project_id=1`, environment `local`.

## Inspect The Deployment

In Console, verify:

- the `support-agent` record exists
- the new version is `ready`
- the deployment exists in the `local` environment
- the deployment desired status is `active`

## Submit A Task

Working directory: repository root.

```bash
uv run dimoorun run support-agent --env local --input-json "{\"message\":\"customer asks for refund and account deletion\"}" --watch --show-events
```

Expected result: you get a `run_id` and `task_id`, followed by run status
updates until the run reaches a terminal state.

If you prefer the explicit automation command, use the lower-level task submit
and watch commands:

Working directory: repository root.

```bash
uv run dimoorun deployment task submit --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --deployment-id <DEPLOYMENT_ID> --thread-id quickstart-cli --input-json "{\"message\": \"timeout in checkout flow\"}"
```

Expected result: a new `run_id` and `task_id` are returned with status `queued`.

## Verify The Run

Watch the run from CLI:

Working directory: repository root.

```bash
uv run dimoorun run watch --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --run-id <RUN_ID> --show-events
```

Then inspect the run in Console:

- status
- attempts
- events
- deployment and version
- input, output, and error payloads
- artifacts and audit links when present
- policy/approval evidence for high-risk messages
- replay or triage next action where available

Expected result: the LangGraph support-agent example reaches a visible terminal
state and shows structured runtime evidence.

## One-Command Demo Seed

To prepare the same P0-A demo data with one command:

Working directory: repository root.

```bash
uv run dimoorun demo seed --watch
```

Expected result: the command creates or reuses the `support-agent`, deploys it
to `local`, submits a task, and prints Console links for Dashboard, Deployment,
and Run evidence.

## Tear Down

Working directory: repository root.

```bash
docker compose down --remove-orphans --volumes
```

Expected result: all local containers and volumes are removed.

## Stop The Stack

Record any mismatch in the readiness scorecard before calling the path complete.
