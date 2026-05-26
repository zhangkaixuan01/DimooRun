import pytest
from dimoo_run.deployments.service import DeploymentRecord, DeploymentRuntimeControlService
from dimoo_run.domain.enums import DeploymentDesiredStatus
from dimoo_run.runtime.run_manager import InMemoryRunStore, RunManager
from dimoo_run.scheduler.in_memory import InMemoryTaskBackend


class FailingEnqueueBackend(InMemoryTaskBackend):
    async def enqueue(self, task: dict[str, object]) -> str:
        raise RuntimeError("enqueue failed")


async def test_run_manager_creates_run_and_enqueues_task() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    manager = RunManager(run_store=run_store, task_backend=task_backend)

    run, task_id = await manager.create_run_task(
        tenant_id="tenant_1",
        project_id="project_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        deployment_id="deployment_1",
        input_data={"message": "hello"},
    )

    assert run.status == "pending"
    assert task_backend.tasks[task_id].run_id == run.run_id
    assert task_backend.tasks[task_id].payload["input_data"] == {"message": "hello"}


async def test_run_manager_removes_created_run_when_enqueue_fails() -> None:
    run_store = InMemoryRunStore()
    manager = RunManager(run_store=run_store, task_backend=FailingEnqueueBackend())

    with pytest.raises(RuntimeError, match="enqueue failed"):
        await manager.create_run_task(
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="version_1",
            deployment_id="deployment_1",
            input_data={"message": "hello"},
            run_id="run_1",
        )

    assert "run_1" not in run_store.runs


async def test_run_manager_rejects_cross_scope_deployment_run() -> None:
    gate = DeploymentRuntimeControlService()
    gate.deployments.add(
        DeploymentRecord(
            id="deployment_1",
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="version_1",
            environment="prod",
            desired_status=DeploymentDesiredStatus.active,
        )
    )
    manager = RunManager(
        run_store=InMemoryRunStore(),
        task_backend=InMemoryTaskBackend(),
        deployment_gate=gate,
    )

    with pytest.raises(PermissionError, match="deployment_scope_mismatch"):
        await manager.create_run_task(
            tenant_id="tenant_2",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="version_1",
            deployment_id="deployment_1",
            input_data={"message": "hello"},
        )


async def test_run_manager_rejects_deployment_agent_version_mismatch() -> None:
    gate = DeploymentRuntimeControlService()
    gate.deployments.add(
        DeploymentRecord(
            id="deployment_1",
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="version_1",
            environment="prod",
            desired_status=DeploymentDesiredStatus.active,
        )
    )
    manager = RunManager(
        run_store=InMemoryRunStore(),
        task_backend=InMemoryTaskBackend(),
        deployment_gate=gate,
    )

    with pytest.raises(PermissionError, match="deployment_agent_version_mismatch"):
        await manager.create_run_task(
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="version_2",
            deployment_id="deployment_1",
            input_data={"message": "hello"},
        )
