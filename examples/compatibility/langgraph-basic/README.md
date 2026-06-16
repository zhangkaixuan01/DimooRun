# LangGraph Compatibility Basic Example

This example proves the Compatibility API path for a small LangGraph-shaped project.

## Flow

1. Migration report
2. Create assistant
3. Create thread
4. Create run
5. Stream events
6. Replay events
7. Cancel run
8. Native Run and Task evidence

## Run

Start DimooRun locally, then run:

```bash
uv run python examples/compatibility/langgraph-basic/compat_flow.py --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1
```

The script prints assistant_id, thread_id, run_id, task_id, stream events, and native evidence links.
