from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from dimoo_run.policy.engine import AuditRecord, AuditSink, InMemoryAuditSink


@dataclass
class HumanTaskRecord:
    id: int
    tenant_id: int
    project_id: int | None
    run_id: int | None
    attempt_id: int | None
    task_id: int | None
    type: str
    status: str
    payload: dict[str, Any]
    requested_by: str | None
    assignee_user_id: str | None = None
    assignee_role: str | None = None
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None


class HumanTaskService:
    def __init__(
        self,
        *,
        audit_sink: AuditSink | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.audit_sink = audit_sink or InMemoryAuditSink()
        self._now = now or (lambda: datetime.now(UTC))
        self.tasks: dict[int, HumanTaskRecord] = {}
        self._next_id = 1

    def create_approval(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        run_id: int | None,
        attempt_id: int | None,
        task_id: int | None,
        payload: dict[str, Any],
        requested_by: str | None,
        assignee_role: str | None = None,
        expires_at: datetime | None = None,
    ) -> HumanTaskRecord:
        task = HumanTaskRecord(
            id=self._next_id,
            tenant_id=tenant_id,
            project_id=project_id,
            run_id=run_id,
            attempt_id=attempt_id,
            task_id=task_id,
            type="approval",
            status="pending",
            payload=payload,
            requested_by=requested_by,
            assignee_role=assignee_role,
            expires_at=expires_at,
            created_at=self._now(),
        )
        self._next_id += 1
        self.tasks[task.id] = task
        self.audit_sink.write(
            AuditRecord(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=requested_by,
                actor_type="user" if requested_by else "system",
                resource_type="human_task",
                resource_id=task.id,
                action="create",
                result="allow",
                metadata={"type": task.type, "status": task.status},
            )
        )
        return task

    def decide(
        self,
        task_id: int,
        *,
        actor_id: str,
        approved: bool,
        payload: dict[str, Any] | None = None,
    ) -> HumanTaskRecord:
        task = self.tasks[task_id]
        if task.requested_by == actor_id:
            raise PermissionError("approval_self_review_denied")
        if task.status != "pending":
            raise PermissionError("human_task_not_pending")
        task.status = "approved" if approved else "rejected"
        task.payload = {**task.payload, "decision": payload or {}}
        task.updated_at = self._now()
        self.audit_sink.write(
            AuditRecord(
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                actor_id=actor_id,
                actor_type="user",
                resource_type="human_task",
                resource_id=task.id,
                action="decide",
                result=task.status,
                metadata={"approved": approved},
            )
        )
        return task
