import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.core.events import AgentEvent
from dimoo_run.domain.enums import RunStatus, TaskStatus
from dimoo_run.domain.models import Agent, AgentVersion, Run, Task
from dimoo_run.persistence.repositories import (
    AgentRepository,
    AgentVersionRepository,
    AuditLogRepository,
    EventRepository,
    RunRepository,
    TaskRepository,
)
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

    def update_agent(
        self,
        agent: NativeAgent,
        *,
        name: str,
        description: str | None,
    ) -> NativeAgent:
        agent.name = name
        agent.description = description
        return agent

    def archive_agent(self, agent: NativeAgent) -> NativeAgent:
        agent.status = "archived"
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

    def get_version_by_id(
        self,
        agent_id: str,
        agent_version_id: str,
    ) -> NativeAgentVersion | None:
        agent_version = self.versions.get(agent_version_id)
        if agent_version is None or agent_version.agent_id != agent_id:
            return None
        return agent_version

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

    def cancel_run(self, run: NativeRun) -> NativeRun:
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
        return run

    def cancel_task(self, task: NativeTask) -> NativeTask:
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
        return task


class SQLAlchemyNativeRuntimeStore:
    def __init__(self, session: Session, idempotency_store: IdempotencyStore | None = None) -> None:
        self.session = session
        self.idempotency = idempotency_store or IdempotencyStore()

    @property
    def agents(self) -> dict[str, NativeAgent]:
        return {
            agent.id: _agent_from_model(agent)
            for agent in self.session.scalars(select(Agent).where(Agent.is_deleted.is_(False)))
        }

    def create_agent(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        description: str | None,
    ) -> NativeAgent:
        agent = AgentRepository(self.session).create(
            Agent(
                id=f"agent_{uuid4().hex[:12]}",
                tenant_id=tenant_id,
                project_id=project_id,
                name=name,
                description=description,
            )
        )
        self.session.flush()
        return _agent_from_model(agent)

    def list_agents(self, *, tenant_id: str, project_id: str) -> list[NativeAgent]:
        return [
            _agent_from_model(agent)
            for agent in AgentRepository(self.session).list_by_project(tenant_id, project_id)
        ]

    def get_agent(self, agent_id: str, *, tenant_id: str, project_id: str) -> NativeAgent | None:
        agent = AgentRepository(self.session).get_by_id(agent_id)
        if agent is None or agent.tenant_id != tenant_id or agent.project_id != project_id:
            return None
        return _agent_from_model(agent)

    def update_agent(
        self,
        agent: NativeAgent,
        *,
        name: str,
        description: str | None,
    ) -> NativeAgent:
        model = AgentRepository(self.session).get_by_id(agent.id)
        if model is None:
            raise KeyError(agent.id)
        model.name = name
        model.description = description
        self.session.flush()
        return _agent_from_model(model)

    def archive_agent(self, agent: NativeAgent) -> NativeAgent:
        model = AgentRepository(self.session).soft_delete_or_archive(agent.id)
        self.session.flush()
        return _agent_from_model(model)

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
        agent_version = AgentVersionRepository(self.session).create(
            AgentVersion(
                id=f"agent_version_{uuid4().hex[:12]}",
                agent_id=agent.id,
                version=version,
                package_uri=package_uri,
                framework=framework,
                adapter=adapter,
                entrypoint=entrypoint,
                capabilities_json=capabilities,
                manifest_json=manifest,
                status="ready",
            )
        )
        self.session.flush()
        return _version_from_model(agent_version)

    def list_versions(self, agent_id: str) -> list[NativeAgentVersion]:
        return [
            _version_from_model(version)
            for version in AgentVersionRepository(self.session).list_by_agent(agent_id)
        ]

    def get_version(self, agent_id: str, version: str) -> NativeAgentVersion | None:
        agent_version = AgentVersionRepository(self.session).get_by_agent_version(
            agent_id,
            version,
        )
        return _version_from_model(agent_version) if agent_version is not None else None

    def get_version_by_id(
        self,
        agent_id: str,
        agent_version_id: str,
    ) -> NativeAgentVersion | None:
        agent_version = AgentVersionRepository(self.session).get_by_id(agent_version_id)
        if agent_version is None or agent_version.agent_id != agent_id:
            return None
        return _version_from_model(agent_version)

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
                run = self.get_run(
                    reservation.response["run_id"],
                    tenant_id=tenant_id,
                    project_id=project_id,
                )
                task = self.get_task(
                    reservation.response["task_id"],
                    tenant_id=tenant_id,
                    project_id=project_id,
                )
                if run is None or task is None:
                    raise KeyError("idempotency response references missing run/task")
                return run, task, True
            replayed = reservation.is_replay

        run_model = RunRepository(self.session).create(
            Run(
                id=f"run_{uuid4().hex[:12]}",
                tenant_id=tenant_id,
                project_id=project_id,
                agent_id=agent.id,
                agent_version_id=agent_version.id,
                thread_id=thread_id,
                idempotency_key=idempotency_key,
                input_ref=_encode_ref(input_data),
            )
        )
        task_model = TaskRepository(self.session).create(
            Task(
                id=f"task_{uuid4().hex[:12]}",
                run_id=run_model.id,
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
            )
        )
        events = EventRepository(self.session)
        events.append(
            event_id=f"event_{uuid4().hex[:12]}",
            run_id=run_model.id,
            tenant_id=tenant_id,
            project_id=project_id,
            type="run.created",
            payload={"task_id": task_model.id},
        )
        self.session.flush()
        events.append(
            event_id=f"event_{uuid4().hex[:12]}",
            run_id=run_model.id,
            tenant_id=tenant_id,
            project_id=project_id,
            type="task.queued",
            payload={"task_id": task_model.id},
        )
        AuditLogRepository(self.session).append(
            audit_id=f"audit_{uuid4().hex[:12]}",
            tenant_id=tenant_id,
            project_id=project_id,
            action="run.create",
            resource_type="run",
            resource_id=run_model.id,
            result="allow",
        )
        self.session.flush()
        if idempotency_key:
            self.idempotency.complete(
                reservation.record_id,
                {"run_id": run_model.id, "task_id": task_model.id},
            )
        return _run_from_model(run_model), _task_from_model(task_model), replayed

    def get_run(self, run_id: str, *, tenant_id: str, project_id: str) -> NativeRun | None:
        run = RunRepository(self.session).get_by_id(run_id)
        if run is None or run.tenant_id != tenant_id or run.project_id != project_id:
            return None
        return _run_from_model(run)

    def get_task(self, task_id: str, *, tenant_id: str, project_id: str) -> NativeTask | None:
        task = TaskRepository(self.session).get_by_id(task_id)
        if task is None or task.tenant_id != tenant_id or task.project_id != project_id:
            return None
        return _task_from_model(task)

    def list_run_events(self, run_id: str) -> list[AgentEvent]:
        return [
            AgentEvent(
                type=event.type,
                payload=event.payload_json or {},
                run_id=event.run_id,
                attempt_id=event.attempt_id,
                sequence=event.sequence,
                event_id=event.event_id,
                framework=event.framework,
                visibility_level=event.visibility_level,
            )
            for event in EventRepository(self.session).list_by_run(run_id)
        ]

    def cancel_run(self, run: NativeRun) -> NativeRun:
        run_model = RunRepository(self.session).transition(run.id, "cancelled")
        for task in TaskRepository(self.session).list_by_run(run.id):
            if task.status in {"queued", "leased", "running"}:
                TaskRepository(self.session).transition(task.id, "cancelled")
        EventRepository(self.session).append(
            event_id=f"event_{uuid4().hex[:12]}",
            run_id=run.id,
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            type="run.cancelled",
            payload={},
        )
        self.session.flush()
        return _run_from_model(run_model)

    def cancel_task(self, task: NativeTask) -> NativeTask:
        task_model = TaskRepository(self.session).transition(task.id, "cancelled")
        RunRepository(self.session).transition(task.run_id, "cancelled")
        EventRepository(self.session).append(
            event_id=f"event_{uuid4().hex[:12]}",
            run_id=task.run_id,
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            type="task.cancelled",
            payload={"task_id": task.id},
        )
        self.session.flush()
        return _task_from_model(task_model)


