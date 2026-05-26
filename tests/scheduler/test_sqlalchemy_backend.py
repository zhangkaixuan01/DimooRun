from datetime import UTC, datetime, timedelta

import pytest
from dimoo_run.domain.models import Event, Run, Task
from dimoo_run.persistence.database import Base
from dimoo_run.scheduler.backend import RuntimeTaskBackend
from dimoo_run.scheduler.in_memory import StaleFencingTokenError, TaskLeaseError
from dimoo_run.scheduler.quota import QuotaExceededError, RuntimeQuota, SQLAlchemyQuotaPolicy
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def create_run(
    session: Session,
    run_id: str = "run_1",
    *,
    tenant_id: str = "tenant_1",
    project_id: str = "project_1",
    agent_id: str = "agent_1",
    deployment_id: str | None = None,
) -> None:
    session.add(
        Run(
            id=run_id,
            tenant_id=tenant_id,
            project_id=project_id,
            agent_id=agent_id,
            agent_version_id="agent_version_1",
            deployment_id=deployment_id,
            input_ref='json:{"message":"hello"}',
        )
    )
    session.flush()


@pytest.mark.asyncio
async def test_sqlalchemy_backend_leases_by_priority_and_sets_fencing_token() -> None:
    session = make_session()
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = SQLAlchemyTaskBackend(session, now=lambda: current)
    create_run(session, "run_low")
    create_run(session, "run_high")
    low_id = await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "run_id": "run_low",
        }
    )
    high_id = await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "priority": 10,
            "run_id": "run_high",
        }
    )

    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    assert leased is not None
    assert leased["task_id"] == high_id
    assert leased["fencing_token"] == 1
    assert leased["input_data"] == {"message": "hello"}
    assert leased["partition_key"] == "tenant_1:project_1"
    assert leased["resource_class"] == "default"
    assert session.get(Task, low_id).status == "queued"  # type: ignore[union-attr]
    assert session.get(Task, high_id).status == "leased"  # type: ignore[union-attr]


def test_sqlalchemy_backend_satisfies_runtime_task_backend_protocol() -> None:
    backend: RuntimeTaskBackend = SQLAlchemyTaskBackend(make_session())

    assert backend is not None


@pytest.mark.asyncio
async def test_sqlalchemy_backend_heartbeat_extends_only_owner_lease() -> None:
    session = make_session()
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = SQLAlchemyTaskBackend(session, now=lambda: current)
    create_run(session)
    task_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_1"}
    )
    await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    await backend.heartbeat(task_id, worker_id="worker_1", lease_seconds=60)

    assert session.get(Task, task_id).leased_until == (  # type: ignore[union-attr]
        current + timedelta(seconds=60)
    ).replace(tzinfo=None)
    with pytest.raises(TaskLeaseError):
        await backend.heartbeat(task_id, worker_id="worker_2")


@pytest.mark.asyncio
async def test_sqlalchemy_backend_releases_expired_lease_with_new_fencing_token() -> None:
    session = make_session()
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = SQLAlchemyTaskBackend(session, now=lambda: current)
    create_run(session)
    task_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_1"}
    )
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=1)

    current = current + timedelta(seconds=2)
    second = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert first is not None
    assert second is not None
    assert second["task_id"] == task_id
    assert second["fencing_token"] == 2


@pytest.mark.asyncio
async def test_sqlalchemy_backend_rejects_stale_fencing_token_on_complete() -> None:
    session = make_session()
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = SQLAlchemyTaskBackend(session, now=lambda: current)
    create_run(session)
    task_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_1"}
    )
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=1)
    current = current + timedelta(seconds=2)
    await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert first is not None
    with pytest.raises(StaleFencingTokenError):
        await backend.complete(task_id, worker_id="worker_1", fencing_token=first["fencing_token"])


