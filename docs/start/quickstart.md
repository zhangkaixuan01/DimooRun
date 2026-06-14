# Quickstart

This quickstart describes the intended 15-minute local path. Treat it as a
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
Compose fails in your environment, record the failure in
[Compose Smoke Report](../readiness/compose-smoke-report.md) instead of treating
the path as proven.

Working directory: repository root.

```bash
uv run python scripts/compose_runtime_smoke.py
```

Expected result: the smoke script can reach server `/healthz` and the Console
root page. Current failures are still valid evidence; do not hide them.

Current local evidence is tracked in [Compose Smoke Report](../readiness/compose-smoke-report.md).

## Publish The Example Agent

Use the real `examples/langgraph/support-agent` package. The command below
validates the package, creates an agent, publishes a ready version, creates an
active deployment, and submits one task.

Working directory: repository root.

```powershell
@'
from dimoorun import DimooRun

client = DimooRun(
    api_key="dev-local-key",
    base_url="http://127.0.0.1:8000",
    tenant_id=1,
    project_id=1,
)

manifest = {
    "schema_version": "1.0",
    "name": "support-agent",
    "version": "0.1.0",
    "runtime": {
        "framework": "langgraph",
        "adapter": "langgraph",
        "entrypoint": "agent:build_graph",
        "python": ">=3.11",
    },
    "capabilities": {
        "invoke": True,
        "stream": True,
        "checkpoint": True,
        "resume": True,
        "interrupt": True,
        "human_in_loop": True,
        "tool_events": True,
        "model_events": True,
        "token_usage": True,
        "filesystem": False,
        "subagents": False,
    },
}

validation = client.validate_package(
    package_uri="file:///workspace/examples/langgraph/support-agent",
    framework="langgraph",
    adapter="langgraph",
    entrypoint="agent:build_graph",
    manifest=manifest,
)
agent = client.create_agent(name="support-agent", description="Phase 12A quickstart")
version = client.create_agent_version(
    agent_id=agent["id"],
    version="0.1.0",
    package_uri="file:///workspace/examples/langgraph/support-agent",
    framework="langgraph",
    adapter="langgraph",
    entrypoint="agent:build_graph",
    manifest=manifest | {"validation_token": validation["validation_token"]},
    capabilities=manifest["capabilities"],
    status="ready",
)
deployment = client.create_deployment(
    agent_id=agent["id"],
    agent_version_id=version["id"],
    environment="local",
    desired_status="active",
)
run = client.submit_deployment_task(
    deployment_id=deployment["id"],
    input={"message": "customer asks for refund and account deletion"},
    thread_id="phase-12a-quickstart",
)

print(f"agent_id={agent['id']}")
print(f"version_id={version['id']}")
print(f"deployment_id={deployment['id']}")
print(f"run_id={run['run_id']}")
client.close()
'@ | uv run python -
```

Expected result: you get numeric `agent_id`, `version_id`, `deployment_id`, and
`run_id` values.

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

The publish step already submitted one task. To submit another from CLI:

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
- policy/approval evidence for high-risk messages
- replay or triage next action where available

Expected result: the LangGraph support-agent example reaches a visible terminal
state and shows structured runtime evidence.

## Tear Down

Working directory: repository root.

```bash
docker compose down --remove-orphans --volumes
```

Expected result: all local containers and volumes are removed.

## Stop The Stack

Record any mismatch in the readiness scorecard before calling the path complete.
