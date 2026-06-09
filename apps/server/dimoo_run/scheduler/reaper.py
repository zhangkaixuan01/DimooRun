from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ReaperHeartbeat:
    reaper_id: str
    status: str
    heartbeat_at: datetime
    reaped_count: int


class LeaseReaper:
    def __init__(self, backend: Any, *, reaper_id: str = "lease_reaper") -> None:
        self.backend = backend
        self.reaper_id = reaper_id
        self.heartbeat = ReaperHeartbeat(
            reaper_id=reaper_id,
            status="starting",
            heartbeat_at=datetime.now(UTC),
            reaped_count=0,
        )

    def reap(self) -> list[int]:
        if not hasattr(self.backend, "tasks"):
            reaped_count = self.backend.reap_expired_leases()
            self._record_heartbeat(reaped_count)
            return []
        before = {
            task_id
            for task_id, task in self.backend.tasks.items()
            if task.status in {"leased", "running"} and task.leased_until is not None
        }
        self.backend.reap_expired_leases()
        reaped = [
            task_id
            for task_id in before
            if self.backend.tasks[task_id].status == "queued"
            and self.backend.tasks[task_id].worker_id is None
        ]
        self._record_heartbeat(len(reaped))
        return reaped

    def _record_heartbeat(self, reaped_count: int) -> None:
        self.heartbeat = ReaperHeartbeat(
            reaper_id=self.reaper_id,
            status="running",
            heartbeat_at=datetime.now(UTC),
            reaped_count=reaped_count,
        )
