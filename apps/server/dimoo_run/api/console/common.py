from typing import Annotated

from fastapi import Depends, Header
from fastapi.responses import JSONResponse

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

NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]
DeploymentControlDep = Annotated[
    DeploymentRuntimeControlService,
    Depends(get_deployment_control),
]
AuditReasonHeader = Annotated[str | None, Header(alias="X-Audit-Reason")]


def console_read_actor(
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


__all__ = [
    "AuditReasonHeader",
    "AuthorizationHeader",
    "DeploymentControlDep",
    "EnvironmentHeader",
    "NativeRuntimeDep",
    "ProjectIdHeader",
    "RequestIdHeader",
    "TenantIdHeader",
    "console_read_actor",
]
