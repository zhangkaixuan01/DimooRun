from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.domain.models import Agent, AgentVersion, AuditLog, Deployment, Event, Run, Task

ModelT = TypeVar("ModelT", bound=Any)


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def create(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        return instance

    def get_by_id(self, entity_id: str) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def list_by_project(self, tenant_id: str, project_id: str) -> list[ModelT]:
        statement = select(self.model).where(
            self.model.tenant_id == tenant_id,
            self.model.project_id == project_id,
        )
        return list(self.session.scalars(statement))

    def update_status(self, entity_id: str, status: str) -> ModelT:
        instance = self.get_by_id(entity_id)
        if instance is None:
            raise KeyError(entity_id)
        instance.status = status
        return instance

    def soft_delete_or_archive(self, entity_id: str) -> ModelT:
        return self.update_status(entity_id, "archived")


class AgentRepository(BaseRepository[Agent]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Agent)


class AgentVersionRepository(BaseRepository[AgentVersion]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AgentVersion)


class DeploymentRepository(BaseRepository[Deployment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Deployment)


class RunRepository(BaseRepository[Run]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Run)


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Task)


class EventRepository(BaseRepository[Event]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Event)


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AuditLog)
