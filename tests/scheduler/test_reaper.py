from datetime import UTC, datetime, timedelta

from dimoo_run.scheduler.in_memory import InMemoryTaskBackend
from dimoo_run.scheduler.reaper import LeaseReaper


async def test_lease_reaper_requeues_expired_leases() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = InMemoryTaskBackend(now=lambda: current)
    task_id = await backend.enqueue({"queue": "default", "run_id": 1})
    await backend.lease("default", worker_id="worker_1", lease_seconds=1)
    current = current + timedelta(seconds=2)

    reaped = LeaseReaper(backend).reap()

    assert reaped == [task_id]
    assert backend.tasks[task_id].status == "queued"
    assert backend.tasks[task_id].worker_id is None
    assert LeaseReaper(backend).reap() == []


async def test_lease_reaper_requeues_expired_running_tasks() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = InMemoryTaskBackend(now=lambda: current)
    task_id = await backend.enqueue({"queue": "default", "run_id": 1})
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=1)
    assert leased is not None
    backend.mark_running(task_id, worker_id="worker_1", fencing_token=leased["fencing_token"])
    current = current + timedelta(seconds=2)

    reaped = LeaseReaper(backend).reap()

    assert reaped == [task_id]
    assert backend.tasks[task_id].status == "queued"
    assert backend.tasks[task_id].worker_id is None
    assert backend.tasks[task_id].leased_until is None


async def test_lease_reaper_records_heartbeat() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = InMemoryTaskBackend(now=lambda: current)
    task_id = await backend.enqueue({"queue": "default", "run_id": 1})
    await backend.lease("default", worker_id="worker_1", lease_seconds=1)
    current = current + timedelta(seconds=2)
    reaper = LeaseReaper(backend, reaper_id="reaper_1")

    reaped = reaper.reap()

    assert reaped == [task_id]
    assert reaper.heartbeat.reaper_id == "reaper_1"
    assert reaper.heartbeat.status == "running"
    assert reaper.heartbeat.reaped_count == 1
