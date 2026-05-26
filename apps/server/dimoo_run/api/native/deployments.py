from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from dimoo_run.api.dependencies import AuthorizationHeader, RequestIdHeader, authenticate_api_key
from dimoo_run.deployments.service import (
    DeploymentNotFoundError,
    DeploymentRecord,
    DeploymentRuntimeControlService,
    PolicyDeniedError,
)
from dimoo_run.domain.schemas import AgentInstanceRead, DeploymentRead, ErrorResponse

router = APIRouter(tags=["native-deployments"])
ActorIdHeader = Annotated[str | None, Header(alias="X-Actor-Id")]
TenantIdHeader = Annotated[str | None, Header(alias="X-Tenant-Id")]
ProjectIdHeader = Annotated[str | None, Header(alias="X-Project-Id")]

_default_deployment_control = DeploymentRuntimeControlService()


def default_deployment_control() -> DeploymentRuntimeControlService:
    return _default_deployment_control


def reset_deployment_control() -> None:
    global _default_deployment_control
    _default_deployment_control = DeploymentRuntimeControlService()


def get_deployment_control() -> DeploymentRuntimeControlService:
    return _default_deployment_control


DeploymentControlDep = Annotated[
    DeploymentRuntimeControlService,
    Depends(get_deployment_control),
]
CONTROL_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


@router.get(
    "/deployments",
    response_model=list[DeploymentRead],
    responses={400: {"model": ErrorResponse}},
)
def list_deployments(
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> list[DeploymentRead] | JSONResponse:
    scope_error = require_scope(
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if scope_error is not None:
        return scope_error
    assert x_tenant_id is not None
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:read",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    return [
        deployment_to_read(deployment)
        for deployment in service.deployments.list(
            tenant_id=x_tenant_id,
            project_id=x_project_id,
        )
    ]


@router.get(
    "/deployments/{deployment_id}",
    response_model=DeploymentRead,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    scope_error = require_scope(
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if scope_error is not None:
        return scope_error
    assert x_tenant_id is not None
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:read",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    try:
        deployment = service.deployments.get(deployment_id)
    except DeploymentNotFoundError:
        return error_response(
            status_code=404,
            error_code="deployment_not_found",
            message="Deployment was not found.",
            request_id=x_request_id,
            details={"deployment_id": deployment_id},
        )
    if not deployment_in_scope(deployment, tenant_id=x_tenant_id, project_id=x_project_id):
        return deployment_not_found(deployment_id, x_request_id)
    return deployment_to_read(deployment)


@router.get(
    "/deployments/{deployment_id}/instances",
    response_model=list[AgentInstanceRead],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def list_deployment_instances(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> list[AgentInstanceRead] | JSONResponse:
    scope_error = require_scope(
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if scope_error is not None:
        return scope_error
    assert x_tenant_id is not None
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:read",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    try:
        deployment = service.deployments.get(deployment_id)
        if not deployment_in_scope(deployment, tenant_id=x_tenant_id, project_id=x_project_id):
            return deployment_not_found(deployment_id, x_request_id)
        return [instance_to_read(instance) for instance in service.list_instances(deployment_id)]
    except DeploymentNotFoundError:
        return deployment_not_found(deployment_id, x_request_id)


def control_response(
    deployment_id: str,
    *,
    action: Callable[[str, str], DeploymentRecord],
    service: DeploymentRuntimeControlService,
    request_id: str | None,
    tenant_id: str | None,
    project_id: str | None,
    authorization: str | None,
) -> DeploymentRead | JSONResponse:
    scope_error = require_scope(
        tenant_id=tenant_id,
        project_id=project_id,
        request_id=request_id,
    )
    if scope_error is not None:
        return scope_error
    assert tenant_id is not None
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        required_scope="agent:deploy",
        request_id=request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    try:
        deployment_scope = service.deployments.get(deployment_id)
        if not deployment_in_scope(
            deployment_scope,
            tenant_id=tenant_id,
            project_id=project_id,
        ):
            return deployment_not_found(deployment_id, request_id)
        deployment = action(deployment_id, auth.actor_id)
    except DeploymentNotFoundError:
        return deployment_not_found(deployment_id, request_id)
    except PolicyDeniedError as exc:
        return error_response(
            status_code=403,
            error_code=exc.error_code,
            message=exc.reason,
            request_id=request_id,
            details={"deployment_id": deployment_id},
        )
    return deployment_to_read(deployment)


@router.post(
    "/deployments/{deployment_id}/activate",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def activate_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.activate(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/pause",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def pause_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.pause(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/resume",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def resume_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.resume(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/drain",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def drain_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.drain(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/stop",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def stop_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.stop(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/restart",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def restart_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.restart(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


def deployment_to_read(deployment: DeploymentRecord) -> DeploymentRead:
    return DeploymentRead.model_validate(deployment.__dict__)


def instance_to_read(instance: object) -> AgentInstanceRead:
    return AgentInstanceRead.model_validate(instance.__dict__)


def require_scope(
    *,
    tenant_id: str | None,
    project_id: str | None,
    request_id: str | None,
) -> JSONResponse | None:
    if tenant_id is not None and project_id is not None:
        return None
    return error_response(
        status_code=400,
        error_code="request_scope_required",
        message="X-Tenant-Id and X-Project-Id headers are required.",
        request_id=request_id,
        details={"required_headers": ["X-Tenant-Id", "X-Project-Id"]},
    )


def deployment_in_scope(
    deployment: DeploymentRecord,
    *,
    tenant_id: str | None,
    project_id: str | None,
) -> bool:
    return deployment.tenant_id == tenant_id and deployment.project_id == project_id


def deployment_not_found(deployment_id: str, request_id: str | None) -> JSONResponse:
    return error_response(
        status_code=404,
        error_code="deployment_not_found",
        message="Deployment was not found.",
        request_id=request_id,
        details={"deployment_id": deployment_id},
    )


def error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    request_id: str | None,
    details: dict[str, Any],
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error_code=error_code,
            message=message,
            request_id=request_id,
            details=details,
        ).model_dump(mode="json"),
    )
