import pytest
from dimoo_run.domain.models import Agent, AuditLog
from dimoo_run.persistence.database import Base
from dimoo_run.persistence.repositories import AgentRepository, AuditLogRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_repository_create_get_list_update_and_soft_delete() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = AgentRepository(session)
        agent = repository.create(
            Agent(
                id="agent_1",
                tenant_id="tenant_1",
                project_id="project_1",
                name="support-agent",
                description=None,
                owner_id="user_1",
            )
        )
        session.commit()

        assert repository.get_by_id("agent_1") == agent
        assert repository.list_by_project("tenant_1", "project_1") == [agent]

        updated_agent = repository.update_status("agent_1", "paused")
        session.commit()
        assert updated_agent.status == "paused"

        archived_agent = repository.soft_delete_or_archive("agent_1", actor_id="user_1")
        session.commit()
        assert archived_agent.status == "archived"
        assert archived_agent.is_deleted is True
        assert archived_agent.deleted_by == "user_1"
        assert archived_agent.deleted_at is not None
        assert repository.get_by_id("agent_1") is None
        assert repository.get_by_id("agent_1", include_deleted=True) == archived_agent
        assert repository.list_by_project("tenant_1", "project_1") == []
        assert repository.list_by_project("tenant_1", "project_1", include_deleted=True) == [
            archived_agent
        ]


def test_audit_log_repository_rejects_soft_delete() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = AuditLogRepository(session)
        audit_log = repository.create(
            AuditLog(
                id="audit_1",
                tenant_id="tenant_1",
                project_id="project_1",
                action="agent.delete",
                resource_type="agent",
                resource_id="agent_1",
                result="allowed",
            )
        )
        session.commit()

        with pytest.raises(TypeError):
            repository.soft_delete_or_archive(audit_log.id, actor_id="user_1")
