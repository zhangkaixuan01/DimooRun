from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

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
from dimoo_run.api.console.schemas import ConsoleAgentInstance, ConsoleAgentInstanceDetail
from dimoo_run.runtime.capacity import build_agent_instance_views

router = APIRouter(prefix="/v1/console", tags=["console-runtime-instances"])


@router.get("/agent-instances", response_model=None)
def list_agent_instances(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
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
    items = [
        ConsoleAgentInstance.model_validate(item).model_dump(mode="json")
        for item in build_agent_instance_views(
            deployments=deployments,
            runtime=runtime,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    ]
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.get("/agent-instances/{instance_id}", response_model=None)
def get_agent_instance(
    instance_id: int,
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
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
    item = next(
        (
            item
            for item in build_agent_instance_views(
                deployments=deployments,
                runtime=runtime,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
            )
            if item["id"] == instance_id
        ),
        None,
    )
    if item is None:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "agent_instance_not_found",
                "message": "Agent instance was not found.",
                "request_id": x_request_id,
                "details": {"instance_id": instance_id},
            },
        )
    return {
        "item": ConsoleAgentInstanceDetail.model_validate(item).model_dump(mode="json"),
        "request_id": x_request_id,
    }
