from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ReplaySourceRun:
    run_id: int
    tenant_id: int
    project_id: int
    agent_id: int
    agent_version_id: int
    deployment_id: int | None
    input_ref: str | None
    input_data: dict[str, Any]
    status: str


@dataclass(frozen=True)
class ReplayJob:
    id: int
    tenant_id: int
    project_id: int
    source_run_id: int
    source_agent_version_id: int
    candidate_agent_version_id: int
    replay_run_id: int | None
    replay_task_id: int | None
    requested_by: str
    status: str
    override_config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


CreateRunTask = Callable[..., Awaitable[tuple[Any, int]]]


class InMemoryReplayService:
    def __init__(self, *, create_run_task: CreateRunTask | None) -> None:
        self.create_run_task = create_run_task
        self.jobs: dict[int, ReplayJob] = {}
        self._next_job_id = 1

    async def create_replay_job(
        self,
        *,
        source_run: ReplaySourceRun,
        candidate_agent_version_id: int,
        requested_by: str,
        override_config: dict[str, Any] | None = None,
    ) -> ReplayJob:
        if source_run.status not in {"failed", "succeeded", "cancelled", "timeout"}:
            raise PermissionError("source_run_not_terminal")
        effective_override_config = dict(override_config or {})
        replay_run_id: int | None = None
        replay_task_id: int | None = None
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
            id=self._next_job_id,
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
        self._next_job_id += 1
        self.jobs[job.id] = job
        return job
