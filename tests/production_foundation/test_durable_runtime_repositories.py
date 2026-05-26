from dimoo_run.domain.models import Agent, AgentVersion, Deployment, Run, Task
from dimoo_run.persistence.database import Base
from dimoo_run.persistence.repositories import (
    AgentRepository,
    AgentVersionRepository,
    AuditLogRepository,
    DeploymentRepository,
    EventRepository,
    RunRepository,
    TaskRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_durable_agent_version_run_task_event_flow() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        agents = AgentRepository(session)
        versions = AgentVersionRepository(session)
        deployments = DeploymentRepository(session)
        runs = RunRepository(session)
        tasks = TaskRepository(session)
        events = EventRepository(session)
        audits = AuditLogRepository(session)

        agent = agents.create(
            Agent(
                id="agent_1",
                tenant_id="tenant_1",
                project_id="project_1",
                name="support-agent",
                description=None,
            )
        )
        version = versions.create(
            AgentVersion(
                id="agent_version_1",
                agent_id=agent.id,
                version="0.1.0",
                package_uri="file://support-agent",
                framework="langgraph",
                adapter="langgraph",
                entrypoint="agent:create_agent",
            )
        )
        deployment = deployments.create(
            Deployment(
                id="deployment_1",
                tenant_id="tenant_1",
                project_id="project_1",
                agent_id=agent.id,
                agent_version_id=version.id,
                environment="dev",
                replicas=2,
            )
        )
        run = runs.create(
            Run(
                id="run_1",
                tenant_id="tenant_1",
                project_id="project_1",
                agent_id=agent.id,
                agent_version_id=version.id,
                input_ref="artifact://run_1/input",
                idempotency_key="idem_1",
            )
        )
        task = tasks.create(
            Task(
                id="task_1",
                run_id=run.id,
                tenant_id="tenant_1",
                project_id="project_1",
                idempotency_key="idem_1",
            )
        )

        first = events.append(
            event_id="event_record_1",
            run_id=run.id,
            tenant_id="tenant_1",
            project_id="project_1",
            type="run.created",
            payload={"task_id": task.id},
        )
        second = events.append(
            event_id="event_record_2",
            run_id=run.id,
            tenant_id="tenant_1",
            project_id="project_1",
            type="task.queued",
            payload={"task_id": task.id},
        )
        audits.append(
            audit_id="audit_1",
            tenant_id="tenant_1",
            project_id="project_1",
            action="run.create",
            resource_type="run",
            resource_id=run.id,
            result="allow",
            request_id="req_1",
        )
        session.commit()

        assert agents.get_by_name("tenant_1", "project_1", "support-agent") == agent
        assert versions.get_by_agent_version(agent.id, "0.1.0") == version
        assert (
            deployments.get_by_environment(
                "tenant_1",
                "project_1",
                environment="dev",
                agent_id=agent.id,
            )
            == deployment
        )
        assert runs.list_by_project("tenant_1", "project_1") == [run]
        assert tasks.list_by_run(run.id) == [task]
        assert [event.type for event in events.list_by_run(run.id)] == [
            "run.created",
            "task.queued",
        ]
        assert first.sequence == 1
        assert first.event_id == "run_1:1"
        assert second.sequence == 2
        assert second.event_id == "run_1:2"


def test_durable_run_and_task_transitions_set_timestamps() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        runs = RunRepository(session)
        tasks = TaskRepository(session)
        run = runs.create(
            Run(
                id="run_1",
                tenant_id="tenant_1",
                project_id="project_1",
                agent_id="agent_1",
                agent_version_id="agent_version_1",
            )
        )
        task = tasks.create(
            Task(
                id="task_1",
                run_id=run.id,
                tenant_id="tenant_1",
                project_id="project_1",
            )
        )

        running_run = runs.transition(run.id, "running")
        running_task = tasks.transition(task.id, "running", worker_id="worker_1")
        failed_run = runs.transition(run.id, "failed", error="boom")
        failed_task = tasks.transition(task.id, "failed", worker_id="worker_1", error="boom")

        assert running_run.started_at is not None
        assert running_task.started_at is not None
        assert failed_run.finished_at is not None
        assert failed_run.error == "boom"
        assert failed_task.finished_at is not None
        assert failed_task.error == "boom"


def test_durable_deployment_transition_updates_control_state() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        deployments = DeploymentRepository(session)
        deployment = deployments.create(
            Deployment(
                id="deployment_1",
                tenant_id="tenant_1",
                project_id="project_1",
                agent_id="agent_1",
                agent_version_id="agent_version_1",
                environment="prod",
            )
        )

        updated = deployments.transition(
            deployment.id,
            desired_status="active",
            runtime_status="warming_up",
        )

        assert updated.desired_status == "active"
        assert updated.runtime_status == "warming_up"
        assert deployments.list_by_project("tenant_1", "project_1") == [deployment]