@pytest.mark.asyncio
async def test_sqlalchemy_backend_complete_requires_owner_and_token() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    create_run(session)
    task_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_1"}
    )
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    assert leased is not None
    with pytest.raises(TaskLeaseError):
        await backend.complete(task_id, worker_id="worker_2", fencing_token=leased["fencing_token"])
    backend.mark_running(task_id, "worker_1", leased["fencing_token"])
    await backend.complete(task_id, worker_id="worker_1", fencing_token=leased["fencing_token"])

    assert session.get(Task, task_id).status == "succeeded"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_sqlalchemy_backend_retries_then_dead_letters() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    create_run(session)
    task_id = await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "run_id": "run_1",
            "max_attempts": 2,
            "attempt": 1,
        }
    )
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    assert leased is not None
    await backend.fail(
        task_id,
        worker_id="worker_1",
        fencing_token=leased["fencing_token"],
        error={"message": "boom"},
    )

    task = session.get(Task, task_id)
    assert task is not None
    assert task.status == "dead_letter"
    assert task.dead_letter_reason == "boom"
    assert backend.dead_letters[0]["task_id"] == task_id


@pytest.mark.asyncio
async def test_sqlalchemy_backend_blocks_lease_when_project_quota_is_exceeded() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(
        session,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        quota_policy=SQLAlchemyQuotaPolicy(
            session,
            RuntimeQuota(project_max_running_tasks=1),
        ),
    )
    create_run(session, "run_1")
    create_run(session, "run_2")
    first_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_1"}
    )
    second_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_2"}
    )
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=30)
    backend.mark_running(first_id, "worker_1", first["fencing_token"])  # type: ignore[index]

    blocked = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert blocked is None
    assert backend.last_quota_error is not None
    assert backend.last_quota_error.error_code == "runtime_quota_exceeded"
    assert backend.last_quota_error.scope == "project"
    blocked_task = session.get(Task, second_id)
    assert blocked_task is not None
    assert blocked_task.status == "queued"
    assert blocked_task.metadata_json["quota_blocking_reason"]["scope"] == "project"


@pytest.mark.asyncio
async def test_sqlalchemy_backend_skips_quota_blocked_partition() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(
        session,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        quota_policy=SQLAlchemyQuotaPolicy(
            session,
            RuntimeQuota(project_max_running_tasks=1),
        ),
    )
    create_run(session, "run_project_1_active")
    create_run(session, "run_project_1_waiting")
    create_run(
        session,
        "run_project_2_waiting",
        tenant_id="tenant_1",
        project_id="project_2",
    )
    active_id = await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "priority": 10,
            "run_id": "run_project_1_active",
        }
    )
    await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "priority": 10,
            "run_id": "run_project_1_waiting",
        }
    )
    project_2_id = await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_2",
            "queue": "default",
            "run_id": "run_project_2_waiting",
        }
    )
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=30)
    backend.mark_running(active_id, "worker_1", first["fencing_token"])  # type: ignore[index]

    leased = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert leased is not None
    assert leased["task_id"] == project_2_id
    assert backend.last_quota_error is None


@pytest.mark.asyncio
async def test_sqlalchemy_backend_blocks_lease_when_agent_quota_is_exceeded() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(
        session,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        quota_policy=SQLAlchemyQuotaPolicy(
            session,
            RuntimeQuota(agent_max_running_tasks=1),
        ),
    )
    create_run(session, "run_1", agent_id="agent_1")
    create_run(session, "run_2", agent_id="agent_1")
    first_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_1"}
    )
    await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_2"}
    )
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=30)
    backend.mark_running(first_id, "worker_1", first["fencing_token"])  # type: ignore[index]

    blocked = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert blocked is None
    assert backend.last_quota_error is not None
    assert backend.last_quota_error.scope == "agent"


@pytest.mark.asyncio
async def test_sqlalchemy_backend_blocks_lease_when_deployment_quota_is_exceeded() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(
        session,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        quota_policy=SQLAlchemyQuotaPolicy(
            session,
            RuntimeQuota(deployment_max_running_tasks=1),
        ),
    )
    create_run(session, "run_1", deployment_id="deployment_1")
    create_run(session, "run_2", deployment_id="deployment_1")
    first_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_1"}
    )
    await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_2"}
    )
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=30)
    backend.mark_running(first_id, "worker_1", first["fencing_token"])  # type: ignore[index]

    blocked = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert blocked is None
    assert backend.last_quota_error is not None
    assert backend.last_quota_error.scope == "deployment"


@pytest.mark.asyncio
async def test_sqlalchemy_backend_releases_quota_after_terminal_state() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(
        session,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        quota_policy=SQLAlchemyQuotaPolicy(
            session,
            RuntimeQuota(project_max_running_tasks=1),
        ),
    )
    create_run(session, "run_1")
    create_run(session, "run_2")
    first_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_1"}
    )
    second_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_2"}
    )
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=30)
    assert first is not None
    backend.mark_running(first_id, "worker_1", first["fencing_token"])
    await backend.complete(first_id, "worker_1", first["fencing_token"])

    second = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert second is not None
    assert second["task_id"] == second_id


