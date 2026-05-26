from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from dimoo_run.api.compat.auth import ProjectIdHeader, TenantIdHeader, require_compat_api_key
from dimoo_run.api.dependencies import AuthorizationHeader, RequestIdHeader

router = APIRouter(prefix="/agent-protocol", tags=["compat-agent-protocol"])


@router.get("/capabilities", response_model=None)
def get_capabilities(
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = require_compat_api_key(
        response,
        authorization,
        x_tenant_id,
        x_project_id,
        x_request_id,
        required_scope="agent:read",
    )
    if isinstance(auth, JSONResponse):
        return auth
    return {
        "protocol": "agent-protocol",
        "compat_api_version": "1.0",
        "supported": [],
        "unsupported": ["studio-debug", "remote-sessions"],
        "unsupported_error_code": "compatibility_not_supported",
    }
