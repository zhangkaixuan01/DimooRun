from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select

from dimoo_run.api.admin.router import _serialize_api_key
from dimoo_run.api.console.common import (
    AuthorizationHeader,
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    console_read_actor,
)
from dimoo_run.api.dependencies import default_api_key_authenticator
from dimoo_run.domain.models import (
    APIKey,
    AuditLog,
    ConsoleOperator,
    ConsolePermission,
    ConsoleRole,
    ConsoleRolePermission,
    Deployment,
    PublishedSurface,
    Run,
)
from dimoo_run.identity.console import (
    console_operator_session_to_public,
    console_operator_to_public,
    default_console_identity_service,
)
from dimoo_run.persistence.database import create_session_factory

router = APIRouter(prefix="/v1/console/identity", tags=["console-identity"])


def _session_factory():
    from dimoo_run.core.config import Settings

    return create_session_factory(Settings.from_env().database.url)


@router.get("/role-matrix", response_model=None)
def get_role_matrix(
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
    with _session_factory()() as session:
        roles = []
        for role in session.scalars(
            select(ConsoleRole)
            .where(ConsoleRole.is_deleted.is_(False))
            .order_by(ConsoleRole.name)
        ):
            permissions = sorted(
                session.scalars(
                    select(ConsolePermission.code)
                    .join(
                        ConsoleRolePermission,
                        ConsoleRolePermission.permission_id == ConsolePermission.id,
                    )
                    .where(
                        ConsoleRolePermission.role_id == role.id,
                        ConsoleRolePermission.is_deleted.is_(False),
                        ConsolePermission.is_deleted.is_(False),
                    )
                )
            )
            roles.append(
                {
                    "id": role.id,
                    "name": role.name,
                    "description": role.description,
                    "status": role.status,
                    "permissions": permissions,
                }
            )
        permissions = [
            {
                "id": permission.id,
                "code": permission.code,
                "resource": permission.resource,
                "action": permission.action,
                "description": permission.description,
                "status": permission.status,
            }
            for permission in session.scalars(
                select(ConsolePermission)
                .where(ConsolePermission.is_deleted.is_(False))
                .order_by(ConsolePermission.code)
            )
        ]
    return {"items": roles, "permissions": permissions, "request_id": x_request_id}


@router.get("/operators/{operator_id}", response_model=None)
def get_operator_access_detail(
    operator_id: int,
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
    with _session_factory()() as session:
        model = session.get(ConsoleOperator, operator_id)
        if model is None or model.is_deleted:
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "operator_not_found",
                    "message": "Operator was not found.",
                    "request_id": x_request_id,
                    "details": {"operator_id": operator_id},
                },
            )
        operator = next(
            item
            for item in default_console_identity_service().list_operators()
            if item.id == operator_id
        )
        sessions = [
            console_operator_session_to_public(row)
            for row in default_console_identity_service().list_operator_sessions(operator_id) or []
        ]
        keys = [
            {
                "id": key.id,
                "name": key.name,
                "owner_id": key.owner_id,
                "status": key.status,
                "scopes": sorted(key.scopes_json or []),
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            }
            for key in session.scalars(
                select(APIKey)
                .where(APIKey.created_by == str(operator_id), APIKey.is_deleted.is_(False))
                .order_by(APIKey.created_at.desc())
            )
        ]
        recent_audit = [
            {
                "id": item.id,
                "action": item.action,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
                "result": item.result,
                "request_id": item.request_id,
                "created_at": item.created_at.isoformat(),
                "metadata": item.metadata_json,
            }
            for item in session.scalars(
                select(AuditLog)
                .where(AuditLog.actor_id == str(operator_id), AuditLog.is_deleted.is_(False))
                .order_by(AuditLog.created_at.desc())
                .limit(10)
            )
        ]
    return {
        "item": {
            **console_operator_to_public(operator),
            "active_sessions": sessions,
            "api_keys_created": keys,
            "recent_audit_actions": recent_audit,
            "disable_impact": {
                "active_session_count": len(
                    [item for item in sessions if item["status"] == "active"]
                ),
                "api_keys_created_count": len(keys),
            },
        },
        "request_id": x_request_id,
    }


@router.get("/service-accounts/{service_account_id}", response_model=None)
def get_service_account_detail(
    service_account_id: int,
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
    authenticator = default_api_key_authenticator()
    try:
        account = authenticator.service_accounts.get(service_account_id)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "service_account_not_found",
                "message": "Service account was not found.",
                "request_id": x_request_id,
                "details": {"service_account_id": service_account_id},
            },
        )
    with _session_factory()() as session:
        dependencies = []
        for deployment in session.scalars(
            select(Deployment)
            .join(Run, Run.deployment_id == Deployment.id)
            .where(
                Run.service_account_id == service_account_id,
                Deployment.is_deleted.is_(False),
            )
            .distinct()
        ):
            surfaces = [
                {
                    "id": surface.id,
                    "name": str(surface.metadata_json.get("name") or f"surface-{surface.id}"),
                    "status": surface.status,
                }
                for surface in session.scalars(
                    select(PublishedSurface)
                    .where(
                        PublishedSurface.deployment_id == deployment.id,
                        PublishedSurface.is_deleted.is_(False),
                    )
                    .order_by(PublishedSurface.created_at.desc())
                )
            ]
            dependencies.append(
                {
                    "deployment_id": deployment.id,
                    "agent_id": deployment.agent_id,
                    "environment": deployment.environment,
                    "published_surfaces": surfaces,
                }
            )
    keys = [
        {
            **_serialize_api_key(key),
            "scope_diff": {
                "added": sorted(set(key.scopes) - set(account.permissions)),
                "removed": sorted(set(account.permissions) - set(key.scopes)),
                "unchanged": sorted(set(account.permissions) & set(key.scopes)),
            },
        }
        for key in authenticator.list_keys(
            owner_type="service_account",
            owner_id=service_account_id,
        )
    ]
    return {
        "item": {
            "id": account.id,
            "tenant_id": account.tenant_id,
            "project_id": account.project_id,
            "name": account.name,
            "permissions": sorted(account.permissions),
            "status": account.status,
            "created_by": account.created_by,
            "created_at": account.created_at.isoformat(),
            "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
            "api_keys": keys,
            "dependent_deployments": dependencies,
        },
        "request_id": x_request_id,
    }
