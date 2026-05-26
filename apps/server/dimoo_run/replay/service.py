from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ReplaySourceRun:
    run_id: str
    tenant_id: str
    project_id: str
    agent_id: str
    agent_version_id: str
    deployment_id: str | None
    input_ref: str | None
    input_data: dict[str, Any]
    status: str


@dataclass(frozen=True)
class ReplayJob:
    id: str
    tenant_id: str
    project_id: str
    source_run_id: str
    source_agent_version_id: str
    candidate_agent_version_id: str
    replay_run_id: str | None
    replay_task_id: str | None
    requested_by: str
    status: str
    override_config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


CreateRunTask = Callable[..., Awaitable[tuple[Any, str]]]


class InMemoryReplayService:
    def __init__(self, *, create_run_task: CreateRunTask | None) -> None:
        self.create_run_task = create_run_task
        self.jobs: dict[str, ReplayJob] = {}

    async def create_replay_job(
        self,
        *,
        source_run: ReplaySourceRun,
        candidate_agent_version_id: str,
        requested_by: str,
        override_config: dict[str, Any] | None = None,
    ) -> ReplayJob:
        if source_run.status not in {"failed", "succeeded", "cancelled", "timeout"}:
            raise PermissionError("source_run_not_terminal")
        effective_override_config = dict(override_config or {})
        replay_run_id: str | None = None
        replay_task_id: str | None = None
        if self.create_run_task is not None:
            run, replay_task_id = await self.create_run_task(
                tenant_id=source_run.tenant_id,
                project_id=source_run.project_id,
                agent_id=source_run.agent_id,
                agent_version_id=candidate_agent_version_id,
                deployment_id=source_run.deployment_id,
                input_data=dict(source_run.input_data),
                override_config=effective_override_config,
                queue="replay",
            )
            replay_run_id = run["run_id"] if isinstance(run, dict) else run.run_id
        job = ReplayJob(
            id=str(uuid4()),
            tenant_id=source_run.tenant_id,
            project_id=source_run.project_id,
            source_run_id=source_run.run_id,
            source_agent_version_id=source_run.agent_version_id,
            candidate_agent_version_id=candidate_agent_version_id,
            replay_run_id=replay_run_id,
            replay_task_id=replay_task_id,
            requested_by=requested_by,
            status="created",
            override_config=effective_override_config,
        )
        self.jobs[job.id] = job
        return job
