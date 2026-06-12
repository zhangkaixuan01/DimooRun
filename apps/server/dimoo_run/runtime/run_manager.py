from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from dimoo_run.runtime.state_machine import (
    assert_run_attempt_transition,
    assert_run_transition,
)
from dimoo_run.scheduler.backend import TaskBackend


@dataclass
class RuntimeRun:
    run_id: int
    tenant_id: int
    project_id: int
    agent_id: int
    agent_version_id: int
    deployment_id: int | None
    input_data: dict[str, Any]
    override_config: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    thread_id: str | None = None
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RuntimeAttempt:
    attempt_id: int
    run_id: int
    task_id: int
    worker_id: str
    attempt_no: int
    status: str = "running"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error: dict[str, Any] | None = None


@dataclass(frozen=True)
class RuntimeGovernanceBundle:
    secret_provider: Any | None = None
    model_gateway: Any | None = None
    tool_gateway: Any | None = None

    def apply(self, runtime_config: dict[str, Any]) -> dict[str, Any]:
        governance = {
            "secrets": self.secret_provider,
            "model_gateway": self.model_gateway,
            "tools": self.tool_gateway,
        }
        services = {key: value for key, value in governance.items() if value is not None}
        if not services:
            return dict(runtime_config)
        merged = dict(runtime_config)
        merged["governance"] = services
        return merged


class RuntimeRunStore(Protocol):
    @property
    def runs(self) -> dict[int, RuntimeRun]: ...

    @property
    def attempts(self) -> dict[int, RuntimeAttempt]: ...

    async def create_run(
        self,
        *,
        tenant_id: int,
        project_id: int,
        agent_id: int,
        agent_version_id: int,
        deployment_id: int | None,
        input_data: dict[str, Any],
        override_config: dict[str, Any] | None = None,
        thread_id: str | None = None,
        run_id: int | None = None,
    ) -> RuntimeRun: ...

    async def create_attempt(
        self,
        *,
        run_id: int,
        task_id: int,
        worker_id: str,
    ) -> RuntimeAttempt: ...

    def complete_run(self, run_id: int, output: dict[str, Any]) -> None: ...

    def fail_run(self, run_id: int, error: dict[str, Any]) -> None: ...

    def timeout_run(self, run_id: int, error: dict[str, Any]) -> None: ...

    def get_run(self, run_id: int) -> RuntimeRun: ...

    def mark_run_running(self, run_id: int) -> None: ...

    def cancel_run(self, run_id: int) -> None: ...

    def delete_run(self, run_id: int) -> None: ...

    def complete_attempt(self, attempt_id: int) -> None: ...

    def fail_attempt(self, attempt_id: int, error: dict[str, Any]) -> None: ...

    def timeout_attempt(self, attempt_id: int, error: dict[str, Any]) -> None: ...


class DeploymentRunGate(Protocol):
    def assert_accepts_new_run(
        self,
        deployment_id: int,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        agent_id: int | None = None,
        agent_version_id: int | None = None,
    ) -> None: ...


