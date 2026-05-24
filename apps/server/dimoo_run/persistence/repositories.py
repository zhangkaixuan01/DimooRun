from datetime import UTC, datetime
from typing import Any, Generic, Protocol, TypeVar, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.domain.models import Agent, AgentVersion, AuditLog, Deployment, Event, Run, Task

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


class AgentVersionRepository(StatusRepositoryMixin[AgentVersion], BaseRepository[AgentVersion]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AgentVersion)


class DeploymentRepository(
    ArchivableRepositoryMixin[Deployment],
    ProjectScopedRepositoryMixin[Deployment],
    BaseRepository[Deployment],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Deployment)


class RunRepository(
    ArchivableRepositoryMixin[Run],
    ProjectScopedRepositoryMixin[Run],
    BaseRepository[Run],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Run)


class TaskRepository(
    StatusRepositoryMixin[Task],
    SoftDeleteRepositoryMixin[Task],
    ProjectScopedRepositoryMixin[Task],
    BaseRepository[Task],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Task)


class EventRepository(
    SoftDeleteRepositoryMixin[Event],
    ProjectScopedRepositoryMixin[Event],
    BaseRepository[Event],
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Event)


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AuditLog)

    def soft_delete_or_archive(self, entity_id: str, actor_id: str | None = None) -> AuditLog:
        _ = entity_id, actor_id
        raise TypeError("AuditLog is immutable and cannot be soft deleted.")
