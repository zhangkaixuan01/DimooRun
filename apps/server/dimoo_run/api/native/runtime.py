import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from dimoo_run.core.events import AgentEvent
from dimoo_run.domain.enums import RunStatus, TaskStatus
from dimoo_run.runtime.idempotency import IdempotencyStore
from dimoo_run.streaming.replay_buffer import ReplayBuffer


@dataclass
class NativeAgent:
    id: str
    tenant_id: str
    project_id: str
    name: str
    description: str | None = None
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class NativeAgentVersion:
    id: str
    agent_id: str
    version: str
    package_uri: str
    framework: str
    adapter: str
    entrypoint: str
    capabilities: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    status: str = "ready"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class NativeRun:
    id: str
    tenant_id: str
    project_id: str
    agent_id: str
    agent_version_id: str
    deployment_id: str | None
    status: RunStatus
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    thread_id: str | None = None
    idempotency_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class NativeTask:
    id: str
    run_id: str
    tenant_id: str
    project_id: str
    status: TaskStatus
    queue: str = "default"
    priority: int = 0
    attempt: int = 0
    max_attempts: int = 3
    idempotency_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class NativeRuntimeStore:
    def __init__(self) -> None:
        self.agents: dict[str, NativeAgent] = {}
        self.versions: dict[str, NativeAgentVersion] = {}
        self.runs: dict[str, NativeRun] = {}
        self.tasks: dict[str, NativeTask] = {}
        self.idempotency = IdempotencyStore()
        self.replay_buffer = ReplayBuffer()

    def create_agent(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        description: str | None,
    ) -> NativeAgent:
        agent = NativeAgent(
            id=f"agent_{uuid4().hex[:12]}",
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            description=description,
        )
        self.agents[agent.id] = agent
        return agent

    def list_agents(self, *, tenant_id: str, project_id: str) -> list[NativeAgent]:
        return [
            agent
            for agent in self.agents.values()
            if agent.tenant_id == tenant_id and agent.project_id == project_id
        ]

    def get_agent(self, agent_id: str, *, tenant_id: str, project_id: str) -> NativeAgent | None:
        agent = self.agents.get(agent_id)
        if agent is None or agent.tenant_id != tenant_id or agent.project_id != project_id:
            return None
        return agent

    def create_version(
        self,
        *,
        agent: NativeAgent,
        version: str,
        package_uri: str,
        framework: str,
        adapter: str,
        entrypoint: str,
        capabilities: dict[str, Any],
        manifest: dict[str, Any],
    ) -> NativeAgentVersion:
        agent_version = NativeAgentVersion(
            id=f"agent_version_{uuid4().hex[:12]}",
            agent_id=agent.id,
            version=version,
            package_uri=package_uri,
            framework=framework,
            adapter=adapter,
            entrypoint=entrypoint,
            capabilities=capabilities,
            manifest=manifest,
        )
        self.versions[agent_version.id] = agent_version
        return agent_version

    def list_versions(self, agent_id: str) -> list[NativeAgentVersion]:
        return [version for version in self.versions.values() if version.agent_id == agent_id]

    def get_version(self, agent_id: str, version: str) -> NativeAgentVersion | None:
        for agent_version in self.versions.values():
            if agent_version.agent_id == agent_id and agent_version.version == version:
                return agent_version
        return None

    def latest_version(self, agent_id: str) -> NativeAgentVersion | None:
        versions = self.list_versions(agent_id)
        if not versions:
            return None
        return sorted(versions, key=lambda item: item.created_at)[-1]

    def create_task_run(
        self,
        *,
        tenant_id: str,
        project_id: str,
        agent: NativeAgent,
        agent_version: NativeAgentVersion,
        input_data: dict[str, Any],
        thread_id: str | None,
        idempotency_key: str | None,
        endpoint: str,
        request_body: dict[str, Any],
    ) -> tuple[NativeRun, NativeTask, bool]:
        replayed = False
        if idempotency_key:
            request_hash = _stable_hash(request_body)
            reservation = self.idempotency.reserve(
                tenant_id=tenant_id,
                project_id=project_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if reservation.is_replay and reservation.response:
                run = self.runs[reservation.response["run_id"]]
                task = self.tasks[reservation.response["task_id"]]
                return run, task, True
            replayed = reservation.is_replay

        run = NativeRun(
            id=f"run_{uuid4().hex[:12]}",
            tenant_id=tenant_id,
            project_id=project_id,
            agent_id=agent.id,
            agent_version_id=agent_version.id,
            deployment_id=None,
            status=RunStatus.pending,
            input=input_data,
            thread_id=thread_id,
            idempotency_key=idempotency_key,
        )
        task = NativeTask(
            id=f"task_{uuid4().hex[:12]}",
            run_id=run.id,
            tenant_id=tenant_id,
            project_id=project_id,
            status=TaskStatus.queued,
            idempotency_key=idempotency_key,
        )
        self.runs[run.id] = run
        self.tasks[task.id] = task
        self.replay_buffer.append(
            run.id,
            None,
            AgentEvent(type="run.created", payload={"task_id": task.id}),
        )
        self.replay_buffer.append(
            run.id,
            None,
            AgentEvent(type="task.queued", payload={"task_id": task.id}),
        )
        if idempotency_key:
            self.idempotency.complete(
                reservation.record_id,
                {"run_id": run.id, "task_id": task.id},
            )
        return run, task, replayed

    def get_run(self, run_id: str, *, tenant_id: str, project_id: str) -> NativeRun | None:
        run = self.runs.get(run_id)
        if run is None or run.tenant_id != tenant_id or run.project_id != project_id:
            return None
        return run

    def get_task(self, task_id: str, *, tenant_id: str, project_id: str) -> NativeTask | None:
        task = self.tasks.get(task_id)
        if task is None or task.tenant_id != tenant_id or task.project_id != project_id:
            return None
        return task

    def list_run_events(self, run_id: str) -> list[AgentEvent]:
        return self.replay_buffer.replay(run_id)

    def cancel_run(self, run: NativeRun) -> None:
        run.status = RunStatus.cancelled
        run.updated_at = datetime.now(UTC)
        cancellable_statuses = {
            TaskStatus.queued,
            TaskStatus.leased,
            TaskStatus.running,
        }
        for task in self.tasks.values():
            if task.run_id == run.id and task.status in cancellable_statuses:
                task.status = TaskStatus.cancelled
                task.updated_at = run.updated_at
        self.replay_buffer.append(run.id, None, AgentEvent(type="run.cancelled", payload={}))

    def cancel_task(self, task: NativeTask) -> None:
        task.status = TaskStatus.cancelled
        task.updated_at = datetime.now(UTC)
        run = self.runs[task.run_id]
        run.status = RunStatus.cancelled
        run.updated_at = task.updated_at
        self.replay_buffer.append(
            run.id,
            None,
            AgentEvent(type="task.cancelled", payload={"task_id": task.id}),
        )


_default_native_runtime = NativeRuntimeStore()


def default_native_runtime() -> NativeRuntimeStore:
    return _default_native_runtime


def reset_native_runtime() -> None:
    global _default_native_runtime
    _default_native_runtime = NativeRuntimeStore()


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
