from dimoo_run.domain.models import Agent
from dimoo_run.persistence.database import Base
from dimoo_run.persistence.repositories import AgentRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_repository_create_get_list_update_and_archive() -> None:
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

        archived_agent = repository.soft_delete_or_archive("agent_1")
        session.commit()
        assert archived_agent.status == "archived"
