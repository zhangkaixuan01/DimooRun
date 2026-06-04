from datetime import UTC, datetime

import anyio
from dimoo_run.domain.models import Run, Task
from dimoo_run.persistence.database import Base
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from dimoo_run.worker.loop import WorkerLoop
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class FakeCancelSubscriber:
    async def listen_once(self) -> dict[str, int | str]:
        return {
            "run_id": 1,
            "task_id": 1,
            "worker_id": "worker_1",
            "status": "cancelled",
        }


class FakeCancelHandler:
    def __init__(self) -> None:
        self.cancelled: tuple[str, str | None] | None = None

    async def cancel_run(self, run_id: int, *, task_id: int | None = None) -> str:
        self.cancelled = (run_id, task_id)
        return "adapter_cancelled"


class FakeExecuteOnce:
    def __init__(self) -> None:
        self.called = False

    async def __call__(self, *, queue: str, lease_seconds: int) -> object:
        self.called = True
        assert queue == "default"
        assert lease_seconds == 30
        return object()


class StopAfterExecuteOnce:
    def __init__(self, loop: WorkerLoop) -> None:
        self.loop = loop
        self.calls = 0

    async def __call__(self, *, queue: str, lease_seconds: int) -> object:
        _ = queue, lease_seconds
        self.calls += 1
        self.loop.stop()
        return object()


def test_worker_loop_uses_executor_callback_before_lease_only_path() -> None:
    execute_once = FakeExecuteOnce()
    loop = WorkerLoop(worker_id="worker_1", execute_once=execute_once)

    heartbeat = loop.run_once()

    assert heartbeat.status == "executed"
    assert execute_once.called is True


def test_worker_loop_run_forever_uses_executor_callback() -> None:
    loop = WorkerLoop(worker_id="worker_1", poll_interval_seconds=0)
    execute_once = StopAfterExecuteOnce(loop)
    loop.execute_once = execute_once

    loop.run_forever()

    assert execute_once.calls == 1
    assert loop.heartbeat.status == "executed"


def test_worker_loop_can_lease_durable_task_and_mark_it_running() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Run(
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id=1,
            input_ref='json:{"message":"hello"}',
        )
    )
    session.flush()
    run_id = session.query(Run.id).scalar()
    assert run_id is not None
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    task_id = anyio.run(
        backend.enqueue,
        {
            "tenant_id": 1,
            "project_id": 1,
            "run_id": run_id,
            "queue": "default",
        },
    )
    loop = WorkerLoop(worker_id="worker_1", task_backend=backend)

    heartbeat = loop.run_once()

    task = backend._task(task_id)
    assert heartbeat.status == "running"
    assert task.status == "running"
    assert task.worker_id == "worker_1"
    assert task.fencing_token == 1


def test_worker_loop_horizontal_scaling_leases_distinct_tasks() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    run_ids: list[int] = []
    for index in range(3):
        run = Run(
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id=1,
            input_ref=f'json:{{"message":"hello {index}"}}',
        )
        session.add(run)
        session.flush()
        run_ids.append(run.id)
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    for run_id in run_ids:
        anyio.run(
            backend.enqueue,
            {
                "tenant_id": 1,
                "project_id": 1,
                "run_id": run_id,
                "queue": "default",
            },
        )
    loops = [
        WorkerLoop(worker_id=f"worker_{index}", task_backend=backend)
        for index in range(3)
    ]

    heartbeats = [loop.run_once() for loop in loops]

    tasks = list(session.query(Task).order_by(Task.worker_id))
    assert [heartbeat.status for heartbeat in heartbeats] == ["running", "running", "running"]
    assert [task.status for task in tasks] == ["running", "running", "running"]
    assert {task.worker_id for task in tasks} == {"worker_0", "worker_1", "worker_2"}
    assert {task.fencing_token for task in tasks} == {1}


def test_worker_loop_consumes_cancel_message_for_worker() -> None:
    handler = FakeCancelHandler()
    loop = WorkerLoop(
        worker_id="worker_1",
        cancel_subscriber=FakeCancelSubscriber(),
        cancel_handler=handler,
    )

    heartbeat = loop.run_once()

    assert heartbeat.status == "cancel_requested"
    assert handler.cancelled == (1, 1)
