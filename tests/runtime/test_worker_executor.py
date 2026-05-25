from collections.abc import AsyncIterator
from typing import Any

import pytest
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult
from dimoo_run.runtime.run_manager import InMemoryRunStore, RunManager
from dimoo_run.scheduler.in_memory import InMemoryTaskBackend
from dimoo_run.streaming.replay_buffer import ReplayBuffer
from dimoo_run.worker.executor import AgentRuntimeSpec, WorkerExecutor


class FakeAdapter:
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
            output={"echo": input_data["message"], "run_id": context.run_id},
            events=[AgentEvent(type="agent.message", payload={"text": "done"})],
        )

    async def stream(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AsyncIterator[AgentEvent]:
        _ = agent, input_data, context
        yield AgentEvent(type="agent.stream_chunk", payload={"delta": "hello"})

    async def resume(
        self,
        agent: Any,
        run_id: str,
        payload: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = agent, run_id, payload, context
        raise NotImplementedError

    async def cancel(self, run_id: str, context: RuntimeContext) -> None:
        _ = run_id, context


class FailingAdapter(FakeAdapter):
    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = agent, input_data, context
        raise RuntimeError("boom")


class StreamOnlyAdapter(FakeAdapter):
    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = agent, input_data, context
        raise AssertionError("stream mode must not call invoke")


class FailingStreamAdapter(FakeAdapter):
    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = agent, input_data, context
        raise AssertionError("stream mode must not call invoke")

    async def stream(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AsyncIterator[AgentEvent]:
        _ = agent, input_data, context
        yield AgentEvent(type="agent.stream_chunk", payload={"delta": "first"})
        raise RuntimeError("stream broke")


async def create_task(
    run_store: InMemoryRunStore,
    task_backend: InMemoryTaskBackend,
    *,
    max_attempts: int = 3,
) -> str:
    manager = RunManager(run_store=run_store, task_backend=task_backend)
    _run, task_id = await manager.create_run_task(
        tenant_id="tenant_1",
        project_id="project_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        deployment_id="deployment_1",
        input_data={"message": "hello"},
    )
    task_backend.tasks[task_id].max_attempts = max_attempts
    task_backend.tasks[task_id].payload["max_attempts"] = max_attempts
    return task_id


@pytest.mark.asyncio
async def test_worker_executor_streams_adapter_events_when_requested() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    replay_buffer = ReplayBuffer()
    task_id = await create_task(run_store, task_backend)
    task_backend.tasks[task_id].payload["execution_mode"] = "stream"
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=replay_buffer,
        adapters={"fake": StreamOnlyAdapter()},  # type: ignore[dict-item]
        agent_specs={
            "version_1": AgentRuntimeSpec(
                adapter="fake",
                package_uri="memory://fake",
                manifest={"runtime": {"entrypoint": "agent:create"}},
                runtime_config={},
            )
        },
    )

    result = await executor.execute_once(queue="default")

    run_id = task_backend.tasks[task_id].run_id
    assert result is not None
    assert run_store.runs[run_id].status == "succeeded"
    assert [event.type for event in replay_buffer.replay(run_id)] == [
        "attempt.started",
        "agent.stream_chunk",
        "run.completed",
        "stream.completed",
    ]


@pytest.mark.asyncio
async def test_worker_executor_persists_stream_events_before_stream_failure() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    replay_buffer = ReplayBuffer()
    task_id = await create_task(run_store, task_backend)
    task_backend.tasks[task_id].payload["execution_mode"] = "stream"
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=replay_buffer,
        adapters={"fake": FailingStreamAdapter()},  # type: ignore[dict-item]
        agent_specs={
            "version_1": AgentRuntimeSpec(
                adapter="fake",
                package_uri="memory://fake",
                manifest={"runtime": {"entrypoint": "agent:create"}},
                runtime_config={},
            )
        },
    )

    result = await executor.execute_once(queue="default")

    run_id = task_backend.tasks[task_id].run_id
    assert result is not None
    assert [event.type for event in replay_buffer.replay(run_id)] == [
        "attempt.started",
        "agent.stream_chunk",
        "attempt.failed",
        "task.retrying",
    ]


@pytest.mark.asyncio
async def test_worker_executor_runs_adapter_and_persists_events() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    replay_buffer = ReplayBuffer()
    task_id = await create_task(run_store, task_backend)
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=replay_buffer,
        adapters={"fake": FakeAdapter()},  # type: ignore[dict-item]
        agent_specs={
            "version_1": AgentRuntimeSpec(
                adapter="fake",
                package_uri="memory://fake",
                manifest={"runtime": {"entrypoint": "agent:create"}},
                runtime_config={"temperature": 0},
            )
        },
    )

    result = await executor.execute_once(queue="default")

    run_id = task_backend.tasks[task_id].run_id
    assert result is not None
    assert run_store.runs[run_id].status == "succeeded"
    assert run_store.runs[run_id].output == {"echo": "hello", "run_id": run_id}
    assert task_backend.tasks[task_id].status == "succeeded"
    assert [event.type for event in replay_buffer.replay(run_id)] == [
        "attempt.started",
        "agent.message",
        "run.completed",
        "stream.completed",
    ]


@pytest.mark.asyncio
async def test_worker_executor_retries_adapter_failure() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    task_id = await create_task(run_store, task_backend, max_attempts=3)
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=ReplayBuffer(),
        adapters={"fake": FailingAdapter()},  # type: ignore[dict-item]
        agent_specs={
            "version_1": AgentRuntimeSpec(
                adapter="fake",
                package_uri="memory://fake",
                manifest={"runtime": {"entrypoint": "agent:create"}},
                runtime_config={},
            )
        },
    )

    result = await executor.execute_once(queue="default")

    run_id = task_backend.tasks[task_id].run_id
    assert result is not None
    assert run_store.runs[run_id].status == "running"
    assert task_backend.tasks[task_id].status == "queued"
    assert [event.type for event in executor.replay_buffer.replay(run_id)] == [
        "attempt.started",
        "attempt.failed",
        "task.retrying",
    ]


@pytest.mark.asyncio
async def test_worker_executor_dead_letters_after_retry_exhaustion() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    task_id = await create_task(run_store, task_backend, max_attempts=1)
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=ReplayBuffer(),
        adapters={"fake": FailingAdapter()},  # type: ignore[dict-item]
        agent_specs={
            "version_1": AgentRuntimeSpec(
                adapter="fake",
                package_uri="memory://fake",
                manifest={"runtime": {"entrypoint": "agent:create"}},
                runtime_config={},
            )
        },
    )

    result = await executor.execute_once(queue="default")

    run_id = task_backend.tasks[task_id].run_id
    assert result is not None
    assert run_store.runs[run_id].status == "failed"
    assert task_backend.tasks[task_id].status == "dead_letter"
