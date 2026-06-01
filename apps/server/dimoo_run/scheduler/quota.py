from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.domain.models import Run, Task


class QuotaExceededError(RuntimeError):
    def __init__(self, *, scope: str, limit: int, current: int) -> None:
        self.error_code = "runtime_quota_exceeded"
        self.scope = scope
        self.limit = limit
        self.current = current
        super().__init__(f"{scope} concurrency quota exceeded: {current}/{limit}")


@dataclass(frozen=True)
class RuntimeQuota:
    tenant_max_running_tasks: int | None = None
    project_max_running_tasks: int | None = None
    agent_max_running_tasks: int | None = None
    deployment_max_running_tasks: int | None = None


class SQLAlchemyQuotaPolicy:
    def __init__(self, session: Session, quota: RuntimeQuota) -> None:
        self.session = session
        self.quota = quota

    def assert_can_lease(self, task: Task) -> None:
        self._assert_task_within_quota(task)

    def assert_can_enqueue(
        self,
        *,
        tenant_id: int,
        project_id: int,
        agent_id: int | None = None,
        deployment_id: int | None = None,
    ) -> None:
        if self.quota.tenant_max_running_tasks is not None:
            current = self._count_running(tenant_id=tenant_id, project_id=None)
            if current >= self.quota.tenant_max_running_tasks:
                raise QuotaExceededError(
                    scope="tenant",
                    limit=self.quota.tenant_max_running_tasks,
                    current=current,
                )
        if self.quota.project_max_running_tasks is not None:
            current = self._count_running(tenant_id=tenant_id, project_id=project_id)
            if current >= self.quota.project_max_running_tasks:
                raise QuotaExceededError(
                    scope="project",
                    limit=self.quota.project_max_running_tasks,
                    current=current,
                )
        if self.quota.agent_max_running_tasks is not None and agent_id is not None:
            current = self._count_running_for_run_binding(
                tenant_id=tenant_id,
                project_id=project_id,
                agent_id=agent_id,
                deployment_id=None,
            )
            if current >= self.quota.agent_max_running_tasks:
                raise QuotaExceededError(
                    scope="agent",
                    limit=self.quota.agent_max_running_tasks,
                    current=current,
                )
        if self.quota.deployment_max_running_tasks is not None and deployment_id is not None:
            current = self._count_running_for_run_binding(
                tenant_id=tenant_id,
                project_id=project_id,
                agent_id=None,
                deployment_id=deployment_id,
            )
            if current >= self.quota.deployment_max_running_tasks:
                raise QuotaExceededError(
                    scope="deployment",
                    limit=self.quota.deployment_max_running_tasks,
                    current=current,
                )

    def _assert_task_within_quota(self, task: Task) -> None:
        self.assert_can_enqueue(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            agent_id=None,
            deployment_id=None,
        )
        run = self.session.get(Run, task.run_id)
        if run is None:
            return
        if self.quota.agent_max_running_tasks is not None:
            current = self._count_running_for_run_binding(
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                agent_id=run.agent_id,
                deployment_id=None,
            )
            if current >= self.quota.agent_max_running_tasks:
                raise QuotaExceededError(
                    scope="agent",
                    limit=self.quota.agent_max_running_tasks,
                    current=current,
                )
        if (
            self.quota.deployment_max_running_tasks is not None
            and run.deployment_id is not None
        ):
            current = self._count_running_for_run_binding(
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                agent_id=None,
                deployment_id=run.deployment_id,
            )
            if current >= self.quota.deployment_max_running_tasks:
                raise QuotaExceededError(
                    scope="deployment",
                    limit=self.quota.deployment_max_running_tasks,
                    current=current,
                )

    def _count_running(self, *, tenant_id: int, project_id: int | None) -> int:
        conditions = [
            Task.tenant_id == tenant_id,
            Task.status.in_(["leased", "running"]),
            Task.is_deleted.is_(False),
        ]
        if project_id is not None:
            conditions.append(Task.project_id == project_id)
        return len(list(self.session.scalars(select(Task).where(*conditions))))

    def _count_running_for_run_binding(
        self,
        *,
        tenant_id: int,
        project_id: int,
        agent_id: int | None,
        deployment_id: int | None,
    ) -> int:
        conditions = [
            Task.tenant_id == tenant_id,
            Task.project_id == project_id,
            Task.status.in_(["leased", "running"]),
            Task.is_deleted.is_(False),
            Task.run_id == Run.id,
        ]
        if agent_id is not None:
            conditions.append(Run.agent_id == agent_id)
        if deployment_id is not None:
            conditions.append(Run.deployment_id == deployment_id)
        return len(list(self.session.scalars(select(Task).where(*conditions))))
