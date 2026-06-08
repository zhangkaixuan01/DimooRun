# Core Runtime Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the Agent run execution loop from alpha/beta closure to production-grade core behavior: trustworthy lifecycle metrics, durable replay semantics, worker failure guarantees, and Console views backed by real data.

**Architecture:** Keep the existing SQLAlchemy native runtime, worker executor, and Console client boundaries. Harden the existing data path first: expose lifecycle timestamps and latency from persisted run/task/attempt rows, add replay metadata and candidate version selection, and verify every state transition with backend tests before updating Console views.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest, ruff, Vue 3, TypeScript, Vite, existing Console contract tests.

**Execution Status (2026-06-01):** Implemented through Task 6. Backend core suite, Console contract/build, and focused ruff have passed.

---

## File Structure

- Modify `apps/server/dimoo_run/api/native/runs.py`
  - Extend `RunRead` and `EventRead` with persisted lifecycle fields.
  - Keep `/runs/{run_id}/replay` as the replay API surface, then add candidate-version support after tests require it.
- Modify `apps/server/dimoo_run/api/native/runtime.py`
  - Preserve run creation/replay behavior while returning `NativeRun` values with timestamps.
  - Add candidate-version replay support by resolving an optional agent version.
- Modify `apps/server/dimoo_run/api/native/agents.py`
  - Return enough version metadata for Console candidate selection if the existing response is missing it.
- Modify `apps/server/dimoo_run/worker/executor.py`
  - Ensure attempt latency, task timestamps, run timestamps, and terminal status transitions are written consistently for success, failure, timeout, and missing adapter/spec cases.
- Modify `apps/server/dimoo_run/persistence/repositories.py`
  - Add focused helpers only if existing `transition()` methods cannot preserve started/finished times correctly.
- Modify `apps/console/src/api/generated/dimoorun.ts`
  - Add typed fields returned by Native API (`created_at`, `started_at`, `finished_at`, `latency_ms`, event `created_at`) and optional replay payload.
- Modify `apps/console/src/api/types.ts`
  - Make run/event lifecycle fields part of the Console domain model.
- Modify `apps/console/src/api/client.ts`
  - Map native lifecycle fields without fabricating values.
- Modify `apps/console/src/pages/runs/RunsPage.vue`
  - Show real created/started/finished/latency values.
- Modify `apps/console/src/pages/runs/RunDetailPage.vue`
  - Show lifecycle metadata and attempt latency.
- Modify `apps/console/src/pages/replay/ReplayPage.vue`
  - Add candidate version selection and display structured replay metadata.
- Modify `apps/console/tests/console-contract.test.mjs`
  - Add frontend contract checks for no fake lifecycle metrics and replay candidate workflow.
- Modify `tests/api/test_native_api.py`
  - Add API tests for lifecycle fields and replay candidate version behavior.
- Modify `tests/runtime/test_sqlalchemy_worker_executor.py`
  - Add worker tests for timestamps, latency, retry, and dead-letter paths.
- Modify `tests/worker/test_durable_worker_execution.py`
  - Add durable event/timestamp verification.

---

## Task 1: Expose Run Lifecycle Fields From Native API

**Files:**
- Modify: `tests/api/test_native_api.py`
- Modify: `apps/server/dimoo_run/api/native/runs.py`
- Modify: `apps/server/dimoo_run/api/native/runtime.py`

- [ ] **Step 1: Write the failing API test**

Add this test to `tests/api/test_native_api.py` after `test_native_agent_task_run_event_flow_is_real`:

```python
def test_native_run_read_exposes_persisted_lifecycle_fields() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)
    task_body = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "hello"}},
    ).json()

    run = client.get(f"/v1/runs/{task_body['run_id']}", headers=auth_headers(key))

    assert run.status_code == 200
    body = run.json()
    assert isinstance(body["created_at"], str)
    assert body["started_at"] is None
    assert body["finished_at"] is None
    assert body["latency_ms"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/api/test_native_api.py::test_native_run_read_exposes_persisted_lifecycle_fields -q
```

Expected: FAIL with missing `created_at`, `started_at`, `finished_at`, or `latency_ms`.

- [ ] **Step 3: Extend API response models**