_default_native_runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore = NativeRuntimeStore()


def default_native_runtime() -> NativeRuntimeStore | SQLAlchemyNativeRuntimeStore:
    return _default_native_runtime


def set_default_native_runtime(runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore) -> None:
    global _default_native_runtime
    _default_native_runtime = runtime


def reset_native_runtime() -> None:
    global _default_native_runtime
    _default_native_runtime = NativeRuntimeStore()


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _agent_from_model(agent: Agent) -> NativeAgent:
    return NativeAgent(
        id=agent.id,
        tenant_id=agent.tenant_id,
        project_id=agent.project_id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        created_at=agent.created_at,
    )


def _version_from_model(version: AgentVersion) -> NativeAgentVersion:
    return NativeAgentVersion(
        id=version.id,
        agent_id=version.agent_id,
        version=version.version,
        package_uri=version.package_uri,
        framework=version.framework,
        adapter=version.adapter,
        entrypoint=version.entrypoint,
        capabilities=version.capabilities_json,
        manifest=version.manifest_json,
        status=version.status,
        created_at=version.created_at,
    )


def _run_from_model(run: Run) -> NativeRun:
    return NativeRun(
        id=run.id,
        tenant_id=run.tenant_id,
        project_id=run.project_id,
        agent_id=run.agent_id,
        agent_version_id=run.agent_version_id,
        deployment_id=run.deployment_id,
        status=RunStatus(run.status),
        input=_decode_ref(run.input_ref),
        output=_decode_ref(run.output_ref) if run.output_ref else None,
        error={"message": run.error} if run.error else None,
        thread_id=run.thread_id,
        idempotency_key=run.idempotency_key,
        created_at=run.created_at,
        updated_at=run.updated_at or run.created_at,
    )


def _task_from_model(task: Task) -> NativeTask:
    return NativeTask(
        id=task.id,
        run_id=task.run_id,
        tenant_id=task.tenant_id,
        project_id=task.project_id,
        status=TaskStatus(task.status),
        queue=task.queue,
        priority=task.priority,
        attempt=task.attempt,
        max_attempts=task.max_attempts,
        idempotency_key=task.idempotency_key,
        created_at=task.created_at,
        updated_at=task.updated_at or task.created_at,
    )


def _encode_ref(payload: dict[str, Any]) -> str:
    return "json:" + json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _decode_ref(value: str | None) -> dict[str, Any]:
    if not value or not value.startswith("json:"):
        return {}
    decoded = json.loads(value.removeprefix("json:"))
    return decoded if isinstance(decoded, dict) else {}
