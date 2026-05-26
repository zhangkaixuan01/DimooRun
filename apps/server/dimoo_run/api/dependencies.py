from typing import Annotated, Any

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from dimoo_run.domain.schemas import ErrorResponse
from dimoo_run.identity.service_accounts import ServiceAccountRegistry
from dimoo_run.security.api_keys import (
    APIKeyAuthenticator,
    APIKeyDisabledError,
    APIKeyError,
    APIKeyScopeError,
    AuthenticatedActor,
)

RequestIdHeader = Annotated[str | None, Header(alias="X-Request-Id")]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]
AuthorizationHeader = Annotated[str | None, Header(alias="Authorization")]

_default_service_accounts = ServiceAccountRegistry()
_default_api_key_authenticator = APIKeyAuthenticator(service_accounts=_default_service_accounts)


def default_api_key_authenticator() -> APIKeyAuthenticator:
    return _default_api_key_authenticator


def reset_api_key_authenticator() -> None:
    global _default_service_accounts, _default_api_key_authenticator
    _default_service_accounts = ServiceAccountRegistry()
    _default_api_key_authenticator = APIKeyAuthenticator(service_accounts=_default_service_accounts)


def authenticate_api_key(
    *,
    authorization: str | None,
    tenant_id: str,
    project_id: str | None,
    required_scope: str,
    request_id: str | None,
    authenticator: APIKeyAuthenticator | None = None,
) -> AuthenticatedActor | JSONResponse:
    if authorization is None or not authorization.startswith("Bearer "):
        return error_response(
            status_code=401,
            error_code="api_key_invalid",
            message="A bearer API key is required.",
            request_id=request_id,
            details={"required_header": "Authorization"},
        )
    try:
        return (authenticator or default_api_key_authenticator()).authenticate(
            authorization.removeprefix("Bearer ").strip(),
            tenant_id=tenant_id,
            project_id=project_id,
            required_scope=required_scope,
        )
    except APIKeyScopeError as exc:
        return error_response(
            status_code=403,
            error_code=exc.error_code,
            message=str(exc),
            request_id=request_id,
            details={"required_scope": required_scope},
        )
    except APIKeyDisabledError as exc:
        return error_response(
            status_code=401,
            error_code=exc.error_code,
            message=str(exc),
            request_id=request_id,
            details={},
        )
    except APIKeyError as exc:
        return error_response(
            status_code=401,
            error_code=exc.error_code,
            message=str(exc),
            request_id=request_id,
            details={},
        )


def not_implemented_response(
    request: Request,
    request_id: str | None,
    *,
    audit_required: bool = False,
    extra_details: dict[str, Any] | None = None,
) -> tuple[ErrorResponse, int]:
    details: dict[str, Any] = {"path": request.url.path}
    if audit_required:
        details["audit_required"] = True
    if extra_details:
        details.update(extra_details)
    return (
        ErrorResponse(
            error_code="not_implemented",
            message="This API contract is registered but not implemented yet.",
            request_id=request_id,
            details=details,
        ),
        501,
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
