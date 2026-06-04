# Real Agent Execution Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the smallest durable worker execution loop from queued Run/Task to persisted Attempt, Events, terminal Task status, and terminal Run status.

**Architecture:** Add a focused durable worker wiring module that adapts SQLAlchemy rows into the existing `WorkerExecutor` contract. Keep `WorkerExecutor`, `SQLAlchemyRunStore`, and `SQLAlchemyTaskBackend` as the core runtime primitives, and add only the glue needed to resolve `AgentVersion` package metadata and persist replay-buffer events into the event table.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest, existing DimooRun runtime and scheduler modules.

---

## File Structure

- Create `apps/server/dimoo_run/worker/durable.py`
  - Owns durable worker dependency wiring: adapter registry, agent spec lookup, event sink, one-shot execution.
- Modify `apps/server/dimoo_run/worker/loop.py`
  - Let `WorkerLoop` call a real executor callback before falling back to lease-only behavior.
- Modify `apps/worker/dimoo_run_worker/main.py`
  - Add one-shot durable execution as the default CLI behavior.
- Modify `apps/server/dimoo_run/api/native/runs.py`
  - Return real RunAttempt records for `/runs/{run_id}/attempts`.
- Modify `apps/server/dimoo_run/streaming/replay_buffer.py` only if needed
  - Add a small callback hook or subclass-friendly point for durable event persistence.
- Modify `tests/runtime/test_sqlalchemy_worker_executor.py`
  - Fix numeric IDs and assert persisted durable behavior still passes.
- Create `tests/worker/test_durable_worker_execution.py`
  - Cover durable worker one-shot execution through database rows.
- Modify `tests/worker/test_worker_loop_durable_backend.py`
  - Update old numeric ID assumptions and add callback execution behavior.
- Modify `tests/api/test_native_api.py`
  - Add attempts API assertion after inserting a real attempt.

---

### Task 1: Add Durable Worker Wiring Test

**Files:**
- Create: `tests/worker/test_durable_worker_execution.py`
- Later modify: `apps/server/dimoo_run/worker/durable.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from typing import Any

from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult
from dimoo_run.domain.models import Agent, AgentVersion, Run, RunAttempt, Task
from dimoo_run.persistence.database import Base
from dimoo_run.worker.durable import DurableWorkerExecutorFactory, execute_durable_once
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class FakeDurableAdapter:
    framework = "fake"

    async def load(
        self,
        package_uri: str,
        manifest: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        return {"package_uri": package_uri, "manifest": manifest, "runtime_config": runtime_config}

    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        return AgentResult(
            output={"echo": input_data["message"], "version": agent["manifest"]["name"]},
            events=[AgentEvent(type="agent.message", payload={"text": "done"})],
        )


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.asyncio
async def test_execute_durable_once_runs_queued_task_and_persists_runtime_state() -> None:
    session = make_session()
    agent = Agent(tenant_id=1, project_id=1, name="support", status="active")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version="0.1.0",
        package_uri="memory://support",
        framework="fake",
        adapter="fake",
        entrypoint="agent:create",
        manifest_json={"name": "support-v1"},
        capabilities_json={},
        status="ready",
    )
    session.add(version)
    session.flush()
    run = Run(
        tenant_id=1,
        project_id=1,
        agent_id=agent.id,
        agent_version_id=version.id,
        input_ref='json:{"message":"hello"}',
    )
    session.add(run)
    session.flush()
    task = Task(run_id=run.id, tenant_id=1, project_id=1, queue="default")
    session.add(task)
    session.flush()

    result = await execute_durable_once(
        session=session,
        worker_id="worker_1",
        queue="default",
        adapters={"fake": FakeDurableAdapter()},
    )

    assert result is not None
    assert result.status == "succeeded"
    session.refresh(run)
    session.refresh(task)
    attempts = session.query(RunAttempt).filter(RunAttempt.run_id == run.id).all()
    assert run.status == "succeeded"
    assert run.output_ref == 'json:{"echo":"hello","version":"support-v1"}'
    assert task.status == "succeeded"
    assert len(attempts) == 1
    assert attempts[0].status == "succeeded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/worker/test_durable_worker_execution.py -q`

