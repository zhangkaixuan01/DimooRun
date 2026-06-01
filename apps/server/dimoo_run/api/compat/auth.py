from typing import Annotated

from fastapi import Header, Response
from fastapi.responses import JSONResponse

from dimoo_run.api.dependencies import (
    AuthorizationHeader,
    RequestIdHeader,
    authenticate_api_key,
    error_response,
)
from dimoo_run.security.api_keys import AuthenticatedActor

TenantIdHeader = Annotated[int | None, Header(alias="X-Tenant-Id")]
ProjectIdHeader = Annotated[int | None, Header(alias="X-Project-Id")]


def require_compat_api_key(
    response: Response,
    authorization: AuthorizationHeader,
    tenant_id: int | None,
    project_id: int | None,
    x_request_id: RequestIdHeader,
    *,
    required_scope: str = "agent:invoke",
) -> AuthenticatedActor | JSONResponse:
    _ = response
    if authorization is None or not authorization.startswith("Bearer "):
        return error_response(
            status_code=401,
            error_code="api_key_invalid",
            message="A bearer API key is required for Compatibility API.",
            request_id=x_request_id,
            details={"required_header": "Authorization"},
        )
    if tenant_id is None or project_id is None:
        return error_response(
            status_code=400,
            error_code="request_scope_required",
            message="X-Tenant-Id and X-Project-Id headers are required.",
            request_id=x_request_id,
            details={"required_headers": ["X-Tenant-Id", "X-Project-Id"]},
        )
    return authenticate_api_key(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        required_scope=required_scope,
        request_id=x_request_id,
    )