@pytest.mark.asyncio
async def test_sqlalchemy_backend_checks_project_quota_on_enqueue() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(
        session,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        quota_policy=SQLAlchemyQuotaPolicy(
            session,
            RuntimeQuota(project_max_running_tasks=1),
        ),
    )
    create_run(session, "run_1")
    create_run(session, "run_2")
    first_id = await backend.enqueue(
        {"tenant_id": "tenant_1", "project_id": "project_1", "queue": "default", "run_id": "run_1"}
    )
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=30)
    assert first is not None
    backend.mark_running(first_id, "worker_1", first["fencing_token"])

    with pytest.raises(QuotaExceededError) as exc_info:
        await backend.enqueue(
            {
                "tenant_id": "tenant_1",
                "project_id": "project_1",
                "queue": "default",
                "run_id": "run_2",
            }
        )

    assert exc_info.value.error_code == "runtime_quota_exceeded"
    assert exc_info.value.scope == "project"


@pytest.mark.asyncio
async def test_sqlalchemy_backend_dead_letters_expired_running_task_after_attempts() -> None:
    session = make_session()
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = SQLAlchemyTaskBackend(session, now=lambda: current)
    create_run(session)
    task_id = await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "run_id": "run_1",
            "max_attempts": 1,
        }
    )
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=1)
    assert leased is not None
    backend.mark_running(task_id, "worker_1", leased["fencing_token"])
    current = current + timedelta(seconds=2)

    changed = backend.reap_expired_leases()

    task = session.get(Task, task_id)
    assert changed == 1
    assert task is not None
    assert task.status == "dead_letter"
    assert task.dead_letter_reason == "lease_expired"
    events = list(session.query(Event).filter(Event.run_id == "run_1"))
    assert [event.type for event in events] == ["task.dead_letter"]
    assert events[0].payload_json == {"task_id": task_id, "reason": "lease_expired"}


@pytest.mark.asyncio
async def test_sqlalchemy_backend_reaper_consumes_attempt_before_requeue() -> None:
    session = make_session()
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = SQLAlchemyTaskBackend(session, now=lambda: current)
    create_run(session)
    task_id = await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "run_id": "run_1",
            "max_attempts": 3,
        }
    )
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=1)
    assert leased is not None
    backend.mark_running(task_id, "worker_1", leased["fencing_token"])
    current = current + timedelta(seconds=2)

    changed = backend.reap_expired_leases()

    task = session.get(Task, task_id)
    assert changed == 1
    assert task is not None
    assert task.status == "queued"
    assert task.attempt == 1


@pytest.mark.asyncio
async def test_sqlalchemy_backend_stores_partition_and_resource_class_metadata() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    create_run(session)
    task_id = await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "run_id": "run_1",
            "resource_class": "gpu",
        }
    )

    task = session.get(Task, task_id)

    assert task is not None
    assert task.metadata_json["partition_key"] == "tenant_1:project_1"
    assert task.metadata_json["resource_class"] == "gpu"


@pytest.mark.asyncio
async def test_sqlalchemy_backend_fairness_covers_multiple_tenants() -> None:
    session = make_session()
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    create_run(session, "run_tenant_1_active", tenant_id="tenant_1", project_id="project_1")
    create_run(session, "run_tenant_1_waiting", tenant_id="tenant_1", project_id="project_1")
    create_run(session, "run_tenant_2_waiting", tenant_id="tenant_2", project_id="project_2")
    active_id = await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "priority": 10,
            "run_id": "run_tenant_1_active",
        }
    )
    await backend.enqueue(
        {
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "queue": "default",
            "priority": 10,
            "run_id": "run_tenant_1_waiting",
        }
    )
    tenant_2_id = await backend.enqueue(
        {
            "tenant_id": "tenant_2",
            "project_id": "project_2",
            "queue": "default",
            "run_id": "run_tenant_2_waiting",
        }
    )
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=30)
    assert first is not None
    backend.mark_running(active_id, "worker_1", first["fencing_token"])

    leased = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert leased is not None
    assert leased["task_id"] == tenant_2_id