Expected: FAIL with `ModuleNotFoundError` for `dimoo_run.worker.durable`.

- [ ] **Step 3: Implement minimal durable worker module**

Create `apps/server/dimoo_run/worker/durable.py` with:

```python
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.adapters.base.contract import AgentAdapter
from dimoo_run.domain.models import AgentVersion
from dimoo_run.runtime.sqlalchemy_run_store import SQLAlchemyRunStore
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from dimoo_run.streaming.replay_buffer import ReplayBuffer
from dimoo_run.worker.executor import AgentRuntimeSpec, WorkerExecutionResult, WorkerExecutor


class DurableWorkerExecutorFactory:
    def __init__(
        self,
        *,
        session: Session,
        worker_id: str,
        adapters: Mapping[str, AgentAdapter],
    ) -> None:
        self.session = session
        self.worker_id = worker_id
        self.adapters = dict(adapters)

    def build(self) -> WorkerExecutor:
        versions = self.session.scalars(
            select(AgentVersion).where(AgentVersion.is_deleted.is_(False))
        )
        specs = {
            version.id: AgentRuntimeSpec(
                adapter=version.adapter,
                package_uri=version.package_uri,
                manifest=version.manifest_json or {},
                runtime_config={},
            )
            for version in versions
        }
        return WorkerExecutor(
            worker_id=self.worker_id,
            task_backend=SQLAlchemyTaskBackend(self.session),
            run_store=SQLAlchemyRunStore(self.session),
            replay_buffer=ReplayBuffer(),
            adapters=self.adapters,
            agent_specs=specs,
        )


async def execute_durable_once(
    *,
    session: Session,
    worker_id: str,
    queue: str = "default",
    adapters: Mapping[str, AgentAdapter],
    lease_seconds: int = 30,
) -> WorkerExecutionResult | None:
    executor = DurableWorkerExecutorFactory(
        session=session,
        worker_id=worker_id,
        adapters=adapters,
    ).build()
    return await executor.execute_once(queue=queue, lease_seconds=lease_seconds)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/worker/test_durable_worker_execution.py -q`

Expected: PASS.

---

### Task 2: Persist Worker Events To Event Table

**Files:**
- Modify: `apps/server/dimoo_run/worker/durable.py`
- Test: `tests/worker/test_durable_worker_execution.py`

- [ ] **Step 1: Extend the failing test**

Add imports and assertions:

```python
from dimoo_run.domain.models import Event

events = session.query(Event).filter(Event.run_id == run.id).order_by(Event.sequence).all()
assert [event.type for event in events] == [
    "attempt.started",
    "agent.message",
    "run.completed",
    "stream.completed",
]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/worker/test_durable_worker_execution.py -q`

Expected: FAIL because the durable worker uses an in-memory replay buffer only.

- [ ] **Step 3: Implement durable replay buffer sink**

In `apps/server/dimoo_run/worker/durable.py`, add:

```python
from dimoo_run.core.events import AgentEvent
from dimoo_run.persistence.repositories import EventRepository
from dimoo_run.streaming.replay_buffer import ReplayBuffer


class SQLAlchemyReplayBuffer(ReplayBuffer):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def append(
        self,
        run_id: int,
        attempt_id: int | None,
        event: AgentEvent,
    ) -> AgentEvent:
        appended = super().append(run_id, attempt_id, event)
        run = SQLAlchemyRunStore(self.session).get_run(run_id)
        EventRepository(self.session).append(
            event_id=appended.event_id or f"event_{appended.sequence}",
            run_id=run_id,
            attempt_id=attempt_id,
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            type=appended.type,
            payload=appended.payload,
            framework=appended.framework,
            visibility_level=appended.visibility_level,
        )
        self.session.flush()
        return appended
```

