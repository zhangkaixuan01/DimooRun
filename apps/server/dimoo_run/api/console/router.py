from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from dimoo_run.api.console import service
from dimoo_run.api.console.common import (
    AuthorizationHeader,
    DeploymentControlDep,
    EnvironmentHeader,
    NativeRuntimeDep,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    console_read_actor,
)
from dimoo_run.api.console.schemas import (
    ConsoleActionSummary,
    ConsoleDashboardSummary,
    ConsoleDeploymentHealth,
    ConsolePendingAction,
    ConsoleRecentFailure,
    ConsoleRuntimeOverview,
    ConsoleWorkerHealth,
)

router = APIRouter(prefix="/v1/console", tags=["console-aggregate"])


@router.get("/dashboard-summary", response_model=ConsoleDashboardSummary)
def get_dashboard_summary(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> ConsoleDashboardSummary | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    _, tenant_id, project_id, environment = auth
    return service.dashboard_summary(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )


@router.get("/runtime-overview", response_model=ConsoleRuntimeOverview)
def get_runtime_overview(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> ConsoleRuntimeOverview | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    actor, tenant_id, project_id, environment = auth
    return service.runtime_overview(
        runtime=runtime,
        deployments=deployments,
        actor=actor,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )


@router.get("/deployment-health", response_model=list[ConsoleDeploymentHealth])
def get_deployment_health(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[ConsoleDeploymentHealth] | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    _, tenant_id, project_id, environment = auth
    return service.deployment_health_summary(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )


@router.get("/worker-health", response_model=list[ConsoleWorkerHealth])
def get_worker_health(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[ConsoleWorkerHealth] | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    _, tenant_id, project_id, environment = auth
    return service.worker_health_summary(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )


@router.get("/recent-failures", response_model=list[ConsoleRecentFailure])
def get_recent_failures(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[ConsoleRecentFailure] | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    _, tenant_id, project_id, environment = auth
    return service.recent_failures(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )


@router.get("/pending-actions", response_model=list[ConsolePendingAction])
def get_pending_actions(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[ConsolePendingAction] | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    actor, tenant_id, project_id, environment = auth
    return service.pending_actions(
        runtime=runtime,
        deployments=deployments,
        actor=actor,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )


@router.get("/action-summary", response_model=ConsoleActionSummary)
def get_action_summary(
    deployments: DeploymentControlDep,
    resource_type: Annotated[str | None, Query()] = None,
    resource_id: Annotated[int | None, Query()] = None,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> ConsoleActionSummary | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    actor, tenant_id, project_id, environment = auth
    return service.action_summary(
        deployments=deployments,
        actor=actor,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        resource_type=resource_type,
        resource_id=resource_id,
    )
