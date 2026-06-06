from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from dimoo_run.api.console import service
from dimoo_run.api.console.schemas import (
    ConsoleActionSummary,
    ConsoleDashboardSummary,
    ConsoleDeploymentHealth,
    ConsolePendingAction,
    ConsoleRecentFailure,
    ConsoleRuntimeOverview,
    ConsoleWorkerHealth,
)
from dimoo_run.api.dependencies import (
    AuthorizationHeader,
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    authenticate_api_key,
    error_response,
)
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.deployments import get_deployment_control
from dimoo_run.api.native.runtime import NativeRuntimeStore, SQLAlchemyNativeRuntimeStore
from dimoo_run.deployments.service import DeploymentRuntimeControlService
from dimoo_run.security.api_keys import AuthenticatedActor

router = APIRouter(prefix="/v1/console", tags=["console-aggregate"])

NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]
DeploymentControlDep = Annotated[
    DeploymentRuntimeControlService,
    Depends(get_deployment_control),
]


def _console_read_actor(
    *,
    authorization: str | None,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
    request_id: str | None,
) -> tuple[AuthenticatedActor, int, int, str] | JSONResponse:
    if tenant_id is None or project_id is None:
        return error_response(
            status_code=400,
            error_code="request_scope_required",
            message="X-Tenant-Id and X-Project-Id headers are required.",
            request_id=request_id,
            details={"required_headers": ["X-Tenant-Id", "X-Project-Id"]},
        )
    actor = authenticate_api_key(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        required_scope="agent:read",
        request_id=request_id,
    )
    if isinstance(actor, JSONResponse):
        return actor
    return actor, tenant_id, project_id, environment or "production"


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
    auth = _console_read_actor(
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
    auth = _console_read_actor(
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
    auth = _console_read_actor(
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
    auth = _console_read_actor(
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
    auth = _console_read_actor(
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
    auth = _console_read_actor(
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
    auth = _console_read_actor(
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