Then change the factory to pass `SQLAlchemyReplayBuffer(self.session)` instead of `ReplayBuffer()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/worker/test_durable_worker_execution.py -q`

Expected: PASS with persisted events in sequence order.

---

### Task 3: Return Real Run Attempts From Native API

**Files:**
- Modify: `tests/api/test_native_api.py`
- Modify: `apps/server/dimoo_run/api/native/runs.py`

- [ ] **Step 1: Write failing API test**

Append to `tests/api/test_native_api.py`:

```python
def test_native_run_attempts_endpoint_returns_persisted_attempts() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)
    task_body = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "hello"}},
    ).json()

    from dimoo_run.api.native.dependencies import _session_factory
    from dimoo_run.core.config import Settings
    from dimoo_run.domain.models import RunAttempt

    session_factory = _session_factory(Settings.from_env().database.url)
    session = session_factory()
    try:
        session.add(
            RunAttempt(
                run_id=task_body["run_id"],
                task_id=task_body["task_id"],
                attempt_no=1,
                worker_id="worker_1",
                status="succeeded",
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(
        f"/v1/runs/{task_body['run_id']}/attempts",
        headers=auth_headers(key),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "run_id": task_body["run_id"],
            "task_id": task_body["task_id"],
            "attempt_no": 1,
            "worker_id": "worker_1",
            "status": "succeeded",
            "error": None,
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_native_api.py::test_native_run_attempts_endpoint_returns_persisted_attempts -q`

Expected: FAIL because the endpoint returns `[]`.

- [ ] **Step 3: Implement endpoint response**

In `apps/server/dimoo_run/api/native/runs.py`, add a response model:

```python
class RunAttemptRead(BaseModel):
    id: int
    run_id: int
    task_id: int | None
    attempt_no: int
    worker_id: str | None
    status: str
    error: str | None = None
```

Import `RunAttempt` and `select`, then change the endpoint to query attempts when runtime is SQLAlchemy-backed:

```python
@router.get("/runs/{run_id}/attempts", response_model=list[RunAttemptRead])
def list_run_attempts(...) -> list[RunAttemptRead] | JSONResponse:
    run = _find_run(...)
    if isinstance(run, JSONResponse):
        return run
    if isinstance(runtime, SQLAlchemyNativeRuntimeStore):
        attempts = runtime.session.scalars(
            select(RunAttempt)
            .where(RunAttempt.run_id == run.id, RunAttempt.is_deleted.is_(False))
            .order_by(RunAttempt.attempt_no)
        )
        return [RunAttemptRead.model_validate(attempt.__dict__) for attempt in attempts]
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_native_api.py::test_native_run_attempts_endpoint_returns_persisted_attempts -q`

Expected: PASS.

---

### Task 4: Let WorkerLoop Execute Real Work

**Files:**
- Modify: `tests/worker/test_worker_loop_durable_backend.py`
- Modify: `apps/server/dimoo_run/worker/loop.py`

- [ ] **Step 1: Write failing loop callback test**

Add to `tests/worker/test_worker_loop_durable_backend.py`:

```python
class FakeExecuteOnce:
    def __init__(self) -> None:
        self.called = False

    async def __call__(self, *, queue: str, lease_seconds: int) -> object:
        self.called = True
        assert queue == "default"
        assert lease_seconds == 30
        return object()


def test_worker_loop_uses_executor_callback_before_lease_only_path() -> None:
    execute_once = FakeExecuteOnce()
    loop = WorkerLoop(worker_id="worker_1", execute_once=execute_once)

    heartbeat = loop.run_once()

    assert heartbeat.status == "executed"
    assert execute_once.called is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/worker/test_worker_loop_durable_backend.py::test_worker_loop_uses_executor_callback_before_lease_only_path -q`

Expected: FAIL because `WorkerLoop.__init__` does not accept `execute_once`.

- [ ] **Step 3: Implement callback path**

In `apps/server/dimoo_run/worker/loop.py`, add constructor parameter:

