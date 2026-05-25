from dataclasses import dataclass
from typing import Any

from dimoo_run.adapters.base.contract import AgentAdapter
from dimoo_run.adapters.base.utils import maybe_await
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult
from dimoo_run.runtime.run_manager import RuntimeRunStore
from dimoo_run.scheduler.backend import RuntimeTaskBackend
from dimoo_run.streaming.replay_buffer import ReplayBuffer


@dataclass(frozen=True)
class AgentRuntimeSpec:
    adapter: str
    package_uri: str
    manifest: dict[str, Any]
    runtime_config: dict[str, Any]


@dataclass(frozen=True)
class WorkerExecutionResult:
    task_id: str
    run_id: str
    attempt_id: str
    status: str


class WorkerExecutor:
    def __init__(
        self,
        *,
        worker_id: str,
        task_backend: RuntimeTaskBackend,
        run_store: RuntimeRunStore,
        replay_buffer: ReplayBuffer,
        adapters: dict[str, AgentAdapter],
        agent_specs: dict[str, AgentRuntimeSpec],
    ) -> None:
        self.worker_id = worker_id
        self.task_backend = task_backend
        self.run_store = run_store
        self.replay_buffer = replay_buffer
        self.adapters = adapters
        self.agent_specs = agent_specs

    async def execute_once(
        self,
        *,
        queue: str,
        lease_seconds: int = 30,
    ) -> WorkerExecutionResult | None:
        leased = await self.task_backend.lease(
            queue,
            worker_id=self.worker_id,
            lease_seconds=lease_seconds,
        )
        if leased is None:
            return None

        task_id = leased["task_id"]
        run_id = leased["run_id"]
        fencing_token = leased["fencing_token"]
        self.task_backend.mark_running(task_id, self.worker_id, fencing_token)
        attempt = await self.run_store.create_attempt(
            run_id=run_id,
            task_id=task_id,
            worker_id=self.worker_id,
        )
        self._append(run_id, attempt.attempt_id, AgentEvent(type="attempt.started", payload={}))

        run = self.run_store.runs[run_id]
        spec = self.agent_specs[run.agent_version_id]
        adapter = self.adapters[spec.adapter]
        context = RuntimeContext(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            run_id=run.run_id,
            task_id=task_id,
            agent_id=run.agent_id,
            agent_version_id=run.agent_version_id,
            deployment_id=run.deployment_id,
            thread_id=run.thread_id,
            framework=getattr(adapter, "framework", spec.adapter),
            adapter=spec.adapter,
        )

        try:
            agent = await adapter.load(spec.package_uri, spec.manifest, spec.runtime_config)
            result = await self._execute_agent(adapter, agent, leased, context, attempt.attempt_id)
        except Exception as exc:
            error = {"message": str(exc), "type": exc.__class__.__name__}
            self.run_store.fail_attempt(attempt.attempt_id, error)
            self._append(
                run_id,
                attempt.attempt_id,
                AgentEvent(type="attempt.failed", payload=error),
            )
            will_retry = self.task_backend.will_retry(task_id)
            if not will_retry:
                self.run_store.fail_run(run_id, error)
                self._append(
                    run_id,
                    attempt.attempt_id,
                    AgentEvent(type="run.failed", payload=error),
                )
                self._append(
                    run_id,
                    attempt.attempt_id,
                    AgentEvent(type="stream.failed", payload=error),
                )
            else:
                self._append(
                    run_id,
                    attempt.attempt_id,
                    AgentEvent(type="task.retrying", payload=error),
                )
            await self.task_backend.fail(task_id, self.worker_id, fencing_token, error)
            return WorkerExecutionResult(
                task_id=task_id,
                run_id=run_id,
                attempt_id=attempt.attempt_id,
                status="failed",
            )

        await self.task_backend.complete(task_id, self.worker_id, fencing_token)
        self.run_store.complete_run(run_id, result.output)
        self.run_store.complete_attempt(attempt.attempt_id)
        self._append(
            run_id,
            attempt.attempt_id,
            AgentEvent(type="run.completed", payload={"output": result.output}),
        )
        self._append(
            run_id,
            attempt.attempt_id,
            AgentEvent(type="stream.completed", payload={}),
        )
        return WorkerExecutionResult(
            task_id=task_id,
            run_id=run_id,
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )

    def _append(self, run_id: str, attempt_id: str, event: AgentEvent) -> AgentEvent:
        return self.replay_buffer.append(run_id, attempt_id, event)

    async def _execute_agent(
        self,
        adapter: AgentAdapter,
        agent: Any,
        leased: dict[str, Any],
        context: RuntimeContext,
        attempt_id: str,
    ) -> AgentResult:
        if leased.get("execution_mode") != "stream":
            result = await adapter.invoke(agent, leased["input_data"], context)
            for event in result.events:
                self._append(context.run_id, attempt_id, event)
            return result

        stream_result: Any = adapter.stream(agent, leased["input_data"], context)
        stream = await maybe_await(stream_result)
        async for event in stream:
            self._append(context.run_id, attempt_id, event)
        return AgentResult(output={"streamed": True})
