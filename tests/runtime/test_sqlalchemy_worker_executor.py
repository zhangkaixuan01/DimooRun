import asyncio
from typing import Any

import pytest
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult
from dimoo_run.domain.models import Run, RunAttempt, Task
from dimoo_run.persistence.database import Base
from dimoo_run.runtime.run_manager import RunManager
from dimoo_run.runtime.sqlalchemy_run_store import SQLAlchemyRunStore
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from dimoo_run.streaming.replay_buffer import ReplayBuffer
from dimoo_run.worker.executor import AgentRuntimeSpec, WorkerExecutor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class DurableFakeAdapter:
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
        _ = agent
        return AgentResult(
            output={"echo": input_data["message"], "run_id": context.run_id},
            events=[AgentEvent(type="agent.message", payload={"text": "done"})],
        )


class DurableSlowAdapter(DurableFakeAdapter):
    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = agent, input_data, context
        await asyncio.sleep(1)
        return AgentResult(output={"late": True})


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.asyncio
async def test_worker_executor_completes_sqlalchemy_run_attempt_and_task() -> None:
    session = make_session()
    run_store = SQLAlchemyRunStore(session)
    task_backend = SQLAlchemyTaskBackend(session)
    replay_buffer = ReplayBuffer()
    manager = RunManager(run_store=run_store, task_backend=task_backend)
    run, task_id = await manager.create_run_task(
        tenant_id=1,
        project_id=1,
        agent_id=1,
        agent_version_id="version_1",
        deployment_id=None,
        input_data={"message": "hello"},
    )
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=replay_buffer,
        adapters={"fake": DurableFakeAdapter()},  # type: ignore[dict-item]
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

    run_model = session.get(Run, run.run_id)
    task_model = session.get(Task, task_id)
    attempts = list(session.query(RunAttempt).filter(RunAttempt.run_id == run.run_id))
    assert result is not None
    assert run_model is not None
    assert run_model.status == "succeeded"
    assert run_model.output_ref == f'json:{{"echo":"hello","run_id":"{run.run_id}"}}'
    assert task_model is not None
    assert task_model.status == "succeeded"
    assert attempts[0].status == "succeeded"
    assert [event.type for event in replay_buffer.replay(run.run_id)] == [
        "attempt.started",
        "agent.message",
        "run.completed",
        "stream.completed",
    ]


@pytest.mark.asyncio
async def test_worker_executor_times_out_sqlalchemy_run_attempt_and_task() -> None:
    session = make_session()
    run_store = SQLAlchemyRunStore(session)
    task_backend = SQLAlchemyTaskBackend(session)
    replay_buffer = ReplayBuffer()
    manager = RunManager(run_store=run_store, task_backend=task_backend)
    run, task_id = await manager.create_run_task(
        tenant_id=1,
        project_id=1,
        agent_id=1,
        agent_version_id="version_1",
        deployment_id=None,
        input_data={"message": "hello"},
    )
    task = session.get(Task, task_id)
    assert task is not None
    task.max_attempts = 1
    executor = WorkerExecutor(
        worker_id="worker_1",
        task_backend=task_backend,
        run_store=run_store,
        replay_buffer=replay_buffer,
        adapters={"fake": DurableSlowAdapter()},  # type: ignore[dict-item]
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

    run_model = session.get(Run, run.run_id)
    task_model = session.get(Task, task_id)
    attempts = list(session.query(RunAttempt).filter(RunAttempt.run_id == run.run_id))
    assert result is not None
    assert result.status == "timeout"
    assert run_model is not None
    assert run_model.status == "timeout"
    assert task_model is not None
    assert task_model.status == "dead_letter"
    assert task_model.dead_letter_reason == "run timed out"
    assert attempts[0].status == "timeout"
