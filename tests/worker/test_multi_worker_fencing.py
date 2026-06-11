import threading
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import anyio
import pytest
from dimoo_run.adapters.base.contract import AgentAdapter, CapabilityNotSupportedError
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult
from dimoo_run.domain.models import Agent, AgentVersion, Event, Run, RunAttempt, Task
from dimoo_run.persistence.database import Base
from dimoo_run.runtime.sqlalchemy_run_store import SQLAlchemyRunStore
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from dimoo_run.worker.durable import execute_durable_once
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


class FastDurableAdapter:
    framework = "fake"

    async def load(
        self,
        package_uri: str,
        manifest: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "package_uri": package_uri,
            "manifest": manifest,
            "runtime_config": runtime_config,
        }

    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = context
        return AgentResult(
            output={"echo": input_data["message"], "version": agent["manifest"]["name"]},
            events=[AgentEvent(type="agent.message", payload={"text": "done"})],
        )

    async def stream(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AsyncIterator[AgentEvent]:
        _ = agent, input_data, context
        if False:
            yield AgentEvent(type="agent.message", payload={})
        raise CapabilityNotSupportedError("stream", self.framework)

    async def resume(
        self,
        agent: Any,
        run_id: int,
        payload: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = agent, run_id, payload, context
        raise CapabilityNotSupportedError("resume", self.framework)

    async def cancel(self, run_id: int, context: RuntimeContext) -> None:
        _ = run_id, context
        raise CapabilityNotSupportedError("cancel", self.framework)


def _seed_runtime(session: Session) -> tuple[int, int]:
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
    session.commit()
    return run.id, task.id


def test_two_workers_cannot_execute_same_leased_task(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'multi-worker.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run_id, task_id = _seed_runtime(session)

    barrier = threading.Barrier(2)
    results: dict[str, str | None] = {}

    def worker_thread(worker_id: str) -> None:
        with Session(engine) as session:
            barrier.wait()
            result = anyio.run(
                lambda: execute_durable_once(
                    session=session,
                    worker_id=worker_id,
                    queue="default",
                    adapters={"fake": cast(AgentAdapter, FastDurableAdapter())},
                )
            )
            session.commit()
            results[worker_id] = None if result is None else result.status

    first = threading.Thread(target=worker_thread, args=("worker_1",))
    second = threading.Thread(target=worker_thread, args=("worker_2",))
    first.start()
    second.start()
    first.join()
    second.join()

    with Session(engine) as session:
        task = session.get(Task, task_id)
        attempts = list(session.scalars(select(RunAttempt).where(RunAttempt.run_id == run_id)))

    assert list(results.values()).count("succeeded") == 1
    assert list(results.values()).count(None) == 1
    assert task is not None
    assert task.status == "succeeded"
    assert len(attempts) == 1


@pytest.mark.asyncio
async def test_killed_worker_leaves_recoverable_state(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'reaper-recovery.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as setup_session:
        run_id, task_id = _seed_runtime(setup_session)

    current = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(engine) as crashed_session:
        backend = SQLAlchemyTaskBackend(crashed_session, now=lambda: current)
        leased = await backend.lease("default", worker_id="worker_1", lease_seconds=1)
        assert leased is not None
        backend.mark_running(task_id, "worker_1", leased["fencing_token"])
        attempt = await SQLAlchemyRunStore(crashed_session).create_attempt(
            run_id=run_id,
            task_id=task_id,
            worker_id="worker_1",
        )
        crashed_session.commit()

    with Session(engine) as reaper_session:
        reaper_backend = SQLAlchemyTaskBackend(
            reaper_session,
            now=lambda: current + timedelta(seconds=2),
        )
        changed = reaper_backend.reap_expired_leases()
        reaper_session.commit()

    with Session(engine) as recovery_session:
        result = await execute_durable_once(
            session=recovery_session,
            worker_id="worker_2",
            queue="default",
            adapters={"fake": cast(AgentAdapter, FastDurableAdapter())},
            lease_seconds=30,
        )
        recovery_session.commit()

    with Session(engine) as assert_session:
        task = assert_session.get(Task, task_id)
        run = assert_session.get(Run, run_id)
        attempts = list(
            assert_session.scalars(
                select(RunAttempt)
                .where(RunAttempt.run_id == run_id)
                .order_by(RunAttempt.attempt_no)
            )
        )
        events = list(
            assert_session.scalars(
                select(Event).where(Event.run_id == run_id).order_by(Event.sequence)
            )
        )

    assert changed == 1
    assert result is not None
    assert result.status == "succeeded"
    assert task is not None
    assert task.status == "succeeded"
    assert run is not None
    assert run.status == "succeeded"
    assert len(attempts) == 2
    assert attempt.attempt_id == attempts[0].id
    assert attempts[0].status == "failed"
    assert attempts[0].error == "lease_expired"
    assert attempts[1].status == "succeeded"
    assert [event.type for event in events] == [
        "attempt.failed",
        "task.retrying",
        "attempt.started",
        "agent.message",
        "run.completed",
        "stream.completed",
    ]
