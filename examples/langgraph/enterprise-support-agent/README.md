# Enterprise Support Agent

This is a LangGraph customer support agent that uses a real OpenAI-compatible
chat model and LangChain tools.

It is the production-shaped example for this directory. The deterministic
`support-agent` is kept for adapter smoke tests; this example shows how a real
agent declares secrets, calls tools, records model usage, and pauses for human
approval on high-risk requests.

## Agent Behavior

- Classifies a customer support request into billing, order, account-risk, or technical.
- Calls `search_support_knowledge` for policy context.
- Calls `lookup_order_status` when the request is order-related.
- Drafts the response with an OpenAI-compatible model.
- Records `tool_events`, `model_events`, and `token_usage` in graph state.
- Uses `interrupt()` for high-risk account actions and resumes with `Command(resume=...)`.
- Uses `configurable.thread_id` for checkpointed LangGraph runs.

## LangGraph Entry

`langgraph.json` is the native LangGraph entry:

```json
{
  "dependencies": ["."],
  "graphs": {
    "enterprise_support_agent": "./agent.py:build_graph"
  },
  "env": ".env"
}
```

With `langgraph-cli` installed:

```bash
cd examples/langgraph/enterprise-support-agent
langgraph dev
```

## Required Secrets

The agent requires `MODEL_GATEWAY_API_KEY`.

For local LangGraph development, create `.env` from `.env.example`:

```bash
MODEL_GATEWAY_API_KEY=...
MODEL_GATEWAY_BASE_URL=https://api.openai.com/v1
MODEL_GATEWAY_MODEL=gpt-4o-mini
```

For DimooRun, register the key as a Secret named `MODEL_GATEWAY_API_KEY`; do not
put plaintext keys in `manifest.yaml`.

## Local Run

Install this example's dependencies, set the environment variables above, then:

```bash
python run_local.py
```

## Production Notes

- Replace the local example tools with calls to your governed backends or
  DimooRun Tool Gateway once runtime tool injection is enabled.
- Route model access through your enterprise Model Gateway, such as New API or
  another OpenAI-compatible gateway.
- Replace `InMemorySaver` with a durable checkpointer for production recovery.
