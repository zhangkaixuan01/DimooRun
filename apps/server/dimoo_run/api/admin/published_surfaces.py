from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
)
from dimoo_run.core.config import Settings
from dimoo_run.gateway.route_tester import (
    publish_surface,
    rollout_surface,
    sync_state,
    validate_publish,
)

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]


def _sync() -> None:
    sync_state(Settings.from_env().database.url)


@router.post("/v1/published-surfaces/validate")
def validate_published_surface(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    _sync()
    data = payload or {}
    result = validate_publish(dict(data.get("surface") or data))
    return {
        **result,
        "audit": {
            "action": "published_surface.validate",
            "resource_type": "published_surface",
            "resource_id": data.get("surface_id"),
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
        "request_id": x_request_id,
    }


@router.post("/v1/published-surfaces/publish")
def publish_validated_surface(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    _sync()
    data = payload or {}
    audit_scope = {
        "tenant_id": x_tenant_id,
        "project_id": x_project_id,
        "environment": x_environment,
    }
    result = publish_surface(
        dict(data.get("surface") or data),
        request_id=x_request_id,
        audit_scope=audit_scope,
    )
    surface = result.get("surface")
    resource_id = surface.get("id") if isinstance(surface, dict) else None
    audit_preview = result.get("audit_preview")
    audit_action = (
        audit_preview.get("action")
        if resource_id is None and isinstance(audit_preview, dict)
        else "published_surface.publish"
    )
    return {
        **result,
        "audit": {
            "action": audit_action,
            "resource_type": "published_surface",
            "resource_id": resource_id,
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
        "request_id": x_request_id,
    }


@router.post("/v1/published-surfaces/{surface_id}/rollout")
def rollout_published_surface(
    surface_id: int,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    _sync()
    audit_scope = {
        "tenant_id": x_tenant_id,
        "project_id": x_project_id,
        "environment": x_environment,
    }
    status_code, body = rollout_surface(
        surface_id,
        payload or {},
        request_id=x_request_id,
        audit_scope=audit_scope,
    )
    if status_code >= 400:
        audit_preview = body.get("audit_preview")
        audit_action = (
            audit_preview.get("action")
            if isinstance(audit_preview, dict)
            else "published_surface.rollout.blocked"
        )
        return JSONResponse(
            status_code=status_code,
            content={
                **body,
                "audit": {
                    "action": audit_action,
                    "resource_type": "published_surface",
                    "resource_id": surface_id,
                    "request_id": x_request_id,
                    "tenant_id": x_tenant_id,
                    "project_id": x_project_id,
                    "environment": x_environment,
                },
            },
        )
    audit = body.get("audit")
    if isinstance(audit, dict):
        return {
            **body,
            "audit": {
                **audit,
                "tenant_id": x_tenant_id,
                "project_id": x_project_id,
                "environment": x_environment,
            },
        }
    return body