```python
execute_once: Any | None = None,
```

Set `self.execute_once = execute_once`, then before the lease-only block in `run_once()`:

```python
if self.execute_once is not None:
    import anyio

    result = anyio.run(
        self.execute_once,
        queue=self.queue,
        lease_seconds=self.lease_seconds,
    )
    if result is not None:
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="executed")
        return self.heartbeat
```

- [ ] **Step 4: Run loop tests**

Run: `uv run pytest tests/worker/test_worker_loop_durable_backend.py -q`

Expected: PASS.

---

### Task 5: Wire Worker CLI One-Shot Execution

**Files:**
- Modify: `tests/server/test_worker_entrypoint.py`
- Modify: `apps/worker/dimoo_run_worker/main.py`

- [ ] **Step 1: Write failing entrypoint test**

Add to `tests/server/test_worker_entrypoint.py`:

```python
def test_worker_entrypoint_exposes_one_shot_mode() -> None:
    from apps.worker.dimoo_run_worker import main

    assert hasattr(main, "run_once")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_worker_entrypoint.py::test_worker_entrypoint_exposes_one_shot_mode -q`

Expected: FAIL if `run_once` is not exposed.

- [ ] **Step 3: Add one-shot function**

In `apps/worker/dimoo_run_worker/main.py`, add:

```python
def run_once() -> str:
    from dimoo_run.worker.loop import WorkerLoop

    heartbeat = WorkerLoop().run_once()
    return heartbeat.status
```

Then change `main()` to call `run_once()` and print the returned status.

- [ ] **Step 4: Run entrypoint test**

Run: `uv run pytest tests/server/test_worker_entrypoint.py -q`

Expected: PASS.

---

### Task 6: Focused Regression Verification

**Files:**
- No code changes unless a regression is found.

- [ ] **Step 1: Run focused runtime and worker tests**

Run:

```powershell
uv run pytest tests/worker/test_durable_worker_execution.py tests/worker/test_worker_loop_durable_backend.py tests/runtime/test_sqlalchemy_worker_executor.py -q
```

Expected: PASS.

- [ ] **Step 2: Run focused native API tests**

Run:

```powershell
uv run pytest tests/api/test_native_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Run formatting/type smoke if touched imports require it**

Run:

```powershell
uv run ruff check apps/server tests/worker tests/runtime tests/api
```

Expected: PASS.

---

## Self-Review

- Spec coverage: The plan covers durable task execution, agent version spec resolution, attempts API, persisted events, and one-shot worker execution.
- Placeholder scan: No task uses "TBD", "TODO", or unspecified implementation steps.
- Type consistency: `agent_version_id` is consistently numeric, `AgentRuntimeSpec` keys use `int`, and tests use `RunAttempt`, `Run`, `Task`, and `Event` model fields already present in the repository.

## Execution Status - 2026-06-01

This plan has been executed as the core alpha/beta runtime closure:

- `apps/server/dimoo_run/worker/durable.py` was added for SQLAlchemy-backed durable worker wiring.
- Worker entrypoint one-shot execution is exposed through `apps/worker/dimoo_run_worker/main.py`.
- `WorkerLoop` supports a real executor callback path.
- Durable worker events are persisted to the `Event` table.
- `/v1/runs/{run_id}/attempts` returns real persisted attempts for SQLAlchemy-backed runtime.
- Console Run Detail now reads real runs, events, attempts, input, output, and error.
- Replay now creates a new run/task and emits `run.replayed`.

Latest focused verification for this closure:

```powershell
uv run pytest tests/worker/test_durable_worker_execution.py tests/worker/test_worker_loop_durable_backend.py tests/runtime/test_sqlalchemy_worker_executor.py tests/server/test_worker_entrypoint.py tests/api/test_native_api.py -q
uv run ruff check apps/server/dimoo_run/api/native/runs.py apps/server/dimoo_run/api/native/runtime.py tests/api/test_native_api.py
cd apps/console
npm run test
npm run build
```
