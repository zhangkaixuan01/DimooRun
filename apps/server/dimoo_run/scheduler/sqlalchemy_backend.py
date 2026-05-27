import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from dimoo_run.domain.models import Run, Task
from dimoo_run.persistence.repositories import EventRepository
from dimoo_run.runtime.state_machine import assert_task_transition
from dimoo_run.scheduler.in_memory import StaleFencingTokenError, TaskLeaseError
from dimoo_run.scheduler.quota import QuotaExceededError, SQLAlchemyQuotaPolicy


class SQLAlchemyTaskBackend:
    def __init__(
        self,
        session: Session,
        now: Callable[[], datetime] | None = None,
        quota_policy: SQLAlchemyQuotaPolicy | None = None,
    ) -> None:
        self.session = session
        self._now = now or (lambda: datetime.now(UTC))
        self.quota_policy = quota_policy
        self.last_quota_error: QuotaExceededError | None = None
        self.dead_letters: list[dict[str, Any]] = []

    async def enqueue(self, task: dict[str, Any]) -> str:
        if self.quota_policy is not None:
            self.quota_policy.assert_can_enqueue(
                tenant_id=task["tenant_id"],
                project_id=task["project_id"],
                agent_id=task.get("agent_id"),
                deployment_id=task.get("deployment_id"),
            )
        task_id = task.get("task_id") or f"task_{uuid4().hex[:12]}"
        model = Task(
            id=task_id,
            run_id=task["run_id"],
            tenant_id=task["tenant_id"],
            project_id=task["project_id"],
            queue=task.get("queue", "default"),
            priority=task.get("priority", 0),
            attempt=task.get("attempt", 0),
            max_attempts=task.get("max_attempts", 3),
            scheduled_at=task.get("scheduled_at"),
            idempotency_key=task.get("idempotency_key"),
            metadata_json=_task_metadata(task),
        )
        self.session.add(model)
        self.session.flush()
        return task_id

    async def lease(
        self,
        queue: str,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        self.reap_expired_leases()
        now = self._now()
        statement = (
            select(Task)
            .where(
                Task.queue == queue,
                Task.status == "queued",
                Task.is_deleted.is_(False),
                (Task.scheduled_at.is_(None) | (Task.scheduled_at <= now)),
            )
            .order_by(Task.priority.desc(), Task.created_at.asc())
        )
        candidates = list(self.session.scalars(statement))
        if not candidates:
            return None
        candidates.sort(
            key=lambda candidate: (
                self._active_partition_count(candidate),
                -candidate.priority,
                candidate.created_at,
            )
        )
        last_quota_error: QuotaExceededError | None = None
        task: Task | None = None
        for candidate in candidates:
            if self.quota_policy is not None:
                try:
                    self.quota_policy.assert_can_lease(candidate)
                except QuotaExceededError as exc:
                    last_quota_error = exc
                    self._record_quota_block(candidate, exc)
                    continue
            claimed = self._claim_queued_task(
                candidate,
                worker_id=worker_id,
                leased_until=now + timedelta(seconds=lease_seconds),
                now=now,
            )
            if claimed is None:
                continue
            task = claimed
            break
        if task is None:
            self.last_quota_error = last_quota_error
            return None
        self.last_quota_error = None
        return self._snapshot(task)

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
        self.session.flush()

    async def complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        task = self._task(task_id)
        self.assert_can_complete(task_id, worker_id, fencing_token)
        if task.status == "leased":
            assert_task_transition(task.status, "running")
            task.status = "running"
        assert_task_transition(task.status, "succeeded")
        task.status = "succeeded"
        task.finished_at = self._now()
        task.leased_until = None
        self.session.flush()

    async def fail(
        self,
        task_id: str,
        worker_id: str,
        fencing_token: int,
        error: dict[str, Any],
    ) -> None:
        task = self._task(task_id)
        self._assert_fencing_token(task, fencing_token)
        self._assert_owner(task, worker_id)
        if task.status == "leased":
            assert_task_transition(task.status, "running")
            task.status = "running"
        assert_task_transition(task.status, "failed")
        task.status = "failed"
        task.error = _error_message(error)
        now = self._now()
        if task.attempt + 1 >= task.max_attempts:
            assert_task_transition(task.status, "dead_letter")
            task.status = "dead_letter"
            task.finished_at = now
            task.dead_letter_reason = task.error
            task.leased_until = None
            self.dead_letters.append({"task_id": task_id, "error": error})
            self.session.flush()
            return
        assert_task_transition(task.status, "retrying")
        task.status = "retrying"
        task.attempt += 1
        task.worker_id = None
        task.leased_until = None
        assert_task_transition(task.status, "queued")
        task.status = "queued"
        self.session.flush()

    async def cancel(self, task_id: str) -> None:
        task = self._task(task_id)
        if task.status == "leased":
            assert_task_transition(task.status, "running")
            task.status = "running"
        assert_task_transition(task.status, "cancelled")
        task.status = "cancelled"
        task.finished_at = self._now()
        self.session.flush()

    def mark_running(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        task = self._owned_task(task_id, worker_id)
        self._assert_fencing_token(task, fencing_token)
        assert_task_transition(task.status, "running")
        task.status = "running"
        task.started_at = task.started_at or self._now()
        self.session.flush()

    def assert_can_complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        task = self._task(task_id)
        self._assert_fencing_token(task, fencing_token)
        self._assert_owner(task, worker_id)

    def will_retry(self, task_id: str) -> bool:
        task = self._task(task_id)
        return task.attempt + 1 < task.max_attempts

    def reap_expired_leases(self) -> int:
        now = self._now()
        statement = select(Task).where(
            Task.status.in_(["leased", "running"]),
            Task.leased_until.is_not(None),
            Task.leased_until < now,
            Task.is_deleted.is_(False),
        )
        requeued = 0
        for task in self.session.scalars(statement):
            if task.status == "running":
                if task.attempt + 1 >= task.max_attempts:
                    assert_task_transition(task.status, "dead_letter")
                    task.status = "dead_letter"
                    task.finished_at = now
                    task.dead_letter_reason = "lease_expired"
                    task.worker_id = None
                    task.leased_until = None
                    self._append_reaper_event(
                        task,
                        "task.dead_letter",
                        {"task_id": task.id, "reason": "lease_expired"},
                    )
                    requeued += 1
                    continue
                assert_task_transition(task.status, "retrying")
                task.status = "retrying"
                task.attempt += 1
            assert_task_transition(task.status, "queued")
            task.status = "queued"
            task.worker_id = None
            task.leased_until = None
            self._append_reaper_event(
                task,
                "task.lease_expired",
                {"task_id": task.id, "status": "queued"},
            )
            requeued += 1
        self.session.flush()
        return requeued

    def _snapshot(self, task: Task) -> dict[str, Any]:
        run = self.session.get(Run, task.run_id)
        return {
            "task_id": task.id,
            "run_id": task.run_id,
            "tenant_id": task.tenant_id,
            "project_id": task.project_id,
            "queue": task.queue,
            "priority": task.priority,
            "status": task.status,
            "attempt": task.attempt,
            "max_attempts": task.max_attempts,
            "worker_id": task.worker_id,
            "leased_until": task.leased_until,
            "heartbeat_at": task.heartbeat_at,
            "scheduled_at": task.scheduled_at,
            "fencing_token": task.fencing_token,
            "input_data": _decode_ref(run.input_ref) if run is not None else {},
            "partition_key": task.metadata_json.get("partition_key"),
            "resource_class": task.metadata_json.get("resource_class"),
            "quota_blocking_reason": task.metadata_json.get("quota_blocking_reason"),
        }

    def _task(self, task_id: str) -> Task:
        task = self.session.get(Task, task_id)
        if task is None:
            raise KeyError(task_id)
        return task

    def _owned_task(self, task_id: str, worker_id: str) -> Task:
        task = self._task(task_id)
        self._assert_owner(task, worker_id)
        return task

    def _assert_fencing_token(self, task: Task, fencing_token: int) -> None:
        if task.fencing_token != fencing_token:
            raise StaleFencingTokenError(task.id)

    def _assert_owner(self, task: Task, worker_id: str) -> None:
        if task.worker_id != worker_id:
            raise TaskLeaseError(f"Task {task.id} is not leased by {worker_id}.")

    def _record_quota_block(self, task: Task, error: QuotaExceededError) -> None:
        metadata = dict(task.metadata_json or {})
        metadata["quota_blocking_reason"] = {
            "error_code": error.error_code,
            "scope": error.scope,
            "limit": error.limit,
            "current": error.current,
        }
        task.metadata_json = metadata
        task.error = f"{error.error_code}:{error.scope}"
        self.session.flush()

    def _claim_queued_task(
        self,
        task: Task,
        *,
        worker_id: str,
        leased_until: datetime,
        now: datetime,
    ) -> Task | None:
        assert_task_transition(task.status, "leased")
        result = self.session.execute(
            update(Task)
            .where(
                Task.id == task.id,
                Task.status == "queued",
                Task.is_deleted.is_(False),
            )
            .values(
                status="leased",
                worker_id=worker_id,
                leased_until=leased_until,
                heartbeat_at=now,
                fencing_token=Task.fencing_token + 1,
            )
        )
        if cast(Any, result).rowcount != 1:
            self.session.expire(task)
            return None
        self.session.flush()
        self.session.refresh(task)
        return task

    def _active_partition_count(self, task: Task) -> int:
        statement = select(Task).where(
            Task.tenant_id == task.tenant_id,
            Task.project_id == task.project_id,
            Task.status.in_(["leased", "running"]),
            Task.is_deleted.is_(False),
        )
        return len(list(self.session.scalars(statement)))

    def _append_reaper_event(
        self,
        task: Task,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        EventRepository(self.session).append(
            event_id=f"event_{uuid4().hex[:12]}",
            run_id=task.run_id,
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            type=event_type,
            payload=payload,
            visibility_level="internal",
        )


def _error_message(error: dict[str, Any]) -> str:
    message = error.get("message")
    return str(message if message is not None else error)


def _decode_ref(value: str | None) -> dict[str, Any]:
    if not value or not value.startswith("json:"):
        return {}
    payload = json.loads(value.removeprefix("json:"))
    return payload if isinstance(payload, dict) else {}


def _task_metadata(task: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(task.get("metadata") or {})
    metadata.setdefault("partition_key", f"{task['tenant_id']}:{task['project_id']}")
    metadata.setdefault("resource_class", task.get("resource_class", "default"))
    if "agent_id" in task:
        metadata.setdefault("agent_id", task["agent_id"])
    if "deployment_id" in task and task["deployment_id"] is not None:
        metadata.setdefault("deployment_id", task["deployment_id"])
    return metadata
