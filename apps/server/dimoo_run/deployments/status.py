from dataclasses import dataclass
from datetime import datetime

from dimoo_run.deployments.instances import AgentInstanceRecord
from dimoo_run.domain.enums import (
    AgentInstanceStatus,
    DeploymentDesiredStatus,
    DeploymentRuntimeStatus,
)


@dataclass(frozen=True)
class RuntimeStatusSummary:
    runtime_status: DeploymentRuntimeStatus
    running_runs: int
    queue_backlog: int
    worker_distribution: dict[str, int]
    last_runtime_error: str | None
    last_heartbeat_at: datetime | None
    loaded_at: datetime | None


def aggregate_runtime_status(
    *,
    desired_status: DeploymentDesiredStatus,
    instances: list[AgentInstanceRecord],
    running_runs: int,
    queue_backlog: int,
) -> RuntimeStatusSummary:
    active_instances = [
        instance
        for instance in instances
        if instance.status != AgentInstanceStatus.evicted.value
    ]
    available_statuses = {
        AgentInstanceStatus.ready.value,
        AgentInstanceStatus.idle.value,
        AgentInstanceStatus.busy.value,
    }
    available = [
        instance for instance in active_instances if instance.status in available_statuses
    ]
    loading = [
        instance
        for instance in active_instances
        if instance.status == AgentInstanceStatus.loading.value
    ]
    failed = [
        instance
        for instance in active_instances
        if instance.status == AgentInstanceStatus.failed.value
    ]
    draining = [
        instance
        for instance in active_instances
        if instance.status == AgentInstanceStatus.draining.value
    ]

    if desired_status == DeploymentDesiredStatus.stopped and not active_instances:
        runtime_status = DeploymentRuntimeStatus.stopped
    elif desired_status == DeploymentDesiredStatus.draining or (
        active_instances and len(draining) == len(active_instances)
    ):
        runtime_status = DeploymentRuntimeStatus.draining
    elif not active_instances:
        runtime_status = DeploymentRuntimeStatus.not_loaded
    elif available and failed:
        runtime_status = DeploymentRuntimeStatus.degraded
    elif available:
        runtime_status = DeploymentRuntimeStatus.ready
    elif loading:
        runtime_status = DeploymentRuntimeStatus.warming_up
    elif failed:
        runtime_status = DeploymentRuntimeStatus.failed
    else:
        runtime_status = DeploymentRuntimeStatus.not_loaded

    worker_distribution: dict[str, int] = {}
    for instance in active_instances:
        worker_distribution[instance.worker_id] = worker_distribution.get(instance.worker_id, 0) + 1

    return RuntimeStatusSummary(
        runtime_status=runtime_status,
        running_runs=running_runs,
        queue_backlog=queue_backlog,
        worker_distribution=worker_distribution,
        last_runtime_error=next(
            (instance.error for instance in reversed(active_instances) if instance.error),
            None,
        ),
        last_heartbeat_at=max(
            (instance.heartbeat_at for instance in active_instances if instance.heartbeat_at),
            default=None,
        ),
        loaded_at=max(
            (instance.loaded_at for instance in active_instances if instance.loaded_at),
            default=None,
        ),
    )
