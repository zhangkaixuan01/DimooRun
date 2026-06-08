import json
import os
from typing import Annotated, Any

from fastapi import Cookie, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, inspect, select, text

from dimoo_run.core.config import Settings
from dimoo_run.domain.models import APIKey, Environment, Project, ServiceAccount, Tenant
from dimoo_run.domain.schemas import ErrorResponse
from dimoo_run.identity.console import (
    ConsoleIdentityUnavailableError,
    ConsoleOperator,
    ConsoleOperatorSessionRecord,
    ConsoleSession,
    default_console_identity_service,
    reset_default_console_identity_service,
)
from dimoo_run.identity.console import (
    console_operator_session_to_public as _console_operator_session_to_public,
)
from dimoo_run.identity.console import (
    console_operator_to_public as _console_operator_to_public,
)
from dimoo_run.identity.service_accounts import SQLAlchemyServiceAccountRegistry
from dimoo_run.persistence.database import Base, create_session_factory
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
ConsoleSessionCookie = Annotated[str | None, Cookie(alias="dimoorun_console_session")]
TenantIdHeader = Annotated[int | None, Header(alias="X-Tenant-Id")]
ProjectIdHeader = Annotated[int | None, Header(alias="X-Project-Id")]
EnvironmentHeader = Annotated[str | None, Header(alias="X-Environment")]

_default_api_key_authenticator: APIKeyAuthenticator | None = None


def reset_console_identity() -> None:
    service = default_console_identity_service()
    service.reset()
    reset_default_console_identity_service()


def ensure_bootstrap_operator() -> ConsoleOperator:
    return default_console_identity_service().ensure_bootstrap_operator()


