# LangChain Agent Support Example

This example is the minimal realistic package for DimooRun's
`LangChainAgentAdapter`. It is designed to show how a LangChain agent package
is described, published, and inspected without claiming full production proof.

## Manifest

The package manifest is [`manifest.yaml`](manifest.yaml) and declares:

- framework: `langchain-agent`
- adapter: `langchain-agent`
- entrypoint: `support_agent:build_agent`
- capabilities: invoke, stream, tool events, model events, token usage

## What The Agent Does

- builds a deterministic LangChain `create_agent(...)` runtime
- returns a stable answer without external API keys
- supports streaming output for adapter smoke and runtime inspection

## Expected Commands

Working directory: repository root.

```bash
cp .env.example .env
docker compose up --build
```

Working directory: repository root.

```bash
uv sync --extra langchain
```

Working directory: repository root.

```bash
uv run pytest tests/adapters/test_langchain_agent_adapter.py tests/adapters/test_real_framework_smoke.py -q
```

Working directory: repository root.

```bash
uv run dimoorun agent publish --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --name langchain-support-agent --version 0.1.0 --package-uri file:///workspace/examples/langchain-agent/support-agent --framework langchain-agent --adapter langchain-agent --entrypoint support_agent:build_agent --manifest-file examples/langchain-agent/support-agent/manifest.json
```

Working directory: repository root.

```bash
uv run dimoorun run watch --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --run-id <RUN_ID> --show-events
```

## Expected Console Result

After publish, Console should show:

- an agent entry for `langchain-support-agent`
- a `ready` version bound to the LangChain adapter
- deployment compatibility with the same publish/deploy/task flow used by the
  quickstart
- Console reachable at `http://127.0.0.1:8080` with the same local `dev-local-key`
  runtime path used by the main quickstart

## Troubleshooting

- If publish fails, verify the package URI matches the runtime environment. The
  Compose-based worker expects `/workspace/...` paths.
- If the manifest file is missing, convert the YAML manifest into JSON payload
  before calling the CLI, or use the Python SDK path from the main quickstart.
- If stream assertions fail, rerun the adapter smoke tests first to confirm the
  example package still matches the adapter contract.

## Production Caveats

- Current maturity shorthand remains:
  `Production-shaped foundation: yes.` and
  `External production-grade platform: not yet.`
- The model is a fake deterministic chat model for testability, not a real LLM.
- The example proves adapter/runtime wiring, not prompt quality or hosted load
  behavior.
- Production LangChain agents should add real model gateway, secret, and audit
  requirements before claiming runtime safety.
