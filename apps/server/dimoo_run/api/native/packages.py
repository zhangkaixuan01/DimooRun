from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dimoo_run.api.compat.auth import ProjectIdHeader, TenantIdHeader
from dimoo_run.api.dependencies import AuthorizationHeader, RequestIdHeader, authenticate_api_key
from dimoo_run.packages.validation import (
    PackageValidationRequest,
    PackageValidationResult,
    validate_package,
)

router = APIRouter(tags=["native-packages"])


class PackageValidationPayload(BaseModel):
    package_uri: str = Field(min_length=1)
    framework: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    entrypoint: str = Field(min_length=1)
    manifest: dict[str, Any] = Field(default_factory=dict)
    required_secret_refs: list[str] = Field(default_factory=list)


class PackageValidationErrorRead(BaseModel):
    field: str
    code: str
    message: str


class PackageValidationRead(BaseModel):
    status: str
    ready: bool
    validation_token: str | None
    errors: list[PackageValidationErrorRead]
    warnings: list[str]
    missing_secret_refs: list[str]
    capabilities: dict[str, Any]
    next_action: str


@router.post("/packages/validate", response_model=PackageValidationRead)
def validate_agent_package(
    payload: PackageValidationPayload,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> PackageValidationRead | JSONResponse:
    if x_tenant_id is None or x_project_id is None:
        from dimoo_run.api.dependencies import error_response

        return error_response(
            status_code=400,
            error_code="request_scope_required",
            message="X-Tenant-Id and X-Project-Id headers are required.",
            request_id=x_request_id,
            details={"required_headers": ["X-Tenant-Id", "X-Project-Id"]},
        )
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:write",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    result = validate_package(
        PackageValidationRequest(
            package_uri=payload.package_uri,
            framework=payload.framework,
            adapter=payload.adapter,
            entrypoint=payload.entrypoint,
            manifest=payload.manifest,
            required_secret_refs=payload.required_secret_refs,
        )
    )
    return package_validation_to_read(result)


def package_validation_to_read(result: PackageValidationResult) -> PackageValidationRead:
    return PackageValidationRead(
        status=result.status,
        ready=result.ready,
        validation_token=result.validation_token,
        errors=[
            PackageValidationErrorRead(
                field=error.field,
                code=error.code,
                message=error.message,
            )
            for error in result.errors
        ],
        warnings=result.warnings,
        missing_secret_refs=result.missing_secret_refs,
        capabilities=result.capabilities,
        next_action=result.next_action,
    )
