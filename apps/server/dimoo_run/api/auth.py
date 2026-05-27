from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dimoo_run.api.dependencies import (
    AuthorizationHeader,
    RequestIdHeader,
    authenticate_console_operator,
    change_console_operator_password,
    console_operator_to_public,
    create_console_operator,
    ensure_bootstrap_operator,
    get_console_operator_by_session,
    list_console_operators,
    require_console_actor,
    revoke_console_session,
    update_console_operator,
)
from dimoo_run.identity.console import ConsoleIdentityUnavailableError
from dimoo_run.security.api_keys import AuthenticatedActor

router = APIRouter(prefix="/v1", tags=["auth"])
ConsoleActorDep = Annotated[AuthenticatedActor | JSONResponse, Depends(require_console_actor)]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class OperatorCreateRequest(BaseModel):
    email: str = Field(min_length=3)
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)
    roles: list[str] = Field(default_factory=lambda: ["runtime_operator"])
    permissions: list[str] = Field(default_factory=lambda: ["agent:read", "run:read"])
    allowed_scopes: list[dict[str, str]] = Field(default_factory=list)


class OperatorUpdateRequest(BaseModel):
    name: str | None = None
    roles: list[str] | None = None
    permissions: list[str] | None = None
    allowed_scopes: list[dict[str, str]] | None = None
    status: str | None = None


class OperatorPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8)


@router.get("/auth/bootstrap", response_model=None)
def get_bootstrap_status() -> dict[str, object]:
    operator = ensure_bootstrap_operator()
    return {
        "configured": True,
        "operator": console_operator_to_public(operator),
    }


@router.post("/auth/login", response_model=None)
def login(
    payload: LoginRequest,
    x_request_id: RequestIdHeader = None,
) -> dict[str, object] | JSONResponse:
    try:
        session = authenticate_console_operator(payload.email, payload.password)
    except ConsoleIdentityUnavailableError:
        return JSONResponse(
            status_code=503,
            content={
                "error_code": "redis_unavailable",
                "message": "Console session store is unavailable.",
                "request_id": x_request_id,
                "details": {},
            },
        )
    if session is None:
        return JSONResponse(
            status_code=401,
            content={
                "error_code": "invalid_credentials",
                "message": "Email or password is incorrect.",
                "request_id": x_request_id,
                "details": {},
            },
        )
    operator = get_console_operator_by_session(session.token)
    assert operator is not None
    return {
        "access_token": session.token,
        "token_type": "bearer",
        "expires_at": session.expires_at.isoformat(),
        "operator": console_operator_to_public(operator),
        "request_id": x_request_id,
    }


@router.get("/auth/me", response_model=None)
def me(
    actor: ConsoleActorDep,
    authorization: AuthorizationHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, object] | JSONResponse:
    if isinstance(actor, JSONResponse):
        return actor
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    try:
        operator = get_console_operator_by_session(token)
    except ConsoleIdentityUnavailableError:
        return JSONResponse(
            status_code=503,
            content={
                "error_code": "redis_unavailable",
                "message": "Console session store is unavailable.",
                "request_id": x_request_id,
                "details": {},
            },
        )
    if operator is None:
        return JSONResponse(
            status_code=401,
            content={
                "error_code": "session_invalid",
                "message": "Console session is invalid or expired.",
                "request_id": x_request_id,
                "details": {},
            },
        )
    return {"operator": console_operator_to_public(operator), "request_id": x_request_id}


@router.post("/auth/logout", response_model=None)
def logout(authorization: AuthorizationHeader = None) -> dict[str, object]:
    if authorization and authorization.startswith("Bearer "):
        revoke_console_session(authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


@router.post("/auth/change-password", response_model=None)
def change_password(
    payload: ChangePasswordRequest,
    actor: ConsoleActorDep,
    x_request_id: RequestIdHeader = None,
) -> dict[str, object] | JSONResponse:
    if isinstance(actor, JSONResponse):
        return actor
    changed = change_console_operator_password(
        actor.actor_id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    if not changed:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "password_change_failed",
                "message": "Current password is incorrect.",
                "request_id": x_request_id,
                "details": {},
            },
        )
    return {"ok": True, "request_id": x_request_id}


@router.get("/identity/operators", response_model=None)
def list_operators(
    actor: ConsoleActorDep,
    x_request_id: RequestIdHeader = None,
) -> dict[str, object] | JSONResponse:
    if isinstance(actor, JSONResponse):
        return actor
    return {
        "items": [console_operator_to_public(operator) for operator in list_console_operators()],
        "count": len(list_console_operators()),
        "request_id": x_request_id,
    }


@router.post("/identity/operators", status_code=201, response_model=None)
def create_operator(
    payload: OperatorCreateRequest,
    actor: ConsoleActorDep,
    x_request_id: RequestIdHeader = None,
) -> dict[str, object] | JSONResponse:
    if isinstance(actor, JSONResponse):
        return actor
    denied = _require_console_permission(actor, "identity:operator:write", x_request_id)
    if denied is not None:
        return denied
    try:
        operator = create_console_operator(
            email=payload.email,
            name=payload.name,
            password=payload.password,
            roles=payload.roles,
            permissions=set(payload.permissions),
            allowed_scopes=payload.allowed_scopes or None,
        )
    except ValueError:
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "operator_email_exists",
                "message": "Operator email already exists.",
                "request_id": x_request_id,
                "details": {"email": payload.email},
            },
        )
    return {"item": console_operator_to_public(operator), "request_id": x_request_id}


@router.patch("/identity/operators/{operator_id}", response_model=None)
def update_operator(
    operator_id: str,
    payload: OperatorUpdateRequest,
    actor: ConsoleActorDep,
    x_request_id: RequestIdHeader = None,
) -> dict[str, object] | JSONResponse:
    if isinstance(actor, JSONResponse):
        return actor
    denied = _require_console_permission(actor, "identity:operator:write", x_request_id)
    if denied is not None:
        return denied
    operator = update_console_operator(
        operator_id,
        name=payload.name,
        roles=payload.roles,
        permissions=set(payload.permissions) if payload.permissions is not None else None,
        allowed_scopes=payload.allowed_scopes,
        status=payload.status,
    )
    if operator is None:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "operator_not_found",
                "message": "Operator was not found.",
                "request_id": x_request_id,
                "details": {"operator_id": operator_id},
            },
        )
    return {"item": console_operator_to_public(operator), "request_id": x_request_id}


@router.post("/identity/operators/{operator_id}/reset-password", response_model=None)
def reset_operator_password(
    operator_id: str,
    payload: OperatorPasswordResetRequest,
    actor: ConsoleActorDep,
    x_request_id: RequestIdHeader = None,
) -> dict[str, object] | JSONResponse:
    if isinstance(actor, JSONResponse):
        return actor
    denied = _require_console_permission(actor, "identity:operator:write", x_request_id)
    if denied is not None:
        return denied
    changed = change_console_operator_password(
        operator_id,
        current_password=None,
        new_password=payload.new_password,
        require_current=False,
    )
    if not changed:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "operator_not_found",
                "message": "Operator was not found.",
                "request_id": x_request_id,
                "details": {"operator_id": operator_id},
            },
        )
    return {"ok": True, "request_id": x_request_id}


def _require_console_permission(
    actor: AuthenticatedActor,
    permission: str,
    request_id: str | None,
) -> JSONResponse | None:
    if "*" in actor.scopes or permission in actor.scopes:
        return None
    return JSONResponse(
        status_code=403,
        content={
            "error_code": "permission_denied",
            "message": "Console write permission is required.",
            "request_id": request_id,
            "details": {"required_scope": permission},
        },
    )