def authenticate_console_operator(
    email: str,
    password: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ConsoleSession | None:
    return default_console_identity_service().authenticate(
        email,
        password,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def get_console_operator_by_session(token: str) -> ConsoleOperator | None:
    return default_console_identity_service().get_operator_by_session(token)


def revoke_console_session(token: str) -> None:
    default_console_identity_service().revoke_session(token)


def list_console_operators() -> list[ConsoleOperator]:
    return default_console_identity_service().list_operators()


def create_console_operator(
    *,
    email: str,
    name: str,
    password: str,
    roles: list[str] | None = None,
    permissions: set[str] | None = None,
    allowed_scopes: list[dict[str, Any]] | None = None,
) -> ConsoleOperator:
    return default_console_identity_service().create_operator(
        email=email,
        name=name,
        password=password,
        roles=roles,
        permissions=permissions,
        allowed_scopes=allowed_scopes,
    )


def update_console_operator(
    operator_id: int,
    *,
    name: str | None = None,
    roles: list[str] | None = None,
    permissions: set[str] | None = None,
    allowed_scopes: list[dict[str, Any]] | None = None,
    status: str | None = None,
) -> ConsoleOperator | None:
    return default_console_identity_service().update_operator(
        operator_id,
        name=name,
        roles=roles,
        permissions=permissions,
        allowed_scopes=allowed_scopes,
        status=status,
    )


def change_console_operator_password(
    operator_id: int,
    *,
    current_password: str | None,
    new_password: str,
    require_current: bool = True,
) -> bool:
    return default_console_identity_service().change_password(
        operator_id,
        current_password=current_password,
        new_password=new_password,
        require_current=require_current,
    )


def revoke_console_operator_sessions(operator_id: int, *, reason: str = "admin_revoked") -> bool:
    return default_console_identity_service().revoke_operator_sessions(operator_id, reason=reason)


def list_console_operator_sessions(operator_id: int) -> list[ConsoleOperatorSessionRecord] | None:
    return default_console_identity_service().list_operator_sessions(operator_id)


def delete_console_operator(operator_id: int) -> ConsoleOperator | None:
    return default_console_identity_service().delete_operator(operator_id)


def console_operator_to_public(operator: ConsoleOperator) -> dict[str, Any]:
    return _console_operator_to_public(operator)


def console_operator_session_to_public(session: ConsoleOperatorSessionRecord) -> dict[str, Any]:
    return _console_operator_session_to_public(session)


def default_api_key_authenticator() -> APIKeyAuthenticator:
    global _default_api_key_authenticator
    if _default_api_key_authenticator is None:
        settings = Settings.from_env()
        session_factory = create_session_factory(settings.database.url)
        if settings.runtime.mode == "dev":
            with session_factory() as session:
                Base.metadata.create_all(session.get_bind())
                _ensure_machine_identity_columns(session)
                _ensure_default_scope_resources(session)
        service_accounts = SQLAlchemyServiceAccountRegistry(session_factory)
        _default_api_key_authenticator = APIKeyAuthenticator(
            service_accounts=service_accounts,  # type: ignore[arg-type]
            session_factory=session_factory,
        )
    return _default_api_key_authenticator


def reset_api_key_authenticator() -> None:
    global _default_api_key_authenticator
    settings = Settings.from_env()
    if settings.runtime.mode == "dev" and not _is_missing_sqlite_database_file(
        settings.database.url
    ):
        session_factory = create_session_factory(settings.database.url)
        with session_factory() as session:
            Base.metadata.create_all(session.get_bind())
            _ensure_machine_identity_columns(session)
            _ensure_default_scope_resources(session)
            session.execute(delete(APIKey))
            session.execute(delete(ServiceAccount))
            session.commit()
    _default_api_key_authenticator = None


def _is_missing_sqlite_database_file(database_url: str) -> bool:
    sqlite_prefixes = ("sqlite:///", "sqlite+pysqlite:///")
    prefix = next(
        (candidate for candidate in sqlite_prefixes if database_url.startswith(candidate)),
        None,
    )
    if prefix is None:
        return False
    path = database_url.removeprefix(prefix)
    if path in {"", ":memory:"}:
        return False
    return not os.path.exists(path)


def authenticate_api_key(
    *,
    authorization: str | None,
    tenant_id: int,
    project_id: int | None,
    required_scope: str,
    request_id: str | None,
    console_session: str | None = None,
    environment: str | None = None,
    authenticator: APIKeyAuthenticator | None = None,
) -> AuthenticatedActor | JSONResponse:
    if authorization is None and console_session:
        authorization = f"Bearer {console_session.strip()}"
    if authorization is None or not authorization.startswith("Bearer "):
        return error_response(
            status_code=401,
            error_code="api_key_invalid",
            message="A bearer API key is required.",
            request_id=request_id,
            details={"required_header": "Authorization"},
        )
    plain_key = authorization.removeprefix("Bearer ").strip()
    if plain_key.startswith("sess_"):
        try:
            operator = get_console_operator_by_session(plain_key)
        except ConsoleIdentityUnavailableError:
            return error_response(
                status_code=503,
                error_code="redis_unavailable",
                message="Console session store is unavailable.",
                request_id=request_id,
                details={},
            )
        if operator is not None:
            if not _operator_can_access_scope(operator, tenant_id, project_id, environment):
                return error_response(
                    status_code=403,
                    error_code="scope_not_allowed",
                    message=(
                        "The selected tenant, project, or environment is not allowed "
                        "for this operator."
                    ),
                    request_id=request_id,
                    details={
                        "tenant_id": tenant_id,
                        "project_id": project_id,
                        "environment": environment,
                    },
                )
            return AuthenticatedActor(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_type="operator",
                actor_id=str(operator.id),
                scopes=frozenset(operator.permissions),
                api_key_id=None,
            )
    dev_key = os.getenv("DIMOORUN_DEV_API_KEY")
    runtime_mode = os.getenv("DIMOORUN_RUNTIME_MODE", "dev")
    if dev_key and runtime_mode == "dev" and plain_key == dev_key:
        return AuthenticatedActor(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_type="service_account",
            actor_id="dev_console",
            scopes=frozenset({"*"}),
            api_key_id=None,
        )
    try:
        return (authenticator or default_api_key_authenticator()).authenticate(
            plain_key,
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


def _operator_can_access_scope(
    operator: ConsoleOperator,
    tenant_id: int,
    project_id: int | None,
    environment: str | None,
) -> bool:
    return default_console_identity_service().can_access_scope(
        operator,
        tenant_id,
        project_id,
        environment,
    )


def require_console_actor(
    authorization: AuthorizationHeader = None,
    console_session: ConsoleSessionCookie = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> AuthenticatedActor | JSONResponse:
    if x_tenant_id is None:
        return error_response(
            status_code=400,
            error_code="request_scope_required",
            message="X-Tenant-Id header is required.",
            request_id=x_request_id,
            details={"required_headers": ["X-Tenant-Id"]},
        )
    actor = authenticate_api_key(
        authorization=authorization,
        console_session=console_session,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        required_scope="admin:read",
        request_id=x_request_id,
    )
    if isinstance(actor, JSONResponse):
        return actor
    if "*" not in actor.scopes and "admin:read" not in actor.scopes:
        return error_response(
            status_code=403,
            error_code="permission_denied",
            message="Console admin access is required.",
            request_id=x_request_id,
            details={"required_scope": "admin:read"},
        )
    return actor


def enforce_console_actor(
    request: Request,
    authorization: AuthorizationHeader = None,
    console_session: ConsoleSessionCookie = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> AuthenticatedActor:
    actor = require_console_actor(
        authorization=authorization,
        console_session=console_session,
        x_tenant_id=x_tenant_id,
        x_project_id=x_project_id,
        x_environment=x_environment,
        x_request_id=x_request_id,
    )
    if isinstance(actor, JSONResponse):
        raise HTTPException(
            status_code=actor.status_code,
            detail=json.loads(bytes(actor.body).decode("utf-8")),
        )
    required_permission = _required_console_permission(request.method, request.url.path)
    if required_permission and "*" not in actor.scopes and required_permission not in actor.scopes:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "permission_denied",
                "message": "Console write permission is required.",
                "request_id": x_request_id,
                "details": {"required_scope": required_permission},
            },
        )
    return actor


def _required_console_permission(method: str, path: str) -> str | None:
    if method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return None
    if "/v1/identity/operators" in path:
        return "identity:operator:write"
    if "/v1/identity/roles" in path:
        return "identity:role:write"
    if "/v1/identity/permissions" in path:
        return "identity:permission:write"
    if (
        "/v1/identity/tenants" in path
        or "/v1/identity/projects" in path
        or "/v1/identity/environments" in path
    ):
        return "identity:scope:write"
    if "/v1/identity/service-accounts" in path:
        if "/api-keys" in path:
            return "identity:api-key:write"
        return "identity:service-account:write"
    return "admin:write"


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


def _ensure_machine_identity_columns(session: Any) -> None:
    bind = session.get_bind()
    inspector = inspect(bind)
    service_account_columns = {
        column["name"] for column in inspector.get_columns("service_accounts")
    }
    api_key_columns = {column["name"] for column in inspector.get_columns("api_keys")}
    if "permissions_json" not in service_account_columns:
        session.execute(
            text(
                "ALTER TABLE service_accounts "
                "ADD COLUMN permissions_json JSON NOT NULL DEFAULT '[]'"
            )
        )
    if "key_prefix" not in api_key_columns:
        session.execute(
            text(
                "ALTER TABLE api_keys "
                "ADD COLUMN key_prefix VARCHAR(32) NOT NULL DEFAULT ''"
            )
        )
    session.commit()


def _ensure_default_scope_resources(session: Any) -> None:
    tenant_slug = os.getenv("DIMOORUN_DEFAULT_TENANT_SLUG", "default-tenant")
    project_slug = os.getenv("DIMOORUN_DEFAULT_PROJECT_SLUG", "default-project")
    environment_name = os.getenv("DIMOORUN_DEFAULT_ENVIRONMENT", "local")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is None:
        tenant = Tenant(
            name=os.getenv("DIMOORUN_DEFAULT_TENANT_NAME", "Default Tenant"),
            slug=tenant_slug,
            status="active",
        )
        session.add(tenant)
        session.flush()
    project = session.scalar(
        select(Project).where(Project.tenant_id == tenant.id, Project.slug == project_slug)
    )
    if project is None:
        project = Project(
            tenant_id=tenant.id,
            name=os.getenv("DIMOORUN_DEFAULT_PROJECT_NAME", "Default Project"),
            slug=project_slug,
            status="active",
        )
        session.add(project)
        session.flush()
    existing_environment = session.scalar(
        select(Environment).where(
            Environment.tenant_id == tenant.id,
            Environment.project_id == project.id,
            Environment.environment == environment_name,
        )
    )
    if existing_environment is None:
        session.add(
            Environment(
                tenant_id=tenant.id,
                project_id=project.id,
                name=environment_name,
                environment=environment_name,
                status="active",
                metadata_json={"seeded": True},
            )
        )
    session.commit()
