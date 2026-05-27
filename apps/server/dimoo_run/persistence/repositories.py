from datetime import UTC, datetime
from typing import Any, Generic, Protocol, TypeVar, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.domain.models import (
    Agent,
    AgentVersion,
    AuditLog,
    Deployment,
    Environment,
    Event,
    Project,
    Run,
    Task,
    Tenant,
)

ModelT = TypeVar("ModelT", bound=Any)
ModelT_co = TypeVar("ModelT_co", covariant=True)


class SupportsGetById(Protocol[ModelT_co]):
    def get_by_id(self, entity_id: str, *, include_deleted: bool = False) -> ModelT_co | None: ...


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def create(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        return instance

    def get_by_id(self, entity_id: str, *, include_deleted: bool = False) -> ModelT | None:
        instance = self.session.get(self.model, entity_id)
        if instance is None:
            return None
        if not include_deleted and getattr(instance, "is_deleted", False):
            return None
        return instance


class ProjectScopedRepositoryMixin(Generic[ModelT]):
    model: type[ModelT]
    session: Session

    def list_by_project(
        self,
        tenant_id: str,
        project_id: str,
        *,
        include_deleted: bool = False,
    ) -> list[ModelT]:
        conditions = [
            self.model.tenant_id == tenant_id,
            self.model.project_id == project_id,
        ]
        if not include_deleted:
            conditions.append(self.model.is_deleted.is_(False))
        statement = select(self.model).where(*conditions)
        return list(self.session.scalars(statement))


class StatusRepositoryMixin(Generic[ModelT]):
    def update_status(self, entity_id: str, status: str) -> ModelT:
        repository = cast(SupportsGetById[ModelT], self)
        instance = repository.get_by_id(entity_id)
        if instance is None:
            raise KeyError(entity_id)
        instance.status = status
        return instance


class SoftDeleteRepositoryMixin(Generic[ModelT]):
    def soft_delete(self, entity_id: str, actor_id: str | None = None) -> ModelT:
        repository = cast(SupportsGetById[ModelT], self)
        instance = repository.get_by_id(entity_id)
        if instance is None:
            raise KeyError(entity_id)
        instance.is_deleted = True
        instance.deleted_at = datetime.now(UTC)
        instance.deleted_by = actor_id
        return instance


class ArchivableRepositoryMixin(StatusRepositoryMixin[ModelT], SoftDeleteRepositoryMixin[ModelT]):
    def soft_delete_or_archive(self, entity_id: str, actor_id: str | None = None) -> ModelT:
        instance = self.update_status(entity_id, "archived")
        instance.is_deleted = True
        instance.deleted_at = datetime.now(UTC)
        instance.deleted_by = actor_id
        return instance


class AgentRepository(
    ArchivableRepositoryMixin[Agent],
    ProjectScopedRepositoryMixin[Agent],
    BaseRepository[Agent],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Agent)

    def get_by_name(self, tenant_id: str, project_id: str, name: str) -> Agent | None:
        statement = select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.project_id == project_id,
            Agent.name == name,
            Agent.is_deleted.is_(False),
        )
        return self.session.scalar(statement)


class TenantRepository(
    StatusRepositoryMixin[Tenant],
    SoftDeleteRepositoryMixin[Tenant],
    BaseRepository[Tenant],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Tenant)

    def list_active(self, *, include_deleted: bool = False) -> list[Tenant]:
        conditions = []
        if not include_deleted:
            conditions.append(Tenant.is_deleted.is_(False))
        statement = select(Tenant).where(*conditions).order_by(Tenant.created_at.desc())
        return list(self.session.scalars(statement))


class ProjectRepository(
    StatusRepositoryMixin[Project],
    SoftDeleteRepositoryMixin[Project],
    BaseRepository[Project],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Project)

    def list_by_tenant(self, tenant_id: str, *, include_deleted: bool = False) -> list[Project]:
        conditions = [Project.tenant_id == tenant_id]
        if not include_deleted:
            conditions.append(Project.is_deleted.is_(False))
        statement = select(Project).where(*conditions).order_by(Project.created_at.desc())
        return list(self.session.scalars(statement))


class EnvironmentRepository(
    StatusRepositoryMixin[Environment],
    SoftDeleteRepositoryMixin[Environment],
    ProjectScopedRepositoryMixin[Environment],
    BaseRepository[Environment],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Environment)


class AgentVersionRepository(StatusRepositoryMixin[AgentVersion], BaseRepository[AgentVersion]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AgentVersion)

    def list_by_agent(self, agent_id: str) -> list[AgentVersion]:
        statement = select(AgentVersion).where(
            AgentVersion.agent_id == agent_id,
            AgentVersion.is_deleted.is_(False),
        )
        return list(self.session.scalars(statement))

    def get_by_agent_version(self, agent_id: str, version: str) -> AgentVersion | None:
        statement = select(AgentVersion).where(
            AgentVersion.agent_id == agent_id,
            AgentVersion.version == version,
            AgentVersion.is_deleted.is_(False),
        )
        return self.session.scalar(statement)


