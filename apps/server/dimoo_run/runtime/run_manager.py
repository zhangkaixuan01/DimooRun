from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from dimoo_run.runtime.state_machine import (
    assert_run_attempt_transition,
    assert_run_transition,
)
from dimoo_run.scheduler.backend import TaskBackend


@dataclass
class RuntimeRun:
    run_id: str
    tenant_id: str
    project_id: str
    agent_id: str
    agent_version_id: str
    deployment_id: str | None
    input_data: dict[str, Any]
    override_config: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    thread_id: str | None = None
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RuntimeAttempt:
    attempt_id: str
    run_id: str
    task_id: str
    worker_id: str
    attempt_no: int
    status: str = "running"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error: dict[str, Any] | None = None


class RuntimeRunStore(Protocol):
    runs: dict[str, RuntimeRun]
    attempts: dict[str, RuntimeAttempt]

    async def create_run(
        self,
        *,
        tenant_id: str,
        project_id: str,
        agent_id: str,
        agent_version_id: str,
        deployment_id: str | None,
        input_data: dict[str, Any],
        override_config: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> RuntimeRun: ...

    async def create_attempt(
        self,
        *,
        run_id: str,
        task_id: str,
        worker_id: str,
    ) -> RuntimeAttempt: ...

    def complete_run(self, run_id: str, output: dict[str, Any]) -> None: ...

    def fail_run(self, run_id: str, error: dict[str, Any]) -> None: ...

    def complete_attempt(self, attempt_id: str) -> None: ...

    def fail_attempt(self, attempt_id: str, error: dict[str, Any]) -> None: ...


class DeploymentRunGate(Protocol):
    def assert_accepts_new_run(
        self,
        deployment_id: str,
        *,
        tenant_id: str | None = None,
        project_id: str | None = None,
        agent_id: str | None = None,
        agent_version_id: str | None = None,
    ) -> None: ...


class InMemoryRunStore:
    def __init__(self) -> None:
        self.runs: dict[str, RuntimeRun] = {}
        self.attempts: dict[str, RuntimeAttempt] = {}

    async def create_run(
        self,
        *,
        tenant_id: str,
        project_id: str,
        agent_id: str,
        agent_version_id: str,
        deployment_id: str | None,
        input_data: dict[str, Any],
        override_config: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> RuntimeRun:
        run = RuntimeRun(
            run_id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            deployment_id=deployment_id,
            input_data=input_data,
            override_config=dict(override_config or {}),
            thread_id=thread_id,
        )
        self.runs[run.run_id] = run
        return run

    async def create_attempt(
        self,
        *,
        run_id: str,
        task_id: str,
        worker_id: str,
    ) -> RuntimeAttempt:
        attempt_no = (
            len([attempt for attempt in self.attempts.values() if attempt.run_id == run_id]) + 1
        )
        attempt = RuntimeAttempt(
            attempt_id=str(uuid4()),
            run_id=run_id,
            task_id=task_id,
            worker_id=worker_id,
            attempt_no=attempt_no,
        )
        self.attempts[attempt.attempt_id] = attempt
        if self.runs[run_id].status != "running":
            assert_run_transition(self.runs[run_id].status, "running")
            self.runs[run_id].status = "running"
        return attempt

    def complete_run(self, run_id: str, output: dict[str, Any]) -> None:
        run = self.runs[run_id]
        assert_run_transition(run.status, "succeeded")
        run.status = "succeeded"
        run.output = output

    def fail_run(self, run_id: str, error: dict[str, Any]) -> None:
        run = self.runs[run_id]
        assert_run_transition(run.status, "failed")
        run.status = "failed"
        run.error = error

    def complete_attempt(self, attempt_id: str) -> None:
        attempt = self.attempts[attempt_id]
        assert_run_attempt_transition(attempt.status, "succeeded")
        attempt.status = "succeeded"
        attempt.finished_at = datetime.now(UTC)

    def fail_attempt(self, attempt_id: str, error: dict[str, Any]) -> None:
        attempt = self.attempts[attempt_id]
        assert_run_attempt_transition(attempt.status, "failed")
        attempt.status = "failed"
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
        tenant_id: str,
        project_id: str,
        agent_id: str,
        agent_version_id: str,
        deployment_id: str | None,
        input_data: dict[str, Any],
        override_config: dict[str, Any] | None = None,
        queue: str = "default",
    ) -> tuple[RuntimeRun, str]:
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
        )
        task_id = await self.task_backend.enqueue(
            {
                "run_id": run.run_id,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "agent_id": agent_id,
                "agent_version_id": agent_version_id,
                "deployment_id": deployment_id,
                "input_data": input_data,
                "override_config": dict(override_config or {}),
                "queue": queue,
            }
        )
        return run, task_id
