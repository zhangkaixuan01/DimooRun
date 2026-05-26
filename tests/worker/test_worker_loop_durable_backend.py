from datetime import UTC, datetime

import anyio
from dimoo_run.domain.models import Run, Task
from dimoo_run.persistence.database import Base
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from dimoo_run.worker.loop import WorkerLoop
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class FakeCancelSubscriber:
    async def listen_once(self) -> dict[str, str]:
        return {
            "run_id": "run_1",
            "task_id": "task_1",
            "worker_id": "worker_1",
            "status": "cancelled",
        }


def test_worker_loop_can_lease_durable_task_and_mark_it_running() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Run(
            id="run_1",
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="agent_version_1",
            input_ref='json:{"message":"hello"}',
        )
    )
    session.flush()
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    task_id = anyio.run(
        backend.enqueue,
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "run_id": "run_1",
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
    for index in range(3):
        session.add(
            Run(
                id=f"run_{index}",
                tenant_id="tenant_1",
                project_id="project_1",
                agent_id="agent_1",
                agent_version_id="agent_version_1",
                input_ref='json:{"message":"hello"}',
            )
        )
    session.flush()
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    for index in range(3):
        anyio.run(
            backend.enqueue,
            {
                "tenant_id": "tenant_1",
                "project_id": "project_1",
                "run_id": f"run_{index}",
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
    loop = WorkerLoop(worker_id="worker_1", cancel_subscriber=FakeCancelSubscriber())

    heartbeat = loop.run_once()

    assert heartbeat.status == "cancel_requested"