class DeploymentRepository(
    ArchivableRepositoryMixin[Deployment],
    ProjectScopedRepositoryMixin[Deployment],
    BaseRepository[Deployment],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Deployment)

    def get_by_environment(
        self,
        tenant_id: str,
        project_id: str,
        *,
        environment: str,
        agent_id: str,
    ) -> Deployment | None:
        statement = select(Deployment).where(
            Deployment.tenant_id == tenant_id,
            Deployment.project_id == project_id,
            Deployment.environment == environment,
            Deployment.agent_id == agent_id,
            Deployment.is_deleted.is_(False),
        )
        return self.session.scalar(statement)

    def transition(
        self,
        deployment_id: str,
        *,
        desired_status: str | None = None,
        runtime_status: str | None = None,
        last_runtime_error: str | None = None,
    ) -> Deployment:
        deployment = self.get_by_id(deployment_id)
        if deployment is None:
            raise KeyError(deployment_id)
        if desired_status is not None:
            deployment.desired_status = desired_status
        if runtime_status is not None:
            deployment.runtime_status = runtime_status
        deployment.last_runtime_error = last_runtime_error
        return deployment


class RunRepository(
    ArchivableRepositoryMixin[Run],
    ProjectScopedRepositoryMixin[Run],
    BaseRepository[Run],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Run)

    def transition(self, run_id: str, status: str, *, error: str | None = None) -> Run:
        run = self.get_by_id(run_id)
        if run is None:
            raise KeyError(run_id)
        run.status = status
        run.error = error
        if status in {"running"} and run.started_at is None:
            run.started_at = datetime.now(UTC)
        if status in {"succeeded", "failed", "cancelled", "timeout"}:
            run.finished_at = datetime.now(UTC)
        return run


class TaskRepository(
    StatusRepositoryMixin[Task],
    SoftDeleteRepositoryMixin[Task],
    ProjectScopedRepositoryMixin[Task],
    BaseRepository[Task],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Task)

    def list_by_run(self, run_id: str) -> list[Task]:
        statement = select(Task).where(
            Task.run_id == run_id,
            Task.is_deleted.is_(False),
        )
        return list(self.session.scalars(statement))

    def transition(
        self,
        task_id: str,
        status: str,
        *,
        worker_id: str | None = None,
        error: str | None = None,
    ) -> Task:
        task = self.get_by_id(task_id)
        if task is None:
            raise KeyError(task_id)
        task.status = status
        task.worker_id = worker_id
        task.error = error
        if status == "running" and task.started_at is None:
            task.started_at = datetime.now(UTC)
        if status in {"succeeded", "failed", "dead_letter", "cancelled"}:
            task.finished_at = datetime.now(UTC)
        return task


class EventRepository(
    SoftDeleteRepositoryMixin[Event],
    ProjectScopedRepositoryMixin[Event],
    BaseRepository[Event],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Event)

    def next_sequence(self, run_id: str) -> int:
        events = self.list_by_run(run_id)
        if not events:
            return 1
        return max(event.sequence for event in events) + 1

    def append(
        self,
        *,
        event_id: str,
        run_id: str,
        tenant_id: str,
        project_id: str,
        type: str,
        payload: dict[str, Any] | None = None,
        attempt_id: str | None = None,
        framework: str | None = None,
        visibility_level: str = "internal",
    ) -> Event:
        sequence = self.next_sequence(run_id)
        event = Event(
            id=event_id,
            run_id=run_id,
            attempt_id=attempt_id,
            tenant_id=tenant_id,
            project_id=project_id,
            type=type,
            sequence=sequence,
            event_id=f"{run_id}:{sequence}",
            framework=framework,
            payload_json=payload or {},
            visibility_level=visibility_level,
        )
        return self.create(event)

    def list_by_run(self, run_id: str) -> list[Event]:
        statement = (
            select(Event)
            .where(Event.run_id == run_id, Event.is_deleted.is_(False))
            .order_by(Event.sequence)
        )
        return list(self.session.scalars(statement))


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AuditLog)

    def append(
        self,
        *,
        audit_id: str,
        tenant_id: str,
        project_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        result: str,
        actor_id: str | None = None,
        actor_type: str = "system",
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        return self.create(
            AuditLog(
                id=audit_id,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                actor_type=actor_type,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                result=result,
                request_id=request_id,
                metadata_json=metadata or {},
            )
        )

    def soft_delete_or_archive(self, entity_id: str, actor_id: str | None = None) -> AuditLog:
        _ = entity_id, actor_id
        raise TypeError("AuditLog is immutable and cannot be soft deleted.")
