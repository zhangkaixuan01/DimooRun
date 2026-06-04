# Implementation Update - 2026-06-01

This document records the core-runtime and Console work completed on 2026-06-01 before the production-hardening plan begins.

## Scope Completed

### Durable Worker Execution Loop

- Added SQLAlchemy-backed durable worker wiring in `apps/server/dimoo_run/worker/durable.py`.
- Wired durable execution into `apps/worker/dimoo_run_worker/main.py` through `run_once()`.
- Updated `WorkerLoop` so it can execute a real callback path instead of lease-only behavior.
- Persisted worker events through a durable replay-buffer path into the `Event` table.
- Added structured worker failures for missing agent version/spec and missing adapter.
- Exposed real persisted run attempts through `/v1/runs/{run_id}/attempts`.

### Native Runtime API

- Confirmed native task creation creates real `Run` and `Task` records.
- Confirmed worker entrypoint can execute a queued SQLAlchemy-backed task through a real adapter.
- Changed `/v1/runs/{run_id}/replay` from a stub that returned the original run into a real replay action that creates a new run and task from the source run input.
- Added a `run.replayed` event on the replay run with `source_run_id` and `task_id`.

### Console Core Runtime Views

- Run detail now loads real run, events, and attempts.
- Run detail now shows real `input`, `output`, and `error` payloads instead of hard-coded sample JSON.
- Event timeline supports selected-event interaction; selected event payload changes when the user clicks a timeline item.
- Runs list no longer fabricates latency/cost values when the backend does not provide them.
- Dashboard no longer hides the runtime chart in live mode; it derives chart points from real runs already returned to the page.
- Tasks page queue/status filters are wired to real local filtering.
- Replay page now loads real runs, selects a source run, calls the dedicated replay API, and links to the replay run result.

## Verification Completed

The latest focused verification run after the production-hardening pass:

```powershell
npm run test
npm run build
uv run pytest tests/worker/test_durable_worker_execution.py tests/worker/test_worker_loop_durable_backend.py tests/runtime/test_sqlalchemy_worker_executor.py tests/server/test_worker_entrypoint.py tests/api/test_native_api.py -q
uv run ruff check apps/server/dimoo_run/api/native/runs.py apps/server/dimoo_run/api/native/runtime.py apps/server/dimoo_run/worker/executor.py apps/server/dimoo_run/runtime/sqlalchemy_run_store.py tests/api/test_native_api.py tests/runtime/test_sqlalchemy_worker_executor.py
```

Results:

- Console contract tests: passed.
- Console production build: passed.
- Focused backend tests: `27 passed`.
- Focused ruff check: passed.

## Remaining Production Gaps

The runtime is now an alpha/beta-level core loop, not production-complete. The main remaining gaps are:

- Native API responses do not expose trustworthy run lifecycle timestamps and latency to the Console.
- Event API responses do not expose persisted event creation time.
- Dashboard metrics are still derived in the Console instead of being served by a runtime metrics endpoint.
- Replay creates a new run/task, but does not yet support candidate version selection or structured diff output.
- Worker retry/dead-letter semantics need stronger end-to-end guarantees for repeated failure and recovery.
- Core Console paths still need interaction-level tests beyond static contract tests and build checks.

## Production Hardening Completion

- Native run lifecycle fields are exposed through the API and mapped into Console run views.
- Worker success/failure paths persist run/task/attempt timestamps, and attempts persist latency.
- Replay creates durable run/task/event records and supports selecting a candidate agent version.
- Console Replay now calls the dedicated replay API and passes `agent_version_id` instead of using a generic control action.
- Worker missing-adapter failures are covered by a dead-letter contract test.

## Console Core Flow Completion

The Console now closes the MVP loop from `docs/DESIGN_SPEC.md`:

```text
Register Agent -> Create AgentVersion -> Create Task -> Worker executes -> Inspect Run / Task / Event
```

Implementation plan: `docs/superpowers/plans/2026-06-01-console-core-flow.md`.

This pass is intentionally narrow. It adds AgentVersion creation and Task submission to the existing Agents page and keeps Runs, Run Detail, Tasks, Events, and Replay as the inspection and control surfaces. Full Agent detail pages, package upload, deployment promotion, and rich manifest editing remain outside this pass.

Verification:

- `cd apps/console && npm run test`: passed.
- `cd apps/console && npm run build`: passed.
- `uv run pytest tests/api/test_native_api.py::test_native_agent_task_run_event_flow_is_real -q`: passed.

## Production Console Live Deployment Flow

Implementation plan: `docs/superpowers/plans/2026-06-01-production-console-live-deployment-flow.md`.

This pass moves the product workflow from MVP direct-agent task submission to the production deployment path:

```text
Register Agent -> Create AgentVersion -> Create active Deployment -> Submit Deployment Task -> Inspect Run / Task / Event
```

Backend changes:

- Added `POST /v1/deployments/{deployment_id}/tasks`.
- Deployment task submission requires tenant/project scope and `agent:invoke`.
- Only active deployments accept new tasks; inactive deployments return `deployment_not_active`.
- Runs created through a deployment persist `deployment_id`.
- Native OpenAPI route tests now include the deployment task endpoint.

Console changes:

- Removed product-path mock data selection from `consoleClient`; Console now runs live-only when `VITE_DIMOORUN_API_BASE_URL` is set and otherwise shows offline state.
- Agents page now manages Agent and AgentVersion only.
- Deployments page is now the production runtime entry: create Deployment, control desired status, submit task through Deployment, and link to the created Run.
- Replay candidate versions now load from real AgentVersion API records for the selected run's agent.

Verification added:

- Backend deployment task flow tests.
- Console contract tests rejecting mock product data and requiring deployment task workflow wiring.
