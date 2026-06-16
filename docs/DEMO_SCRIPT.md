# Demo Script

This script is for maintainers who want to record or present a truthful
DimooRun walkthrough. It prioritizes workflows that already have repository
evidence and calls out where the demo is illustrative rather than hosted-proof.

Current maturity shorthand:

```text
Production-shaped foundation: yes.
External production-grade platform: not yet.
```

Evidence index: [docs/readiness/evidence-gallery.md](readiness/evidence-gallery.md)

## Prerequisites

- local `.env` created from `.env.example`
- Docker Compose available
- repository dependencies installed
- a shell at the repository root
- browser access to `http://127.0.0.1:8080`

## Setup

Goal: show the stack come up and establish the evaluation scope.

Working directory: repository root.

```bash
cp .env.example .env
docker compose up --build
```

Narration:

- explain tenant/project/environment scope
- explain that the demo is local proof, not hosted GA proof
- open the Console login page
- note which screens have current evidence-gallery coverage and which are still local-only

## Agent Publish

Goal: publish the LangGraph example as a real package/version/deployment path.

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
agent = client.create_agent(name="demo-support-agent", description="demo")
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
    input={"message": "customer asked to delete a production account"},
    thread_id="demo-script",
)

print(f"deployment_id={deployment['id']}")
print(f"run_id={run['run_id']}")
client.close()
'@ | uv run python -
```

Narration:

- explain package validation token and ready version gating
- show the deployment and run in Console
- reference the gallery rows for dashboard, agent detail, and deployment workflow

## Deployment Promote

Goal: show the promotion surface and impact preview. Use existing deployment
detail tabs in Console rather than claiming a fully hosted promotion story.

Narration:

- open the deployment detail
- switch to the promotion tab
- point out active runs, queued tasks, candidate readiness, and rollback target

## Run Inspect

Goal: show the runtime evidence model.

Working directory: repository root.

```bash
uv run dimoorun run watch --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --run-id <RUN_ID> --show-events
```

Narration:

- highlight attempts, events, output, and deployment/version context
- show how run evidence differs from a plain framework-only demo

## Replay

Goal: show that replay creates a new run instead of mutating the original.

Narration:

- open the replay comparison page in Console
- explain source run versus replay run
- call out that replay is for investigation, not silent mutation
- point to the run workbench evidence row for follow-up verification

## Policy Approval

Goal: show that high-risk actions can require approval instead of silently proceeding.

Narration:

- open Human Tasks or Policy Workbench pages
- explain the approval-required path for destructive or risky behavior
- point to audit reason requirements

## Gateway Route Test

Goal: show the governed published surface workflow.

Narration:

- open Published Surfaces
- demonstrate route test, request log drilldown, and evidence bundle context
- emphasize that publish/gateway flows are governed runtime surfaces

## Incident Triage

Goal: show operational evidence beyond raw logs.

Narration:

- open Incident Triage
- explain acknowledge, linked evidence, delivery attempts, and resolution summary

## Cost Drilldown

Goal: show the current cost/usage surface honestly.

Narration:

- open a run detail or model-gateway-related view that exposes token/cost
  information
- explain that cost coverage exists, but broader budget/cost workflows are not
  complete yet

## Close

End with:

- current maturity statement
- evidence gallery location
- trust/security docs location
- example READMEs for follow-up evaluation
- reminder that hosted proof still has gaps
