from dimoo_run.runtime.run_manager import InMemoryRunStore, RunManager
from dimoo_run.scheduler.in_memory import InMemoryTaskBackend


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