class InMemoryRunStore:
    def __init__(self) -> None:
        self.runs: dict[int, RuntimeRun] = {}
        self.attempts: dict[int, RuntimeAttempt] = {}
        self._next_run_id = 1
        self._next_attempt_id = 1

    async def create_run(
        self,
        *,
        tenant_id: int,
        project_id: int,
        agent_id: int,
        agent_version_id: int,
        deployment_id: int | None,
        input_data: dict[str, Any],
        override_config: dict[str, Any] | None = None,
        thread_id: str | None = None,
        run_id: int | None = None,
    ) -> RuntimeRun:
        run = RuntimeRun(
            run_id=run_id or self._next_run_id,
            tenant_id=tenant_id,
            project_id=project_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            deployment_id=deployment_id,
            input_data=input_data,
            override_config=dict(override_config or {}),
            thread_id=thread_id,
        )
        if run_id is None:
            self._next_run_id += 1
        else:
            self._next_run_id = max(self._next_run_id, run_id + 1)
        self.runs[run.run_id] = run
        return run

    async def create_attempt(
        self,
        *,
        run_id: int,
        task_id: int,
        worker_id: str,
    ) -> RuntimeAttempt:
        attempt_no = (
            len([attempt for attempt in self.attempts.values() if attempt.run_id == run_id]) + 1
        )
        attempt = RuntimeAttempt(
            attempt_id=self._next_attempt_id,
            run_id=run_id,
            task_id=task_id,
            worker_id=worker_id,
            attempt_no=attempt_no,
        )
        self._next_attempt_id += 1
        self.attempts[attempt.attempt_id] = attempt
        if self.runs[run_id].status != "running":
            assert_run_transition(self.runs[run_id].status, "running")
            self.runs[run_id].status = "running"
        return attempt

    def get_run(self, run_id: int) -> RuntimeRun:
        return self.runs[run_id]

    def complete_run(self, run_id: int, output: dict[str, Any]) -> None:
        run = self.runs[run_id]
        if run.status == "pending":
            assert_run_transition(run.status, "running")
            run.status = "running"
        assert_run_transition(run.status, "succeeded")
        run.status = "succeeded"
        run.output = output

    def fail_run(self, run_id: int, error: dict[str, Any]) -> None:
        run = self.runs[run_id]
        if run.status == "pending":
            assert_run_transition(run.status, "running")
            run.status = "running"
        assert_run_transition(run.status, "failed")
        run.status = "failed"
        run.error = error

    def timeout_run(self, run_id: int, error: dict[str, Any]) -> None:
        run = self.runs[run_id]
        if run.status == "pending":
            assert_run_transition(run.status, "running")
            run.status = "running"
        assert_run_transition(run.status, "timeout")
        run.status = "timeout"
        run.error = error

    def mark_run_running(self, run_id: int) -> None:
        run = self.runs[run_id]
        if run.status == "running":
            return
        assert_run_transition(run.status, "running")
        run.status = "running"

    def cancel_run(self, run_id: int) -> None:
        run = self.runs[run_id]
        assert_run_transition(run.status, "cancelled")
        run.status = "cancelled"

    def delete_run(self, run_id: int) -> None:
        self.runs.pop(run_id, None)

    def complete_attempt(self, attempt_id: int) -> None:
        attempt = self.attempts[attempt_id]
        assert_run_attempt_transition(attempt.status, "succeeded")
        attempt.status = "succeeded"
        attempt.finished_at = datetime.now(UTC)

    def fail_attempt(self, attempt_id: int, error: dict[str, Any]) -> None:
        attempt = self.attempts[attempt_id]
        assert_run_attempt_transition(attempt.status, "failed")
        attempt.status = "failed"
        attempt.error = error
        attempt.finished_at = datetime.now(UTC)

    def timeout_attempt(self, attempt_id: int, error: dict[str, Any]) -> None:
        attempt = self.attempts[attempt_id]
        assert_run_attempt_transition(attempt.status, "timeout")
        attempt.status = "timeout"
        attempt.error = error
        attempt.finished_at = datetime.now(UTC)


class RunManager:
    def __init__(
        self,
        *,
        run_store: RuntimeRunStore,
        task_backend: TaskBackend,
        deployment_gate: DeploymentRunGate | None = None,
    ) -> None:
        self.run_store = run_store
        self.task_backend = task_backend
        self.deployment_gate = deployment_gate

    async def create_run_task(
        self,
        *,
        tenant_id: int,
        project_id: int,
        agent_id: int,
        agent_version_id: int,
        deployment_id: int | None,
        input_data: dict[str, Any],
        override_config: dict[str, Any] | None = None,
        queue: str = "default",
        thread_id: str | None = None,
        run_id: int | None = None,
        task_id: int | None = None,
    ) -> tuple[RuntimeRun, int]:
        if deployment_id is not None and self.deployment_gate is not None:
            self.deployment_gate.assert_accepts_new_run(
                deployment_id,
                tenant_id=tenant_id,
                project_id=project_id,
                agent_id=agent_id,
                agent_version_id=agent_version_id,
            )
        run = await self.run_store.create_run(
            tenant_id=tenant_id,
            project_id=project_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            deployment_id=deployment_id,
            input_data=input_data,
            override_config=override_config,
            thread_id=thread_id,
            run_id=run_id,
        )
        try:
            task_id = await self.task_backend.enqueue(
                {
                    "task_id": task_id,
                    "run_id": run.run_id,
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "agent_id": agent_id,
                    "agent_version_id": agent_version_id,
                    "deployment_id": deployment_id,
                    "input_data": input_data,
                    "override_config": dict(override_config or {}),
                    "queue": queue,
                    "thread_id": thread_id,
                }
            )
        except Exception:
            self.run_store.delete_run(run.run_id)
            raise
        return run, task_id
