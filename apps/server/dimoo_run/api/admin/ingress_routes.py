from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends

from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
)
from dimoo_run.core.config import Settings
from dimoo_run.gateway.route_tester import sync_state, test_route

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]


@router.post("/v1/ingress-routes/test")
def test_ingress_route(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    sync_state(Settings.from_env().database.url)
    result = test_route(payload or {}, request_id=x_request_id)
    matched_deployment = result.get("matched_deployment")
    resource_id = (
        matched_deployment.get("route_id")
        if isinstance(matched_deployment, dict)
        else None
    )
    return {
        **result,
        "audit": {
            "action": "ingress_route.test",
            "resource_type": "ingress_route",
            "resource_id": resource_id,
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
        "request_id": x_request_id,
    }
