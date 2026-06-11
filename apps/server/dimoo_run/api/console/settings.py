from typing import Any, Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dimoo_run.api.console.common import (
    AuditReasonHeader,
    AuthorizationHeader,
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    console_read_actor,
)
from dimoo_run.core.config import Settings
from dimoo_run.domain.models import Environment, Project, Tenant
from dimoo_run.persistence.database import create_session_factory
from dimoo_run.platform import (
    build_dangerous_action_preview,
    build_platform_settings_snapshot,
    build_provider_status_views,
    list_scoped_setting_views,
    write_scoped_setting,
)
from dimoo_run.platform.settings_snapshot import apply_dangerous_action

router = APIRouter(prefix="/v1/console/settings", tags=["console-settings"])


def _session_factory() -> sessionmaker[Session]:
    return create_session_factory(Settings.from_env().database.url)


@router.get("/platform", response_model=None)
def get_platform_settings_snapshot(
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
    _, tenant_id, project_id, environment = auth
    settings = Settings.from_env()
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        item = build_platform_settings_snapshot(
            session,
            settings=settings,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    return {"item": item, "request_id": x_request_id}


@router.get("/providers", response_model=None)
def get_provider_statuses(
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
    _, tenant_id, project_id, _ = auth
    settings = Settings.from_env()
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=x_environment or settings.runtime.environment,
        )
        items = build_provider_status_views(
            session,
            settings=settings,
            tenant_id=tenant_id,
            project_id=project_id,
        )
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.get("/scoped-defaults", response_model=None)
def get_scoped_defaults(
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
    _, tenant_id, project_id, environment = auth
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        items = list_scoped_setting_views(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.post("/scoped-defaults/{scope_kind}", response_model=None)
def update_scoped_defaults(
    scope_kind: Literal["organization", "project", "environment"],
    payload: dict[str, Any],
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
    x_audit_reason: AuditReasonHeader = None,
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
    actor, tenant_id, project_id, environment = auth
    if "*" not in actor.scopes and "admin:write" not in actor.scopes:
        return _permission_denied(x_request_id, "admin:write")
    settings = Settings.from_env()
    config = payload.get("config")
    if not isinstance(config, dict):
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "invalid_platform_settings_payload",
                "message": "A config object is required.",
                "request_id": x_request_id,
                "details": {"required_field": "config"},
            },
        )
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        try:
            item = write_scoped_setting(
                session,
                settings=settings,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
                scope_kind=scope_kind,
                config=dict(config),
                actor_id=actor.actor_id,
                request_id=x_request_id,
                audit_reason=x_audit_reason,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error_code": "platform_setting_read_only",
                    "message": str(exc),
                    "request_id": x_request_id,
                    "details": {"scope_kind": scope_kind},
                },
            )
    return {"item": item, "request_id": x_request_id}


@router.post("/danger/preflight", response_model=None)
def preflight_dangerous_action(
    payload: dict[str, Any],
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
    _, tenant_id, project_id, environment = auth
    action = str(payload.get("action") or "")
    settings = Settings.from_env()
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        try:
            item = build_dangerous_action_preview(
                session,
                settings=settings,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
                action=action,
            )
        except KeyError:
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "dangerous_action_not_found",
                    "message": "Dangerous configuration action was not found.",
                    "request_id": x_request_id,
                    "details": {"action": action},
                },
            )
    return {"item": item, "request_id": x_request_id}


@router.post("/danger/actions/{action}", response_model=None)
def run_dangerous_action(
    action: str,
    payload: dict[str, Any],
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
    x_audit_reason: AuditReasonHeader = None,
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
    actor, tenant_id, project_id, environment = auth
    if "*" not in actor.scopes and "admin:write" not in actor.scopes:
        return _permission_denied(x_request_id, "admin:write")
    settings = Settings.from_env()
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        try:
            item = apply_dangerous_action(
                session,
                settings=settings,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
                action=action,
                confirmation=str(payload.get("confirmation") or ""),
                rollback_notes=str(payload.get("rollback_notes") or ""),
                audit_reason=(x_audit_reason or str(payload.get("audit_reason") or "")).strip(),
                actor_id=actor.actor_id,
                request_id=x_request_id,
            )
        except KeyError:
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "dangerous_action_not_found",
                    "message": "Dangerous configuration action was not found.",
                    "request_id": x_request_id,
                    "details": {"action": action},
                },
            )
        except RuntimeError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "error_code": "dangerous_action_preflight_failed",
                    "message": str(exc),
                    "request_id": x_request_id,
                    "details": {"action": action},
                },
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={
                    "error_code": "dangerous_action_confirmation_required",
                    "message": str(exc),
                    "request_id": x_request_id,
                    "details": {"action": action},
                },
            )
    return {"item": item, "request_id": x_request_id}


def _permission_denied(request_id: str | None, required_scope: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "error_code": "permission_denied",
            "message": "Console write permission is required.",
            "request_id": request_id,
            "details": {"required_scope": required_scope},
        },
    )


def _ensure_scope_resources(
    session: Session,
    *,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> None:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(name="Default Tenant", slug=f"tenant-{tenant_id}", status="active")
        tenant.id = tenant_id
        session.add(tenant)
        session.flush()
    project = session.get(Project, project_id)
    if project is None:
        project = Project(
            tenant_id=tenant.id,
            name="Default Project",
            slug=f"project-{project_id}",
            status="active",
        )
        project.id = project_id
        session.add(project)
        session.flush()
    existing_environment = session.scalar(
        select(Environment).where(
            Environment.tenant_id == tenant.id,
            Environment.project_id == project.id,
            Environment.environment == environment,
        )
    )
    if existing_environment is None:
        session.add(
            Environment(
                tenant_id=tenant.id,
                project_id=project.id,
                name=environment,
                environment=environment,
                status="active",
                metadata_json={"seeded": True},
            )
        )
        session.flush()
