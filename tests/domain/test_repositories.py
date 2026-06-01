import pytest
from dimoo_run.domain.models import Agent, AgentVersion, AuditLog, Event
from dimoo_run.persistence.database import Base
from dimoo_run.persistence.repositories import (
    AgentRepository,
    AgentVersionRepository,
    AuditLogRepository,
    EventRepository,
)
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
                tenant_id=1,
                project_id=1,
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
                tenant_id=1,
                project_id=1,
                action="agent.delete",
                resource_type="agent",
                resource_id="agent_1",
                result="allowed",
            )
        )
        session.commit()

        with pytest.raises(TypeError):
            repository.soft_delete_or_archive(audit_log.id, actor_id="user_1")


def test_repository_capabilities_match_model_shape() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        agent_version_repository = AgentVersionRepository(session)
        agent_version = agent_version_repository.create(
            AgentVersion(
                id="agent_version_1",
                agent_id=1,
                version="0.1.0",
                package_uri="file://package",
                framework="langgraph",
                adapter="langgraph",
                entrypoint="agent:graph",
            )
        )

        updated_version = agent_version_repository.update_status("agent_version_1", "published")
        assert updated_version == agent_version
        assert updated_version.status == "published"
        assert not hasattr(agent_version_repository, "list_by_project")

        event_repository = EventRepository(session)
        event = event_repository.create(
            Event(
                id="event_1",
                run_id=1,
                tenant_id=1,
                project_id=1,
                type="run.started",
                sequence=1,
                event_id="run_1:1",
            )
        )
        assert event_repository.list_by_project("tenant_1", "project_1") == [event]
        assert not hasattr(event_repository, "update_status")
