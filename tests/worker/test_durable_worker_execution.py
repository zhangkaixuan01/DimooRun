from typing import Any

import pytest
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult
from dimoo_run.domain.models import Agent, AgentVersion, Event, Run, RunAttempt, Task
from dimoo_run.persistence.database import Base
from dimoo_run.worker.durable import execute_durable_once
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
        adapters={"fake": FakeDurableAdapter()},  # type: ignore[dict-item]
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
    events = session.query(Event).filter(Event.run_id == run.id).order_by(Event.sequence).all()
    assert [event.type for event in events] == [
        "attempt.started",
        "agent.message",
        "run.completed",
        "stream.completed",
    ]


@pytest.mark.asyncio
async def test_execute_durable_once_records_missing_adapter_as_terminal_failure() -> None:
    session = make_session()
    agent = Agent(tenant_id=1, project_id=1, name="support", status="active")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version="0.1.0",
        package_uri="memory://support",
        framework="missing",
        adapter="missing",
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
    task = Task(
        run_id=run.id,
        tenant_id=1,
        project_id=1,
        queue="default",
        max_attempts=1,
    )
    session.add(task)
    session.flush()

    result = await execute_durable_once(
        session=session,
        worker_id="worker_1",
        queue="default",
        adapters={},
    )

    assert result is not None
    assert result.status == "failed"
    session.refresh(run)
    session.refresh(task)
    attempt = session.query(RunAttempt).filter(RunAttempt.run_id == run.id).one()
    events = session.query(Event).filter(Event.run_id == run.id).order_by(Event.sequence).all()
    assert run.status == "failed"
    assert run.error == "worker_adapter_not_found"
    assert task.status == "dead_letter"
    assert task.dead_letter_reason == "worker_adapter_not_found"
    assert attempt.status == "failed"
    assert attempt.error == "worker_adapter_not_found"
    assert [event.type for event in events] == [
        "attempt.started",
        "attempt.failed",
        "run.failed",
        "stream.failed",
    ]


@pytest.mark.asyncio
async def test_execute_durable_once_records_missing_agent_version_as_terminal_failure() -> None:
    session = make_session()
    run = Run(
        tenant_id=1,
        project_id=1,
        agent_id=1,
        agent_version_id=999,
        input_ref='json:{"message":"hello"}',
    )
    session.add(run)
    session.flush()
    task = Task(
        run_id=run.id,
        tenant_id=1,
        project_id=1,
        queue="default",
        max_attempts=1,
    )
    session.add(task)
    session.flush()

    result = await execute_durable_once(
        session=session,
        worker_id="worker_1",
        queue="default",
        adapters={"fake": FakeDurableAdapter()},  # type: ignore[dict-item]
    )

    assert result is not None
    assert result.status == "failed"
    session.refresh(run)
    session.refresh(task)
    assert run.status == "failed"
    assert run.error == "worker_agent_version_not_found"
    assert task.status == "dead_letter"
    assert task.dead_letter_reason == "worker_agent_version_not_found"
