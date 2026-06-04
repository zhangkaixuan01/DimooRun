# Support Agent

This is a deterministic customer support agent built with LangGraph.

It classifies support requests, retrieves a simple policy, drafts a response,
and pauses for human approval when the request is high risk. It does not call an
external LLM provider, so it can run locally without API keys.

## LangGraph Entry

The project uses the standard `langgraph.json` entrypoint:

```json
{
  "dependencies": ["."],
  "graphs": {
    "support_agent": "./agent.py:build_graph"
  }
}
```

The graph id is `support_agent`, and the graph factory is `./agent.py:build_graph`.

With `langgraph-cli` installed, this is the normal development shape:

```bash
cd examples/langgraph/support-agent
langgraph dev
```

## Agent Behavior

- Classifies the request into a support category and priority.
- Looks up a deterministic policy for the category.
- Drafts a customer-facing answer.
- Emits model-like metadata and token usage for observability tests.
- Pauses with `interrupt()` when the request needs human approval.
- Resumes with `Command(resume=...)` after approval.
- Uses `configurable.thread_id` so checkpointed conversations can continue.

## Graph Capabilities

- `invoke`: normal graph execution through `graph.invoke`.
- `stream`: graph update streaming through `graph.stream`.
- `checkpoint`: compiled with an `InMemorySaver` checkpointer for local development.
- `interrupt / resume`: high-risk support actions require approval.
- `tool_events`: policy lookup events are recorded in graph state.
- `model_events`: deterministic drafter metadata is recorded in graph state.
- `token_usage`: deterministic token accounting is recorded in graph state.

## Local Run

Install the LangGraph extra first:

```bash
uv sync --extra langgraph
```

Then run:

```bash
uv run python examples/langgraph/support-agent/run_local.py
```

## Production Note

This example uses `InMemorySaver` so it can run without external services.
Production LangGraph agents should use a durable checkpoint backend, typically
Postgres, and should not rely on process memory for checkpoint recovery.
