from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from dimoo_run.runtime.state_machine import assert_task_transition


class TaskLeaseError(RuntimeError):
    pass


class StaleFencingTokenError(RuntimeError):
    error_code = "stale_fencing_token"


@dataclass
class InMemoryTask:
    task_id: str
    payload: dict[str, Any]
    run_id: str
    queue: str = "default"
    priority: int = 0
    status: str = "queued"
    attempt: int = 0
    max_attempts: int = 3
    worker_id: str | None = None
    leased_until: datetime | None = None
    heartbeat_at: datetime | None = None
    scheduled_at: datetime | None = None
    fencing_token: int = 0
    error: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def snapshot(self) -> dict[str, Any]:
        return {
            **self.payload,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "queue": self.queue,
            "priority": self.priority,
            "status": self.status,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "worker_id": self.worker_id,
            "leased_until": self.leased_until,
            "heartbeat_at": self.heartbeat_at,
            "scheduled_at": self.scheduled_at,
            "fencing_token": self.fencing_token,
        }


class InMemoryTaskBackend:
    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))
        self.tasks: dict[str, InMemoryTask] = {}
        self.dead_letters: list[dict[str, Any]] = []

    async def enqueue(self, task: dict[str, Any]) -> str:
        task_id = task.get("task_id") or str(uuid4())
        item = InMemoryTask(
            task_id=task_id,
            payload=dict(task),
            run_id=task["run_id"],
            queue=task.get("queue", "default"),
            priority=task.get("priority", 0),
            attempt=task.get("attempt", 0),
            max_attempts=task.get("max_attempts", 3),
            scheduled_at=task.get("scheduled_at"),
            created_at=self._now(),
        )
        self.tasks[task_id] = item
        return task_id

    async def lease(
        self,
        queue: str,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        now = self._now()
        self.reap_expired_leases()
        candidates = [
            task
            for task in self.tasks.values()
            if task.queue == queue
            and task.status == "queued"
            and (task.scheduled_at is None or task.scheduled_at <= now)
        ]
        if not candidates:
            return None
        task = sorted(candidates, key=lambda item: (-item.priority, item.created_at))[0]
        self._transition(task, "leased")
        task.status = "leased"
        task.worker_id = worker_id
        task.leased_until = now + timedelta(seconds=lease_seconds)
        task.heartbeat_at = now
        task.fencing_token += 1
        return task.snapshot()

    async def heartbeat(
        self,
        task_id: str,
        worker_id: str,
        lease_seconds: int = 30,
    ) -> None:
        task = self._owned_task(task_id, worker_id)
        now = self._now()
        task.heartbeat_at = now
        task.leased_until = now + timedelta(seconds=lease_seconds)

    async def complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        task = self.tasks[task_id]
        self.assert_can_complete(task_id, worker_id, fencing_token)
        self._transition(task, "succeeded")
        task.status = "succeeded"

    async def fail(
        self,
        task_id: str,
        worker_id: str,
        fencing_token: int,
        error: dict[str, Any],
    ) -> None:
        task = self.tasks[task_id]
        self._assert_fencing_token(task, fencing_token)
        self._assert_owner(task, worker_id)
        if task.status == "leased":
            self._transition(task, "running")
            task.status = "running"
        self._transition(task, "failed")
        task.status = "failed"
        if task.attempt + 1 >= task.max_attempts:
            self._transition(task, "dead_letter")
        else:
            self._transition(task, "retrying")
        task.error = error
        if task.attempt + 1 >= task.max_attempts:
            task.status = "dead_letter"
            self.dead_letters.append({"task_id": task_id, "error": error})
            return
        task.attempt += 1
        task.status = "retrying"
        task.worker_id = None
        task.leased_until = None
        self._transition(task, "queued")
        task.status = "queued"

    async def cancel(self, task_id: str) -> None:
        self._transition(self.tasks[task_id], "cancelled")
        self.tasks[task_id].status = "cancelled"

    def mark_running(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        task = self._owned_task(task_id, worker_id)
        self._assert_fencing_token(task, fencing_token)
        self._transition(task, "running")
        task.status = "running"

    def assert_can_complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        task = self.tasks[task_id]
        self._assert_fencing_token(task, fencing_token)
        self._assert_owner(task, worker_id)

    def will_retry(self, task_id: str) -> bool:
        task = self.tasks[task_id]
        return task.attempt + 1 < task.max_attempts

    def reap_expired_leases(self) -> None:
        now = self._now()
        for task in self.tasks.values():
            if (
                task.status in {"leased", "running"}
                and task.leased_until is not None
                and task.leased_until < now
            ):
                if task.status == "running":
                    self._transition(task, "retrying")
                    task.status = "retrying"
                self._transition(task, "queued")
                task.status = "queued"
                task.worker_id = None
                task.leased_until = None

    def _owned_task(self, task_id: str, worker_id: str) -> InMemoryTask:
        task = self.tasks[task_id]
        self._assert_owner(task, worker_id)
        return task

    def _assert_fencing_token(self, task: InMemoryTask, fencing_token: int) -> None:
        if task.fencing_token != fencing_token:
            raise StaleFencingTokenError(task.task_id)

    def _assert_owner(self, task: InMemoryTask, worker_id: str) -> None:
        if task.worker_id != worker_id:
            raise TaskLeaseError(f"Task {task.task_id} is not leased by {worker_id}.")

    def _transition(self, task: InMemoryTask, target: str) -> None:
        assert_task_transition(task.status, target)
