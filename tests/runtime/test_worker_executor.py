import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from dimoo_run.adapters.base.contract import CapabilityNotSupportedError
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult
from dimoo_run.runtime.run_manager import InMemoryRunStore, RunManager
from dimoo_run.scheduler.in_memory import InMemoryTaskBackend, StaleFencingTokenError
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


class TrackingCancelAdapter(FakeAdapter):
    def __init__(self) -> None:
        self.cancelled_run_id: str | None = None

    async def cancel(self, run_id: str, context: RuntimeContext) -> None:
        _ = context
        self.cancelled_run_id = run_id


class UnsupportedCancelAdapter(FakeAdapter):
    async def cancel(self, run_id: str, context: RuntimeContext) -> None:
        _ = run_id, context
        raise CapabilityNotSupportedError("cancel", self.framework)


class SlowAdapter(FakeAdapter):
    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = agent, input_data, context
        await asyncio.sleep(1)
        return AgentResult(output={"late": True})


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


class RuntimeConfigCapturingAdapter(FakeAdapter):
    def __init__(self) -> None:
        self.loaded_runtime_config: dict[str, Any] | None = None

    async def load(
        self,
        package_uri: str,
        manifest: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        self.loaded_runtime_config = runtime_config
        return await super().load(package_uri, manifest, runtime_config)


class StaleCompleteBackend(InMemoryTaskBackend):
    def assert_can_complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        _ = task_id, worker_id, fencing_token
        raise StaleFencingTokenError("stale")

    async def complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        _ = task_id, worker_id, fencing_token
        raise StaleFencingTokenError("stale")


class StaleAfterFirstFencingBackend(InMemoryTaskBackend):
    def __init__(self) -> None:
        super().__init__()
        self.assert_calls = 0

    def assert_can_complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        self.assert_calls += 1
        if self.assert_calls > 1:
            raise StaleFencingTokenError("stale")
        super().assert_can_complete(task_id, worker_id, fencing_token)


class FailingCompleteRunStore(InMemoryRunStore):
    def complete_run(self, run_id: str, output: dict[str, Any]) -> None:
        _ = run_id, output
        raise RuntimeError("run store unavailable")


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
async def test_worker_executor_applies_task_override_config_to_adapter_runtime_config() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    replay_buffer = ReplayBuffer()
    manager = RunManager(run_store=run_store, task_backend=task_backend)
    _run, task_id = await manager.create_run_task(
        tenant_id="tenant_1",
        project_id="project_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        deployment_id="deployment_1",
        input_data={"message": "hello"},
        override_config={"temperature": 0, "model": "candidate"},
    )
    adapter = RuntimeConfigCapturingAdapter()
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=replay_buffer,
        adapters={"fake": adapter},  # type: ignore[dict-item]
        agent_specs={
            "version_1": AgentRuntimeSpec(
                adapter="fake",
                package_uri="memory://fake",
                manifest={"runtime": {"entrypoint": "agent:create"}},
                runtime_config={"temperature": 1, "timeout": 30},
            )
        },
    )

    await executor.execute_once(queue="default")

    assert task_backend.tasks[task_id].status == "succeeded"
    assert adapter.loaded_runtime_config == {
        "temperature": 0,
        "timeout": 30,
        "model": "candidate",
    }


@pytest.mark.asyncio
async def test_worker_executor_does_not_mark_run_failed_on_stale_complete() -> None:
    run_store = InMemoryRunStore()
    task_backend = StaleCompleteBackend()
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
                runtime_config={},
            )
        },
    )

    with pytest.raises(StaleFencingTokenError):
        await executor.execute_once(queue="default")

    run_id = task_backend.tasks[task_id].run_id
    assert run_store.runs[run_id].status == "running"
    assert list(run_store.attempts.values())[0].status == "running"
    assert "run.failed" not in [event.type for event in replay_buffer.replay(run_id)]


@pytest.mark.asyncio
async def test_worker_executor_does_not_fail_attempt_after_stale_adapter_error() -> None:
    run_store = InMemoryRunStore()
    task_backend = StaleAfterFirstFencingBackend()
    replay_buffer = ReplayBuffer()
    task_id = await create_task(run_store, task_backend)
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=replay_buffer,
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

    with pytest.raises(StaleFencingTokenError):
        await executor.execute_once(queue="default")

    run_id = task_backend.tasks[task_id].run_id
    assert run_store.runs[run_id].status == "running"
    assert list(run_store.attempts.values())[0].status == "running"
    assert [event.type for event in replay_buffer.replay(run_id)] == ["attempt.started"]


@pytest.mark.asyncio
async def test_worker_executor_does_not_complete_task_before_run_success_is_persisted() -> None:
    run_store = FailingCompleteRunStore()
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
                runtime_config={},
            )
        },
    )

    with pytest.raises(RuntimeError, match="run store unavailable"):
        await executor.execute_once(queue="default")

    assert task_backend.tasks[task_id].status == "running"


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


@pytest.mark.asyncio
async def test_worker_executor_calls_adapter_cancel_when_supported() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    task_id = await create_task(run_store, task_backend)
    run_id = task_backend.tasks[task_id].run_id
    adapter = TrackingCancelAdapter()
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=ReplayBuffer(),
        adapters={"fake": adapter},  # type: ignore[dict-item]
        agent_specs={
            "version_1": AgentRuntimeSpec(
                adapter="fake",
                package_uri="memory://fake",
                manifest={"runtime": {"entrypoint": "agent:create"}},
                runtime_config={},
            )
        },
    )

    status = await executor.cancel_run(run_id, task_id=task_id)

    assert status == "adapter_cancelled"
    assert adapter.cancelled_run_id == run_id
    assert executor.replay_buffer.replay(run_id)[0].payload == {
        "status": "adapter_cancelled",
        "task_id": task_id,
    }


@pytest.mark.asyncio
async def test_worker_executor_marks_cancel_best_effort_when_unsupported() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    task_id = await create_task(run_store, task_backend)
    run_id = task_backend.tasks[task_id].run_id
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=ReplayBuffer(),
        adapters={"fake": UnsupportedCancelAdapter()},  # type: ignore[dict-item]
        agent_specs={
            "version_1": AgentRuntimeSpec(
                adapter="fake",
                package_uri="memory://fake",
                manifest={"runtime": {"entrypoint": "agent:create"}},
                runtime_config={},
            )
        },
    )

    status = await executor.cancel_run(run_id, task_id=task_id)

    assert status == "best_effort"
    assert executor.replay_buffer.replay(run_id)[0].payload["status"] == "best_effort"


@pytest.mark.asyncio
async def test_worker_executor_marks_run_timeout_after_retry_exhaustion() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    task_id = await create_task(run_store, task_backend, max_attempts=1)
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=ReplayBuffer(),
        adapters={"fake": SlowAdapter()},  # type: ignore[dict-item]
        agent_specs={
            "version_1": AgentRuntimeSpec(
                adapter="fake",
                package_uri="memory://fake",
                manifest={"runtime": {"entrypoint": "agent:create"}},
                runtime_config={"timeout_seconds": 0.01},
            )
        },
    )

    result = await executor.execute_once(queue="default")

    run_id = task_backend.tasks[task_id].run_id
    assert result is not None
    assert result.status == "timeout"
    assert run_store.runs[run_id].status == "timeout"
    assert list(run_store.attempts.values())[0].status == "timeout"
    assert task_backend.tasks[task_id].status == "dead_letter"
    assert [event.type for event in executor.replay_buffer.replay(run_id)] == [
        "attempt.started",
        "attempt.timeout",
        "run.timeout",
        "stream.failed",
    ]
