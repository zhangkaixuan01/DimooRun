from collections.abc import Iterable

from dimoo_run.api.console.schemas import (
    ConsoleActionAvailability,
    ConsoleActionSummary,
    ConsoleDashboardSummary,
    ConsoleDeploymentHealth,
    ConsolePendingAction,
    ConsoleRecentFailure,
    ConsoleRuntimeOverview,
    ConsoleWorkerHealth,
)
from dimoo_run.api.native.runtime import NativeRun, NativeRuntimeStore, SQLAlchemyNativeRuntimeStore
from dimoo_run.deployments.service import DeploymentRecord, DeploymentRuntimeControlService
from dimoo_run.domain.enums import RunStatus, TaskStatus
from dimoo_run.security.api_keys import AuthenticatedActor


def dashboard_summary(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> ConsoleDashboardSummary:
    scoped_deployments = _scoped_deployments(
        deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    scoped_runs = _scoped_runs(
        runtime,
        tenant_id=tenant_id,
        project_id=project_id,
        deployment_ids={deployment.id for deployment in scoped_deployments},
    )
    scoped_tasks = [
        task
        for task in runtime.list_tasks(tenant_id=tenant_id, project_id=project_id)
        if any(run.id == task.run_id for run in scoped_runs)
    ]
    completed_runs = [
        run for run in scoped_runs if run.status in {RunStatus.succeeded, RunStatus.failed}
    ]
    succeeded_runs = [run for run in scoped_runs if run.status == RunStatus.succeeded]
    latencies = sorted(
        int((run.finished_at - run.started_at).total_seconds() * 1000)
        for run in scoped_runs
        if run.started_at is not None and run.finished_at is not None
    )
    deployment_health = deployment_health_summary(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    return ConsoleDashboardSummary(
        run_count_today=len(scoped_runs),
        success_rate=(len(succeeded_runs) / len(completed_runs)) if completed_runs else 0,
        p95_latency_ms=_percentile(latencies, 0.95),
        p99_latency_ms=_percentile(latencies, 0.99),
        queue_backlog=sum(item.queue_backlog for item in deployment_health),
        worker_ready=sum(1 for item in deployment_health if item.runtime_status == "ready"),
        worker_total=len(deployment_health),
        monthly_cost_usd=0,
        pending_approvals=0,
        running_runs=sum(1 for run in scoped_runs if run.status == RunStatus.running),
        active_incidents=0,
    )


def runtime_overview(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    actor: AuthenticatedActor,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> ConsoleRuntimeOverview:
    return ConsoleRuntimeOverview(
        summary=dashboard_summary(
            runtime=runtime,
            deployments=deployments,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        ),
        deployment_health=deployment_health_summary(
            runtime=runtime,
            deployments=deployments,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        ),
        worker_health=worker_health_summary(
            runtime=runtime,
            deployments=deployments,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        ),
        recent_failures=recent_failures(
            runtime=runtime,
            deployments=deployments,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        ),
        pending_actions=pending_actions(
            runtime=runtime,
            deployments=deployments,
            actor=actor,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        ),
    )


def deployment_health_summary(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> list[ConsoleDeploymentHealth]:
    runs = runtime.list_runs(tenant_id=tenant_id, project_id=project_id)
    tasks = runtime.list_tasks(tenant_id=tenant_id, project_id=project_id)
    health: list[ConsoleDeploymentHealth] = []
    for deployment in _scoped_deployments(
        deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    ):
        deployment_runs = [run for run in runs if run.deployment_id == deployment.id]
        deployment_run_ids = {run.id for run in deployment_runs}
        deployment_tasks = [task for task in tasks if task.run_id in deployment_run_ids]
        health.append(
            ConsoleDeploymentHealth(
                deployment_id=deployment.id,
                environment=deployment.environment,
                desired_status=deployment.desired_status.value,
                runtime_status=deployment.runtime_status.value,
                replicas=deployment.replicas,
                queue_backlog=sum(
                    1
                    for task in deployment_tasks
                    if task.status
                    in {TaskStatus.queued, TaskStatus.retrying, TaskStatus.dead_letter}
                ),
                running_runs=sum(1 for run in deployment_runs if run.status == RunStatus.running),
                last_runtime_error=deployment.last_runtime_error,
            )
        )
    return health


def worker_health_summary(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> list[ConsoleWorkerHealth]:
    return [
        ConsoleWorkerHealth(
            worker_id=f"deployment-{item.deployment_id}",
            deployment_id=item.deployment_id,
            environment=item.environment,
            status="ready" if item.runtime_status == "ready" else "degraded",
            queue_backlog=item.queue_backlog,
            running_runs=item.running_runs,
        )
        for item in deployment_health_summary(
            runtime=runtime,
            deployments=deployments,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    ]


def recent_failures(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> list[ConsoleRecentFailure]:
    deployment_ids = {
        deployment.id
        for deployment in _scoped_deployments(
            deployments,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    }
    failures = [
        run
        for run in _scoped_runs(
            runtime,
            tenant_id=tenant_id,
            project_id=project_id,
            deployment_ids=deployment_ids,
        )
        if run.status == RunStatus.failed
    ]
    return [
        ConsoleRecentFailure(
            run_id=run.id,
            deployment_id=run.deployment_id,
            agent_id=run.agent_id,
            agent_version_id=run.agent_version_id,
            status=run.status.value,
            error_summary=_error_summary(run),
            created_at=run.created_at.isoformat(),
        )
        for run in sorted(failures, key=lambda item: item.created_at, reverse=True)[:10]
    ]


def action_summary(
    *,
    deployments: DeploymentRuntimeControlService,
    actor: AuthenticatedActor,
    tenant_id: int,
    project_id: int,
    environment: str,
    resource_type: str | None,
    resource_id: int | None,
) -> ConsoleActionSummary:
    if resource_type and resource_type != "deployment":
        return ConsoleActionSummary(actions=[])
    deployment_records = _scoped_deployments(
        deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    if resource_id is not None:
        deployment_records = [
            deployment for deployment in deployment_records if deployment.id == resource_id
        ]
    actions: list[ConsoleActionAvailability] = []
    for deployment in deployment_records:
        actions.extend(_deployment_actions(deployment, actor))
    return ConsoleActionSummary(actions=actions)


def pending_actions(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    actor: AuthenticatedActor,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> list[ConsolePendingAction]:
    _ = runtime
    summary = action_summary(
        deployments=deployments,
        actor=actor,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        resource_type="deployment",
        resource_id=None,
    )
    pending: list[ConsolePendingAction] = []
    for action in summary.actions:
        if action.available:
            continue
        pending.append(
            ConsolePendingAction(
                resource_type=action.resource_type,
                resource_id=action.resource_id,
                action=action.action,
                label=action.action.removeprefix("deployment."),
                disabled_reason=action.disabled_reasons[0] if action.disabled_reasons else None,
                required_permissions=action.required_permissions,
                audit_required=action.audit_required,
            )
        )
    return pending[:10]


def _deployment_actions(
    deployment: DeploymentRecord,
    actor: AuthenticatedActor,
) -> list[ConsoleActionAvailability]:
    actions = {
        "deployment.activate": {"stopped", "paused", "active"},
        "deployment.pause": {"active"},
        "deployment.resume": {"paused"},
        "deployment.drain": {"active"},
        "deployment.stop": {"active", "paused", "draining"},
        "deployment.restart": {"active"},
    }
    result: list[ConsoleActionAvailability] = []
    has_permission = "*" in actor.scopes or "agent:deploy" in actor.scopes
    for action, allowed_statuses in actions.items():
        disabled_reasons: list[str] = []
        if deployment.desired_status.value not in allowed_statuses:
            disabled_reasons.append(_status_disabled_reason(action))
        if not has_permission:
            disabled_reasons.append("Current actor lacks agent:deploy permission.")
        result.append(
            ConsoleActionAvailability(
                resource_type="deployment",
                resource_id=deployment.id,
                action=action,
                available=not disabled_reasons,
                disabled_reasons=disabled_reasons,
                required_permissions=["agent:deploy"],
                policy_warnings=["Policy Engine enforces this action on submit."],
                audit_required=True,
            )
        )
    return result


def _status_disabled_reason(action: str) -> str:
    reasons = {
        "deployment.activate": "Deployment must be stopped, paused, or active before activation.",
        "deployment.pause": "Deployment must be active before it can be paused.",
        "deployment.resume": "Deployment must be paused before it can resume.",
        "deployment.drain": "Deployment must be active before it can drain.",
        "deployment.stop": "Deployment must be active, paused, or draining before it can stop.",
        "deployment.restart": "Deployment must be active before it can restart.",
    }
    return reasons[action]


def _scoped_deployments(
    deployments: DeploymentRuntimeControlService,
    *,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> list[DeploymentRecord]:
    return [
        deployment
        for deployment in deployments.deployments.list(tenant_id=tenant_id, project_id=project_id)
        if deployment.environment == environment
    ]


def _scoped_runs(
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    *,
    tenant_id: int,
    project_id: int,
    deployment_ids: set[int],
) -> list[NativeRun]:
    return [
        run
        for run in runtime.list_runs(tenant_id=tenant_id, project_id=project_id)
        if run.deployment_id in deployment_ids
    ]


def _error_summary(run: NativeRun) -> str:
    if not run.error:
        return "Run failed."
    message = run.error.get("message")
    return str(message) if message else "Run failed."


def _percentile(values: Iterable[int], percentile: float) -> int:
    sorted_values = sorted(values)
    if not sorted_values:
        return 0
    index = min(len(sorted_values) - 1, round((len(sorted_values) - 1) * percentile))
    return sorted_values[index]
