from datetime import UTC, datetime, timedelta

from dimoo_run.scheduler.in_memory import InMemoryTaskBackend
from dimoo_run.scheduler.reaper import LeaseReaper


async def test_lease_reaper_requeues_expired_leases() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)
    backend = InMemoryTaskBackend(now=lambda: current)
    task_id = await backend.enqueue({"queue": "default", "run_id": "run_1"})
    await backend.lease("default", worker_id="worker_1", lease_seconds=1)
    current = current + timedelta(seconds=2)

    reaped = LeaseReaper(backend).reap()

    assert reaped == [task_id]
    assert backend.tasks[task_id].status == "queued"
    assert backend.tasks[task_id].worker_id is None
