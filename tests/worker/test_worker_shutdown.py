from datetime import UTC, datetime

import anyio
from dimoo_run.domain.models import Run, Task
from dimoo_run.persistence.database import Base
from dimoo_run.runtime.capacity import WorkerRegistry
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from dimoo_run.worker.loop import WorkerLoop
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _make_backend() -> tuple[Session, SQLAlchemyTaskBackend, int]:
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
    return session, backend, task_id


def test_worker_loop_graceful_shutdown_prevents_new_lease() -> None:
    session, backend, task_id = _make_backend()
    registry = WorkerRegistry()
    loop = WorkerLoop(
        worker_id="worker_shutdown",
        task_backend=backend,
        worker_registry=registry,
    )

    loop.request_shutdown(graceful=True)
    heartbeat = loop.run_once()

    task = session.get(Task, task_id)
    assert heartbeat.status == "stopped"
    assert loop.stopped is True
    assert task is not None
    assert task.status == "queued"
    record = registry.get(
        "worker_shutdown",
        tenant_id=1,
        project_id=1,
        environment="production",
    )
    assert record is not None
    assert record.status == "stopped"


def test_worker_loop_respects_registry_drain_status() -> None:
    session, backend, task_id = _make_backend()
    registry = WorkerRegistry()
    registry.ensure(
        worker_id="worker_draining",
        tenant_id=1,
        project_id=1,
        environment="production",
    )
    registry.drain(
        "worker_draining",
        tenant_id=1,
        project_id=1,
        environment="production",
    )
    loop = WorkerLoop(
        worker_id="worker_draining",
        task_backend=backend,
        worker_registry=registry,
    )

    heartbeat = loop.run_once()

    task = session.get(Task, task_id)
    assert heartbeat.status == "stopped"
    assert task is not None
    assert task.status == "queued"
