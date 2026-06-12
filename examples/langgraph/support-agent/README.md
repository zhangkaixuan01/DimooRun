# LangGraph Support Agent Example

This example shows the most complete local evaluator path for DimooRun today.
It is a deterministic support triage graph built with LangGraph and packaged in
the same shape DimooRun expects for real runtime execution.

## Manifest

The package manifest is [`manifest.yaml`](manifest.yaml) and declares:

- framework: `langgraph`
- adapter: `langgraph`
- entrypoint: `agent:build_graph`
- capabilities: invoke, stream, checkpoint, resume, interrupt,
  human-in-the-loop, tool events, model events, token usage

## What The Agent Does

- classifies the request into support category and priority
- emits deterministic policy lookup events
- drafts a deterministic answer
- interrupts for human approval on high-risk requests
- resumes after approval payload is supplied

## Expected Commands

Working directory: repository root.

```bash
cp .env.example .env
docker compose up --build
```

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
agent = client.create_agent(name="langgraph-support-agent", description="example")
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
    input={"message": "customer asked to cancel production account"},
    thread_id="langgraph-example",
)

print(f"deployment_id={deployment['id']}")
print(f"run_id={run['run_id']}")
client.close()
'@ | uv run python -
```

Working directory: repository root.

```bash
uv run dimoorun run watch --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --run-id <RUN_ID> --show-events
```

## Expected Console Result

In `http://127.0.0.1:8080`, you should be able to confirm:

- the agent exists and has a `ready` version
- the deployment is active in the `local` environment
- the run has attempts and ordered events
- high-risk input creates approval-oriented runtime evidence
- replay and run-detail surfaces can inspect the result

## Troubleshooting

- If package validation fails, compare the manifest fields with
  [`manifest.yaml`](manifest.yaml) and ensure the entrypoint is
  `agent:build_graph`.
- If the worker never finishes the run, inspect `docker compose logs worker`.
- If Console login fails, confirm Redis is reachable and `.env` still contains
  the bootstrap admin credentials.
- If the agent loads but checkpoint/resume behavior looks transient, remember
  the example uses `InMemorySaver`.

## Production Caveats

- The example uses an in-memory checkpointer, not a durable production backend.
- The agent is deterministic and intentionally avoids external model providers.
- The example proves packaging and runtime shape, not hosted production
  readiness.