In `apps/server/dimoo_run/api/native/runs.py`, extend `RunRead`:

```python
from datetime import datetime

class RunRead(BaseModel):
    id: int
    tenant_id: int
    project_id: int
    agent_id: int
    agent_version_id: int
    deployment_id: int | None
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    thread_id: str | None = None
    idempotency_key: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latency_ms: int | None = None
```

In `_run_to_read()`, compute latency:

```python
def _run_to_read(run: NativeRun) -> RunRead:
    payload = run.__dict__.copy()
    payload["status"] = run.status.value
    started_at = payload.get("started_at")
    finished_at = payload.get("finished_at")
    payload["latency_ms"] = (
        int((finished_at - started_at).total_seconds() * 1000)
        if started_at is not None and finished_at is not None
        else None
    )
    return RunRead.model_validate(payload)
```

Add these fields to `NativeRun` in `apps/server/dimoo_run/api/native/runtime.py` if missing:

```python
started_at: datetime | None = None
finished_at: datetime | None = None
```

When `_run_from_model()` builds `NativeRun`, pass:

```python
started_at=run.started_at,
finished_at=run.finished_at,
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
uv run pytest tests/api/test_native_api.py::test_native_run_read_exposes_persisted_lifecycle_fields -q
```

Expected: PASS.

---

## Task 2: Persist Worker Lifecycle Timing And Attempt Latency

**Files:**
- Modify: `tests/runtime/test_sqlalchemy_worker_executor.py`
- Modify: `apps/server/dimoo_run/worker/executor.py`

- [ ] **Step 1: Write the failing worker timing assertion**

In `test_worker_executor_completes_sqlalchemy_run_attempt_and_task`, add:

```python
assert run_model.started_at is not None
assert run_model.finished_at is not None
assert task_model.started_at is not None
assert task_model.finished_at is not None
assert attempts[0].started_at is not None
assert attempts[0].finished_at is not None
assert attempts[0].latency_ms is not None
assert attempts[0].latency_ms >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/runtime/test_sqlalchemy_worker_executor.py::test_worker_executor_completes_sqlalchemy_run_attempt_and_task -q
```

Expected: FAIL on whichever timestamp/latency field is currently missing.

- [ ] **Step 3: Update executor lifecycle writes**

In `apps/server/dimoo_run/worker/executor.py`, locate the success path after a task is leased and before adapter invocation. Ensure it transitions the run and task to running before invoking:

```python
run = self.run_store.mark_running(task.run_id)
task = self.task_backend.mark_running(task.id, worker_id=self.worker_id)
attempt = self.run_store.start_attempt(
    run_id=task.run_id,
    task_id=task.id,
    worker_id=self.worker_id,
)
```

In the success terminal path, ensure the attempt is completed after output is saved:

```python
self.run_store.complete_attempt(attempt.id, status="succeeded")
self.task_backend.complete_task(task.id, status="succeeded")
self.run_store.complete_run(run.run_id, output=result.output)
```

If the existing store methods use different names, keep the existing method names and add the timestamp/latency writes at the equivalent points. The required database effect is:

- `Run.started_at` set once when execution begins.
- `Task.started_at` set once when execution begins.
- `RunAttempt.started_at` set when the attempt begins.
- `RunAttempt.finished_at` and `latency_ms` set when the attempt ends.
- `Task.finished_at` set on terminal task status.
- `Run.finished_at` set on terminal run status.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
uv run pytest tests/runtime/test_sqlalchemy_worker_executor.py::test_worker_executor_completes_sqlalchemy_run_attempt_and_task -q
```

Expected: PASS.

---

## Task 3: Map Real Lifecycle Fields Into Console

**Files:**
- Modify: `apps/console/tests/console-contract.test.mjs`
- Modify: `apps/console/src/api/generated/dimoorun.ts`
- Modify: `apps/console/src/api/types.ts`
- Modify: `apps/console/src/api/client.ts`
- Modify: `apps/console/src/pages/runs/RunsPage.vue`
- Modify: `apps/console/src/pages/runs/RunDetailPage.vue`

- [ ] **Step 1: Write failing Console contract test**

Add this test to `apps/console/tests/console-contract.test.mjs`:

```javascript
test("maps native lifecycle fields into runtime views", () => {
    const generatedClient = read("src/api/generated/dimoorun.ts");
    const types = read("src/api/types.ts");
    const client = read("src/api/client.ts");
    const runsPage = read("src/pages/runs/RunsPage.vue");
    const runDetail = read("src/pages/runs/RunDetailPage.vue");

    assert.match(generatedClient, /created_at: string/);
    assert.match(generatedClient, /started_at: string \| null/);
    assert.match(generatedClient, /finished_at: string \| null/);
    assert.match(generatedClient, /latency_ms: number \| null/);
    assert.match(types, /createdAt: string/);
    assert.match(types, /startedAt: string \| null/);
    assert.match(types, /finishedAt: string \| null/);
    assert.match(client, /createdAt: run\.created_at/);
    assert.match(client, /startedAt: run\.started_at/);
    assert.match(client, /finishedAt: run\.finished_at/);
    assert.match(client, /latencyMs: run\.latency_ms/);
    assert.match(runsPage, /formatDateTime\(run\.createdAt\)/);
    assert.match(runDetail, /formatDateTime\(currentRun\.startedAt\)/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/console
npm run test
```

Expected: FAIL on missing generated/type/client/view fields.

- [ ] **Step 3: Update generated client and Console domain types**

In `apps/console/src/api/generated/dimoorun.ts`, update `NativeRunRead`:

```ts
export type NativeRunRead = {
  id: ResourceId;
  agent_id: ResourceId;
  agent_version_id: ResourceId;
  deployment_id: ResourceId | null;
  status: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  thread_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  latency_ms: number | null;
};
```

In `apps/console/src/api/types.ts`, update `Run`:

```ts
createdAt: string;
startedAt: string | null;
finishedAt: string | null;
latencyMs: number | null;
```

In `apps/console/src/api/client.ts`, map fields:

```ts
createdAt: run.created_at,
startedAt: run.started_at,
finishedAt: run.finished_at,
latencyMs: run.latency_ms,
```

- [ ] **Step 4: Update views**

In `apps/console/src/pages/runs/RunsPage.vue`, import `formatDateTime`:

```ts
import { formatDateTime } from "../../utils/dateTime";
```

Add a created column:

```vue
<th>{{ t("createdAt") }}</th>
...
<td>{{ formatDateTime(run.createdAt) }}</td>
```

In `apps/console/src/pages/runs/RunDetailPage.vue`, import `formatDateTime` and add metadata:

```vue
<p><strong>{{ t("createdAt") }}</strong><br /><span class="mono">{{ formatDateTime(currentRun.createdAt) }}</span></p>
<p><strong>{{ t("startedAt") }}</strong><br /><span class="mono">{{ formatDateTime(currentRun.startedAt) }}</span></p>
<p><strong>{{ t("finishedAt") }}</strong><br /><span class="mono">{{ formatDateTime(currentRun.finishedAt) }}</span></p>
<p><strong>{{ t("latency") }}</strong><br /><span class="mono">{{ formatLatency(currentRun.latencyMs) }}</span></p>
```

Add:

```ts
function formatLatency(value: number | null): string {
  return typeof value === "number" ? `${value} ms` : "-";
}
```

- [ ] **Step 5: Run Console verification**

Run:

```powershell
cd apps/console
npm run test
npm run build
```

Expected: both commands PASS.

---

## Task 4: Replay Candidate Version Selection

**Files:**
- Modify: `tests/api/test_native_api.py`
- Modify: `apps/server/dimoo_run/api/native/runs.py`
- Modify: `apps/server/dimoo_run/api/native/runtime.py`
- Modify: `apps/console/src/api/generated/dimoorun.ts`
- Modify: `apps/console/src/api/client.ts`
- Modify: `apps/console/src/pages/replay/ReplayPage.vue`
- Modify: `apps/console/tests/console-contract.test.mjs`

- [ ] **Step 1: Write failing API test**

Add:

```python
def test_native_replay_can_target_candidate_version() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, source_version_id = create_agent_with_version(client, key)
    candidate = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={"version": "0.2.0", "package_uri": "file://support-agent-v2"},
    )
    assert candidate.status_code == 201
    source = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "replay me"}},
    ).json()

    replay = client.post(
        f"/v1/runs/{source['run_id']}/replay",
        headers=auth_headers(key),
        json={"agent_version_id": candidate.json()["id"]},
    )

    assert replay.status_code == 200
    assert replay.json()["agent_version_id"] != source_version_id
    assert replay.json()["agent_version_id"] == candidate.json()["id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/api/test_native_api.py::test_native_replay_can_target_candidate_version -q
```

Expected: FAIL because the replay endpoint does not parse `agent_version_id`.

- [ ] **Step 3: Add replay request model**

In `apps/server/dimoo_run/api/native/runs.py`:

```python
class ReplayRunRequest(BaseModel):
    agent_version_id: int | None = None
```

Change endpoint signature:

```python
def replay_run(
    run_id: int,
    payload: ReplayRunRequest | None = None,
    ...
) -> RunRead | JSONResponse:
```

Call:

```python
replay = runtime.replay_run(
    run,
    agent_version_id=payload.agent_version_id if payload else None,
)
```

In both runtime store classes, change:

```python
def replay_run(
    self,
    source_run: NativeRun,
    *,
    agent_version_id: int | None = None,
) -> NativeRun:
```

Resolve:

```python
agent_version = (
    self.get_version_by_id(source_run.agent_id, agent_version_id)
    if agent_version_id is not None
    else self.get_version_by_id(source_run.agent_id, source_run.agent_version_id)
)
```

If missing, raise `KeyError(source_run.id)`. In the route catch `KeyError` and return:

```python
return error_response(
    status_code=404,
    error_code="agent_version_not_found",
    message="Replay candidate agent version was not found.",
    request_id=x_request_id,
    details={"agent_version_id": payload.agent_version_id if payload else None},
)
```

- [ ] **Step 4: Run API test to verify it passes**

Run:

```powershell
uv run pytest tests/api/test_native_api.py::test_native_replay_can_target_candidate_version -q
```

Expected: PASS.

- [ ] **Step 5: Add Console contract for candidate selection**

Extend `turns replay into a real console workflow` in `apps/console/tests/console-contract.test.mjs`:

```javascript
assert.match(replay, /selectedAgentVersionId/);
assert.match(replay, /consoleClient\.replayRun/);
assert.match(replay, /agent_version_id/);
```

Expected initial result: FAIL until Console client and page are updated.

- [ ] **Step 6: Update Console client and Replay page**

In `apps/console/src/api/generated/dimoorun.ts`, add:

```ts
replayRun: (runId: ResourceId, payload: { agent_version_id?: ResourceId | null }) =>
  request<NativeRunRead>(options, `/v1/runs/${runId}/replay`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
```

In `apps/console/src/api/client.ts`, add live method:

```ts
async replayRun(runId: ResourceId, agentVersionId: ResourceId | null): Promise<Run> {
  const payload = await nativeClient(crypto.randomUUID()).replayRun(runId, {
    agent_version_id: agentVersionId,
  });
  return mapNativeRun(payload);
}
```

Add demo method that returns a cloned run with a new id.

In `ReplayPage.vue`, replace `consoleClient.controlRun(selectedRunId, "replay")` with:

```ts
return consoleClient.replayRun(selectedRunId, selectedAgentVersionId.value);
```

Add a candidate select:

```vue
<select v-model.number="selectedAgentVersionId" class="select">
  <option :value="selectedRun?.version ? Number(selectedRun.version) : null">
    {{ selectedRun ? `${selectedRun.agent}@${selectedRun.version}` : "-" }}
  </option>
</select>
```

- [ ] **Step 7: Run frontend verification**

Run:

```powershell
cd apps/console
npm run test
npm run build
```

Expected: PASS.

---

## Task 5: Worker Failure And Dead-Letter Contract

**Files:**
- Modify: `tests/runtime/test_sqlalchemy_worker_executor.py`
- Modify: `apps/server/dimoo_run/worker/executor.py`

- [ ] **Step 1: Add missing adapter dead-letter test**

Add:

```python
@pytest.mark.asyncio
async def test_worker_executor_dead_letters_missing_adapter_without_crashing() -> None:
    session = make_session()
    run_store = SQLAlchemyRunStore(session)
    task_backend = SQLAlchemyTaskBackend(session)
    manager = RunManager(run_store=run_store, task_backend=task_backend)
    run, task_id = await manager.create_run_task(
        tenant_id=1,
        project_id=1,
        agent_id=1,
        agent_version_id=1,
        deployment_id=None,
        input_data={"message": "hello"},
    )
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=ReplayBuffer(),
        adapters={},
        agent_specs={
            1: AgentRuntimeSpec(
                adapter="missing",
                package_uri="memory://fake",
                manifest={},
                runtime_config={},
            )
        },
    )

    result = await executor.execute_once(queue="default")

    run_model = session.get(Run, run.run_id)
    task_model = session.get(Task, task_id)
    attempts = list(session.query(RunAttempt).filter(RunAttempt.run_id == run.run_id))
    assert result is not None
    assert result.status == "failed"
    assert run_model is not None
    assert run_model.status == "failed"
    assert task_model is not None
    assert task_model.status == "dead_letter"
    assert task_model.dead_letter_reason == "worker_adapter_not_found"
    assert attempts[0].status == "failed"
```

- [ ] **Step 2: Run test to verify it fails if behavior regressed**

Run:

```powershell
uv run pytest tests/runtime/test_sqlalchemy_worker_executor.py::test_worker_executor_dead_letters_missing_adapter_without_crashing -q
```

Expected: PASS if previous defensive behavior is present; FAIL if any path crashes or leaves task leased/running.

- [ ] **Step 3: Fix executor if needed**

If the test fails, update `apps/server/dimoo_run/worker/executor.py` so missing adapter/spec paths call the same terminal failure helper used by invocation failures. The terminal effect must be:

- `Run.status == "failed"`
- `Task.status == "dead_letter"`
- `Task.dead_letter_reason == "worker_adapter_not_found"` or `"worker_agent_version_not_found"`
- `RunAttempt.status == "failed"`
- an error event is appended

- [ ] **Step 4: Run runtime executor test file**

Run:

```powershell
uv run pytest tests/runtime/test_sqlalchemy_worker_executor.py -q
```

Expected: PASS.

---

## Task 6: Core Production Verification Gate

**Files:**
- No code changes unless verification fails.

- [ ] **Step 1: Run backend core suite**

Run:

```powershell
uv run pytest tests/worker/test_durable_worker_execution.py tests/worker/test_worker_loop_durable_backend.py tests/runtime/test_sqlalchemy_worker_executor.py tests/server/test_worker_entrypoint.py tests/api/test_native_api.py -q
```

Expected: PASS with all listed tests.

- [ ] **Step 2: Run frontend core suite**

Run:

```powershell
cd apps/console
npm run test
npm run build
```

Expected: PASS for contract tests and production build.

- [ ] **Step 3: Run focused lint**

Run:

```powershell
uv run ruff check apps/server/dimoo_run/api/native/runs.py apps/server/dimoo_run/api/native/runtime.py apps/server/dimoo_run/worker/executor.py tests/api/test_native_api.py tests/runtime/test_sqlalchemy_worker_executor.py
```

Expected: PASS.

- [ ] **Step 4: Document completion**

Append a completion note to `docs/history/implementation-update-2026-06-01.md`:

```markdown
## Production Hardening Completion

- Native run lifecycle fields are exposed through API and Console.
- Worker success/failure paths persist run/task/attempt timestamps and attempt latency.
- Replay supports candidate version selection and creates durable run/task/event records.
- Core backend and Console verification commands pass.
```

---

## Self-Review

- Spec coverage: The plan covers lifecycle metrics, worker terminal guarantees, Console real-data mapping, Replay candidate selection, and verification gates.
- Placeholder scan: No steps rely on `TODO`, `TBD`, "similar to", or unspecified tests.
- Type consistency: Backend uses `created_at`, `started_at`, `finished_at`, and `latency_ms`; Console maps them to `createdAt`, `startedAt`, `finishedAt`, and `latencyMs`.
- Scope check: Enterprise/admin shells remain outside this plan. This plan is limited to the production-grade Agent run execution loop.
