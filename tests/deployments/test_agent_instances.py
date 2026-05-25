from datetime import UTC, datetime, timedelta

from dimoo_run.deployments.instances import AgentInstanceRegistry
from dimoo_run.deployments.status import aggregate_runtime_status
from dimoo_run.domain.enums import DeploymentDesiredStatus, DeploymentRuntimeStatus


def test_agent_instance_cache_key_and_reuse() -> None:
    registry = AgentInstanceRegistry(now=lambda: datetime(2026, 1, 1, tzinfo=UTC))

    first = registry.register_loading(
        tenant_id="tenant_1",
        project_id="project_1",
        deployment_id="deployment_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        worker_id="worker_1",
        execution_profile_id="profile_1",
    )
    registry.mark_ready(first.id)
    reused = registry.get_ready(
        deployment_id="deployment_1",
        agent_version_id="version_1",
        execution_profile_id="profile_1",
    )

    assert first.cache_key == "deployment_1:version_1:profile_1"
    assert reused == first


def test_agent_instance_status_changes_use_registry_clock() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    registry = AgentInstanceRegistry(now=lambda: now)
    instance = registry.register_loading(
        tenant_id="tenant_1",
        project_id="project_1",
        deployment_id="deployment_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        worker_id="worker_1",
        execution_profile_id="profile_1",
    )

    registry.mark_ready(instance.id)
    registry.mark_failed(instance.id, "load failed")

    assert instance.loaded_at == now
    assert instance.last_used_at == now
    assert instance.heartbeat_at == now


def test_restart_and_stop_evict_cached_instances() -> None:
    registry = AgentInstanceRegistry()
    instance = registry.register_loading(
        tenant_id="tenant_1",
        project_id="project_1",
        deployment_id="deployment_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        worker_id="worker_1",
        execution_profile_id=None,
    )
    registry.mark_ready(instance.id)

    evicted = registry.evict_deployment("deployment_1", reason="restart")

    assert evicted == [instance]
    assert instance.status == "evicted"
    assert instance.metadata["evict_reason"] == "restart"


def test_idle_instances_can_be_evicted_by_policy() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    registry = AgentInstanceRegistry(now=lambda: now)
    instance = registry.register_loading(
        tenant_id="tenant_1",
        project_id="project_1",
        deployment_id="deployment_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        worker_id="worker_1",
        execution_profile_id=None,
    )
    registry.mark_ready(instance.id)
    instance.last_used_at = now - timedelta(minutes=30)

    evicted = registry.evict_idle(max_idle=timedelta(minutes=10))

    assert evicted == [instance]
    assert instance.status == "evicted"


def test_runtime_status_aggregates_instance_health() -> None:
    registry = AgentInstanceRegistry()
    ready = registry.register_loading(
        tenant_id="tenant_1",
        project_id="project_1",
        deployment_id="deployment_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        worker_id="worker_1",
        execution_profile_id=None,
    )
    failed = registry.register_loading(
        tenant_id="tenant_1",
        project_id="project_1",
        deployment_id="deployment_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        worker_id="worker_2",
        execution_profile_id=None,
    )
    registry.mark_ready(ready.id)
    registry.mark_failed(failed.id, "load failed")

    summary = aggregate_runtime_status(
        desired_status=DeploymentDesiredStatus.active,
        instances=registry.list_by_deployment("deployment_1"),
        running_runs=2,
        queue_backlog=5,
    )

    assert summary.runtime_status == DeploymentRuntimeStatus.degraded
    assert summary.running_runs == 2
    assert summary.queue_backlog == 5
    assert summary.worker_distribution == {"worker_1": 1, "worker_2": 1}
    assert summary.last_runtime_error == "load failed"


def test_stopped_deployment_without_active_instances_reports_stopped() -> None:
    summary = aggregate_runtime_status(
        desired_status=DeploymentDesiredStatus.stopped,
        instances=[],
        running_runs=0,
        queue_backlog=0,
    )

    assert summary.runtime_status == DeploymentRuntimeStatus.stopped
