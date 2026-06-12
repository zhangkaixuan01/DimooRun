from collections.abc import Mapping
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.adapters.base.contract import AgentAdapter
from dimoo_run.core.events import AgentEvent
from dimoo_run.domain.models import AgentVersion
from dimoo_run.packages.registry import AgentRuntimeRegistry
from dimoo_run.persistence.repositories import EventRepository
from dimoo_run.runtime.sqlalchemy_run_store import SQLAlchemyRunStore
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from dimoo_run.streaming.replay_buffer import ReplayBuffer
from dimoo_run.worker.executor import AgentRuntimeSpec, WorkerExecutionResult, WorkerExecutor


class SQLAlchemyReplayBuffer(ReplayBuffer):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session
        self.run_store = SQLAlchemyRunStore(session)

    def append(
        self,
        run_id: int,
        attempt_id: int | None,
        event: AgentEvent,
    ) -> AgentEvent:
        appended = super().append(run_id, attempt_id, event)
        run = self.run_store.get_run(run_id)
        EventRepository(self.session).append(
            event_id=appended.event_id or f"{run_id}:event",
            run_id=run_id,
            attempt_id=attempt_id,
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            type=appended.type,
            payload=appended.payload,
            framework=appended.framework,
            visibility_level=appended.visibility_level,
        )
        self.session.flush()
        return appended


class RuntimeSpecRunRecord(Protocol):
    agent_version_id: int
    deployment_id: int | None
    tenant_id: int
    project_id: int | None


class DurableWorkerExecutorFactory:
    def __init__(
        self,
        *,
        session: Session,
        worker_id: str,
        adapters: Mapping[str, AgentAdapter],
    ) -> None:
        self.session = session
        self.worker_id = worker_id
        self.adapters = dict(adapters)
        self.registry = AgentRuntimeRegistry(session=session)

    def build(self) -> WorkerExecutor:
        versions = self.session.scalars(
            select(AgentVersion).where(AgentVersion.is_deleted.is_(False))
        )
        specs = {
            version.id: AgentRuntimeSpec(
                adapter=version.adapter,
                package_uri=version.package_uri,
                manifest=version.manifest_json or {},
                runtime_config={},
            )
            for version in versions
        }
        return WorkerExecutor(
            worker_id=self.worker_id,
            task_backend=SQLAlchemyTaskBackend(self.session),
            run_store=SQLAlchemyRunStore(self.session),
            replay_buffer=SQLAlchemyReplayBuffer(self.session),
            adapters=self.adapters,
            agent_specs=specs,
            runtime_spec_resolver=self._resolve_runtime_spec,
        )

    def _resolve_runtime_spec(self, run: RuntimeSpecRunRecord) -> AgentRuntimeSpec:
        return self.registry.resolve_for_run(
            agent_version_id=run.agent_version_id,
            deployment_id=run.deployment_id,
            tenant_id=run.tenant_id,
            project_id=run.project_id,
        )


async def execute_durable_once(
    *,
    session: Session,
    worker_id: str,
    queue: str = "default",
    adapters: Mapping[str, AgentAdapter],
    lease_seconds: int = 30,
) -> WorkerExecutionResult | None:
    executor = DurableWorkerExecutorFactory(
        session=session,
        worker_id=worker_id,
        adapters=adapters,
    ).build()
    return await executor.execute_once(queue=queue, lease_seconds=lease_seconds)
