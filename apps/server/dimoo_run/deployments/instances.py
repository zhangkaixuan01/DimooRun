from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from dimoo_run.domain.enums import AgentInstanceStatus


def build_cache_key(
    *,
    deployment_id: str,
    agent_version_id: str,
    execution_profile_id: str | None,
) -> str:
    return f"{deployment_id}:{agent_version_id}:{execution_profile_id or 'default'}"


@dataclass
class AgentInstanceRecord:
    id: str
    tenant_id: str
    project_id: str
    deployment_id: str
    agent_id: str
    agent_version_id: str
    worker_id: str
    execution_profile_id: str | None
    cache_key: str
    status: str = AgentInstanceStatus.loading.value
    loaded_at: datetime | None = None
    last_used_at: datetime | None = None
    heartbeat_at: datetime | None = None
    running_runs: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_ready(self, *, now: datetime) -> None:
        self.status = AgentInstanceStatus.ready.value
        self.loaded_at = self.loaded_at or now
        self.last_used_at = now
        self.heartbeat_at = now
        self.error = None

    def mark_failed(self, error: str, *, now: datetime) -> None:
        self.status = AgentInstanceStatus.failed.value
        self.error = error
        self.heartbeat_at = now

    def mark_evicted(self, reason: str) -> None:
        self.status = AgentInstanceStatus.evicted.value
        self.running_runs = 0
        self.metadata["evict_reason"] = reason


class AgentInstanceRegistry:
    def __init__(self, *, now: Any | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))
        self.instances: dict[str, AgentInstanceRecord] = {}

    def register_loading(
        self,
        *,
        tenant_id: str,
        project_id: str,
        deployment_id: str,
        agent_id: str,
        agent_version_id: str,
        worker_id: str,
        execution_profile_id: str | None,
    ) -> AgentInstanceRecord:
        instance = AgentInstanceRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            deployment_id=deployment_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            worker_id=worker_id,
            execution_profile_id=execution_profile_id,
            cache_key=build_cache_key(
                deployment_id=deployment_id,
                agent_version_id=agent_version_id,
                execution_profile_id=execution_profile_id,
            ),
            heartbeat_at=self._now(),
        )
        self.instances[instance.id] = instance
        return instance

    def get_ready(
        self,
        *,
        deployment_id: str,
        agent_version_id: str,
        execution_profile_id: str | None,
    ) -> AgentInstanceRecord | None:
        cache_key = build_cache_key(
            deployment_id=deployment_id,
            agent_version_id=agent_version_id,
            execution_profile_id=execution_profile_id,
        )
        for instance in self.instances.values():
            if instance.cache_key == cache_key and instance.status in {
                AgentInstanceStatus.ready.value,
                AgentInstanceStatus.idle.value,
                AgentInstanceStatus.busy.value,
            }:
                instance.last_used_at = self._now()
                return instance
        return None

    def mark_ready(self, instance_id: str) -> AgentInstanceRecord:
        instance = self.instances[instance_id]
        instance.mark_ready(now=self._now())
        return instance

    def mark_failed(self, instance_id: str, error: str) -> AgentInstanceRecord:
        instance = self.instances[instance_id]
        instance.mark_failed(error, now=self._now())
        return instance

    def list_by_deployment(self, deployment_id: str) -> list[AgentInstanceRecord]:
        return [
            instance
            for instance in self.instances.values()
            if instance.deployment_id == deployment_id
        ]

    def evict_deployment(self, deployment_id: str, *, reason: str) -> list[AgentInstanceRecord]:
        evicted = self.list_by_deployment(deployment_id)
        for instance in evicted:
            instance.mark_evicted(reason)
        return evicted

    def evict_idle(self, *, max_idle: timedelta) -> list[AgentInstanceRecord]:
        threshold = self._now() - max_idle
        evicted: list[AgentInstanceRecord] = []
        for instance in self.instances.values():
            if (
                instance.status in {AgentInstanceStatus.ready.value, AgentInstanceStatus.idle.value}
                and instance.running_runs == 0
                and instance.last_used_at is not None
                and instance.last_used_at < threshold
            ):
                instance.mark_evicted("idle_timeout")
                evicted.append(instance)
        return evicted
