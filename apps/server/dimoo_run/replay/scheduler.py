from dimoo_run.runtime.run_manager import RuntimeRun, RuntimeRunStore
from dimoo_run.scheduler.backend import TaskBackend


class ReplayScheduler:
    def __init__(self, *, run_store: RuntimeRunStore, task_backend: TaskBackend) -> None:
        self.run_store = run_store
        self.task_backend = task_backend

    async def replay_run(
        self,
        *,
        source_run_id: int,
        candidate_agent_version_id: int | None = None,
    ) -> RuntimeRun:
        source = self.run_store.runs[source_run_id]
        replay = await self.run_store.create_run(
            tenant_id=source.tenant_id,
            project_id=source.project_id,
            agent_id=source.agent_id,
            agent_version_id=candidate_agent_version_id or source.agent_version_id,
            deployment_id=source.deployment_id,
            input_data=dict(source.input_data),
            thread_id=source.thread_id,
        )
        await self.task_backend.enqueue(
            {
                "run_id": replay.run_id,
                "tenant_id": replay.tenant_id,
                "project_id": replay.project_id,
                "agent_id": replay.agent_id,
                "agent_version_id": replay.agent_version_id,
                "deployment_id": replay.deployment_id,
                "input_data": replay.input_data,
                "queue": "default",
                "source_run_id": source_run_id,
            }
        )
        return replay
