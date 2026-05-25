from datetime import UTC, datetime, timedelta

import pytest
from dimoo_run.runtime.state_machine import InvalidStateTransitionError
from dimoo_run.scheduler.backend import RuntimeTaskBackend
from dimoo_run.scheduler.in_memory import (
    InMemoryTaskBackend,
    StaleFencingTokenError,
    TaskLeaseError,
)


@pytest.mark.asyncio
async def test_in_memory_backend_leases_by_priority_and_sets_fencing_token() -> None:
    backend = InMemoryTaskBackend(now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    low_id = await backend.enqueue({"queue": "default", "priority": 0, "run_id": "run_low"})
    high_id = await backend.enqueue({"queue": "default", "priority": 10, "run_id": "run_high"})

    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    assert leased is not None
    assert leased["task_id"] == high_id
    assert leased["fencing_token"] == 1
    assert backend.tasks[low_id].status == "queued"
    assert backend.tasks[high_id].status == "leased"


def test_in_memory_backend_satisfies_runtime_task_backend_protocol() -> None:
    backend: RuntimeTaskBackend = InMemoryTaskBackend()

    assert backend is not None


@pytest.mark.asyncio
async def test_in_memory_backend_heartbeat_extends_only_owner_lease() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = InMemoryTaskBackend(now=lambda: current)
    task_id = await backend.enqueue({"queue": "default", "run_id": "run_1"})
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    await backend.heartbeat(task_id, worker_id="worker_1", lease_seconds=60)

    assert leased is not None
    assert backend.tasks[task_id].leased_until == current + timedelta(seconds=60)

    with pytest.raises(TaskLeaseError):
        await backend.heartbeat(task_id, worker_id="worker_2")


@pytest.mark.asyncio
async def test_in_memory_backend_releases_expired_lease_with_new_fencing_token() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = InMemoryTaskBackend(now=lambda: current)
    task_id = await backend.enqueue({"queue": "default", "run_id": "run_1"})
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=1)

    current = current + timedelta(seconds=2)
    second = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert first is not None
    assert second is not None
    assert second["task_id"] == task_id
    assert second["fencing_token"] == 2


@pytest.mark.asyncio
async def test_in_memory_backend_rejects_stale_fencing_token_on_complete() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = InMemoryTaskBackend(now=lambda: current)
    task_id = await backend.enqueue({"queue": "default", "run_id": "run_1"})
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=1)
    current = current + timedelta(seconds=2)
    second = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert first is not None
    assert second is not None
    with pytest.raises(StaleFencingTokenError):
        await backend.complete(
            task_id,
            worker_id="worker_1",
            fencing_token=first["fencing_token"],
        )


@pytest.mark.asyncio
async def test_in_memory_backend_retries_then_dead_letters() -> None:
    backend = InMemoryTaskBackend(now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    task_id = await backend.enqueue(
        {"queue": "default", "run_id": "run_1", "max_attempts": 2, "attempt": 1}
    )
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    assert leased is not None
    await backend.fail(
        task_id,
        worker_id="worker_1",
        fencing_token=leased["fencing_token"],
        error={"message": "boom"},
    )

    assert backend.tasks[task_id].status == "dead_letter"
    assert backend.dead_letters[0]["task_id"] == task_id


@pytest.mark.asyncio
async def test_in_memory_backend_rejects_invalid_task_transition() -> None:
    backend = InMemoryTaskBackend(now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    task_id = await backend.enqueue({"queue": "default", "run_id": "run_1"})

    with pytest.raises(InvalidStateTransitionError):
        await backend.complete(task_id, worker_id="worker_1", fencing_token=0)
