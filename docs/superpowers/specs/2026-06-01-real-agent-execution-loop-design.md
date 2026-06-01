# Real Agent Execution Loop Design

## Goal

Phase 14 makes DimooRun useful as an agent runtime by completing the smallest
real execution loop:

```text
AgentVersion package metadata -> Run / Task -> worker lease -> adapter execution
-> RunAttempt / Event / Task / Run persistence -> Console read path
```

The first hard proof is an example LangGraph agent that can be registered,
queued, executed by a worker, and inspected through the existing API and
Console surfaces.

## Scope

This phase focuses on the runtime spine, not additional enterprise surfaces.

- A queued native task can be leased by the worker from the configured backend.
- The worker resolves the task's run and agent version from durable storage.
- The worker builds an `AgentRuntimeSpec` from `AgentVersion` package metadata.
- The worker loads the adapter and executes the package entrypoint through the
  existing `WorkerExecutor` contract.
- The execution result updates `RunAttempt`, `Run`, `Task`, and `Event` records.
- `/runs/{run_id}/attempts` returns real attempts instead of an empty list.
- `/runs/{run_id}/events` exposes the events emitted during worker execution.
- The worker process supports one-shot execution for tests and continuous
  polling for local development.

## Non-Goals

These remain outside this phase:

- Full `resume`, `retry`, and `replay` behavior.
- Trace tree, Run Graph visualization, and replay comparison UI.
- Model Gateway deep integration and usage accounting enforcement.
- Full Policy Engine coverage for every runtime path.
- Helm, Kubernetes, or multi-node production verification.
- Reworking all AdminCollection Console pages into product-specific workflows.

## Architecture

The implementation should reuse the current boundaries instead of introducing a
parallel runtime:

- `SQLAlchemyNativeRuntimeStore` remains the source of durable Agents,
  AgentVersions, Runs, Tasks, and Events for API requests.
- `SQLAlchemyTaskBackend` remains the durable task leasing backend.
- `WorkerExecutor` remains the execution coordinator for adapter loading,
  attempts, result handling, retries, timeout, and event emission.
- A new worker wiring layer adapts durable database rows into the
  `WorkerExecutor` dependencies: `RuntimeRunStore`, task backend, replay/event
  sink, adapter registry, and `AgentRuntimeSpec` lookup.

The first implementation may keep the adapter registry narrow: LangGraph is the
required production path, and tests may use a fake adapter to prove the durable
worker wiring without requiring a real model call.

## Data Flow

1. A client creates an Agent and AgentVersion.
2. A client creates a Run/Task from the Agent or Deployment path.
3. The worker leases a queued Task.
4. The worker loads the associated Run and AgentVersion.
5. The worker constructs runtime context from tenant, project, run, task,
   agent, version, deployment, and thread fields.
6. The adapter loads the package and executes invoke or stream.
7. The worker writes attempt lifecycle events, terminal run status, terminal
   task status, and visible runtime events.
8. Console reads Runs, Tasks, Events, and Attempts from the existing APIs.

## Error Handling

- Missing Run, Task, AgentVersion, or adapter configuration fails the attempt
  and task with a structured error instead of crashing the worker loop.
- Adapter failures follow existing retry semantics where possible.
- Timeout and stale fencing behavior stay inside `WorkerExecutor`.
- One-shot worker execution should return a clear status when no task is
  available, so CLI and tests can distinguish idle from failure.

## Testing

Implementation must be test-first.

- Add a failing durable worker integration test that creates AgentVersion,
  Run, and Task rows, executes one worker cycle, and asserts successful Run,
  Task, Attempt, and Event state.
- Add a failing API test proving `/runs/{run_id}/attempts` returns persisted
  attempts.
- Add a failing worker entrypoint or loop test proving one-shot execution calls
  the real executor path when a task exists.
- Keep existing runtime, scheduler, native API, and Console contract tests
  passing after the changes.

## Acceptance Criteria

- A queued native task can complete successfully through worker execution.
- Run status becomes `succeeded` or `failed` based on adapter result.
- Task status becomes terminal after execution.
- At least one RunAttempt is persisted and returned by API.
- Events include attempt start and run terminal events.
- The worker process can run in one-shot mode for local verification.
- Existing demo mode remains available, but the core proof uses durable backend
  state rather than mock data.
