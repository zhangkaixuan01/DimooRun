from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.domain.models import ApprovalRequest, HumanTask
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


class SQLAlchemyHumanTaskService:
    def __init__(
        self,
        *,
        session: Session,
        audit_sink: AuditSink | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.audit_sink = audit_sink or InMemoryAuditSink()
        self._now = now or (lambda: datetime.now(UTC))

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
        task = HumanTask(
            tenant_id=tenant_id,
            project_id=project_id,
            run_id=run_id,
            attempt_id=attempt_id,
            task_id=task_id,
            type="approval",
            status="pending",
            assignee_role=assignee_role,
            payload_ref="inline:payload",
            expires_at=expires_at,
        )
        self.session.add(task)
        self.session.flush()
        approval = ApprovalRequest(
            tenant_id=tenant_id,
            project_id=project_id,
            human_task_id=task.id,
            requested_by=requested_by,
            status="pending",
            metadata_json={"payload": payload},
        )
        self.session.add(approval)
        self.session.flush()
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
        return HumanTaskRecord(
            id=task.id,
            tenant_id=tenant_id,
            project_id=project_id,
            run_id=run_id,
            attempt_id=attempt_id,
            task_id=task_id,
            type=task.type,
            status=task.status,
            payload=payload,
            requested_by=requested_by,
            assignee_role=assignee_role,
            expires_at=expires_at,
            created_at=task.created_at or self._now(),
            updated_at=task.updated_at,
        )

    def decide(
        self,
        task_id: int,
        *,
        actor_id: str,
        approved: bool,
        payload: dict[str, Any] | None = None,
    ) -> HumanTaskRecord:
        task = self.session.get(HumanTask, task_id)
        if task is None:
            raise KeyError(task_id)
        approval = self.session.scalar(
            select(ApprovalRequest)
            .where(ApprovalRequest.human_task_id == task_id)
            .order_by(ApprovalRequest.id.desc())
        )
        requested_by = approval.requested_by if approval is not None else None
        if requested_by == actor_id:
            raise PermissionError("approval_self_review_denied")
        if task.status != "pending":
            raise PermissionError("human_task_not_pending")
        task.status = "approved" if approved else "rejected"
        task.decision_ref = "inline:decision"
        task.updated_at = self._now()
        if approval is not None:
            approval.status = task.status
            approval.decision_ref = "inline:decision"
            metadata = dict(approval.metadata_json or {})
            metadata["decision"] = payload or {}
            approval.metadata_json = metadata
        self.session.flush()
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
        payload_data = {}
        if approval is not None and isinstance(approval.metadata_json, dict):
            payload_data = dict(approval.metadata_json.get("payload") or {})
            if payload:
                payload_data["decision"] = payload
        return HumanTaskRecord(
            id=task.id,
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            run_id=task.run_id,
            attempt_id=task.attempt_id,
            task_id=task.task_id,
            type=task.type,
            status=task.status,
            payload=payload_data,
            requested_by=requested_by,
            assignee_user_id=str(task.assignee_user_id) if task.assignee_user_id else None,
            assignee_role=task.assignee_role,
            expires_at=task.expires_at,
            created_at=task.created_at or self._now(),
            updated_at=task.updated_at,
        )
