# DeepAgents Support Example

This example is the minimal realistic package for DimooRun's
`DeepAgentsAdapter`. It demonstrates package shape, real DeepAgents loading,
and event streaming without depending on an external model provider.

## Manifest

The package manifest is [`manifest.yaml`](manifest.yaml) and declares:

- framework: `deepagents`
- adapter: `deepagents`
- entrypoint: `support_agent:build_agent`
- capabilities: invoke, stream, interrupt, human-in-the-loop, tool events,
  model events, token usage, filesystem, subagents

## What The Agent Does

- patches DeepAgents model resolution to use a deterministic fake chat model
- creates a real `create_deep_agent(...)` graph
- streams genuine DeepAgents runtime events through the adapter

## Expected Commands

Working directory: repository root.

```bash
cp .env.example .env
docker compose up --build
```

Working directory: repository root.

```bash
uv sync --extra deepagents
```

Working directory: repository root.

```bash
uv run pytest tests/adapters/test_deepagents_adapter.py tests/adapters/test_real_framework_smoke.py -q
```

Working directory: repository root.

```bash
uv run dimoorun agent publish --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --name deepagents-support-agent --version 0.1.0 --package-uri file:///workspace/examples/deepagents/support-agent --framework deepagents --adapter deepagents --entrypoint support_agent:build_agent --manifest-file examples/deepagents/support-agent/manifest.json
```

Working directory: repository root.

```bash
uv run dimoorun run watch --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --run-id <RUN_ID> --show-events
```

## Expected Console Result

After publish, Console should show:

- an agent entry for `deepagents-support-agent`
- a `ready` version tied to the DeepAgents adapter
- runtime evidence that distinguishes stream output and approval-style behavior
  from the simpler LangChain example
- Console reachable at `http://127.0.0.1:8080` with the same local `dev-local-key`
  runtime path used by the main quickstart

## Troubleshooting

- If load fails with model-resolution errors, rerun
  `tests/adapters/test_real_framework_smoke.py` first. This example depends on
  the deterministic patch path in `agent.py`.
- If filesystem or subagent capabilities appear in the manifest but do not show
  in behavior, remember they are capability declarations, not proof that a
  full production workflow exists around them yet.
- If CLI manifest handling is inconvenient, use the SDK publish flow and pass
  the manifest payload directly.

## Production Caveats

- Current maturity shorthand remains:
  `Production-shaped foundation: yes.` and
  `External production-grade platform: not yet.`
- The example patches model initialization for deterministic testing.
- It is useful for adapter compatibility evaluation, not for proving hosted
  DeepAgents production operations.
- Production DeepAgents usage should bind real secret, gateway, sandbox, and
  approval controls before being treated as operationally safe.
