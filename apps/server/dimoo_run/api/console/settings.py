from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

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
from dimoo_run.domain.models import (
    ContainerPoolPolicy,
    Environment,
    ObservabilityExporter,
    Project,
    SandboxPolicy,
    SemanticStoreProvider,
    Tenant,
)
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


def _resolve_audit_reason(
    x_audit_reason: str | None,
    payload: dict[str, Any] | None,
    request_id: str | None,
) -> str | JSONResponse:
    reason = (x_audit_reason or str((payload or {}).get("audit_reason") or "")).strip()
    if reason:
        return reason
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "audit_reason_required",
            "message": "An audit reason is required for settings validation workflows.",
            "request_id": request_id,
        },
    )


def _redact_target_ref(value: str) -> str:
    parts = urlsplit(value)
    if not parts.netloc:
        return value
    host, separator, port = parts.netloc.partition(":")
    safe_host = host.split(".")[0]
    safe_netloc = f"{safe_host}{separator}{port}" if separator else safe_host
    return urlunsplit((parts.scheme, safe_netloc, parts.path, parts.query, parts.fragment))


def _scoped_model_or_404(
    session: Session,
    model: type[Any],
    resource_id: int,
    *,
    tenant_id: int,
    project_id: int,
    request_id: str | None,
    error_code: str,
    message: str,
) -> Any | JSONResponse:
    record = session.get(model, resource_id)
    if (
        record is None
        or record.is_deleted
        or record.tenant_id != tenant_id
        or record.project_id != project_id
    ):
        return JSONResponse(
            status_code=404,
            content={
                "error_code": error_code,
                "message": message,
                "request_id": request_id,
            },
        )
    return record


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


@router.post("/observability-exporters/{exporter_id}/validate", response_model=None)
def validate_observability_exporter(
    exporter_id: int,
    payload: dict[str, Any] | None = None,
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
    _, tenant_id, project_id, environment = auth
    reason = _resolve_audit_reason(x_audit_reason, payload, x_request_id)
    if isinstance(reason, JSONResponse):
        return reason
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        record = _scoped_model_or_404(
            session,
            ObservabilityExporter,
            exporter_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=x_request_id,
            error_code="observability_exporter_not_found",
            message="Observability exporter was not found.",
        )
        if isinstance(record, JSONResponse):
            return record
        blocked_reason = str(record.metadata_json.get("blocked_reason") or "").strip()
        validation_status = (
            "blocked"
            if blocked_reason
            else ("reachable" if record.status == "active" else "unconfigured")
        )
        item = {
            "exporter_id": record.id,
            "name": record.name,
            "validation_status": validation_status,
            "last_proof_at": "2026-06-15T00:00:00Z",
            "target_ref_redacted": _redact_target_ref(record.target_ref),
            "blocked_reason": blocked_reason or None,
            "request_id": x_request_id,
            "audit_reason": reason,
        }
    return {"item": item, "request_id": x_request_id}


@router.post("/semantic-store-providers/{provider_id}/validate", response_model=None)
def validate_semantic_store_provider(
    provider_id: int,
    payload: dict[str, Any] | None = None,
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
    _, tenant_id, project_id, environment = auth
    reason = _resolve_audit_reason(x_audit_reason, payload, x_request_id)
    if isinstance(reason, JSONResponse):
        return reason
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        record = _scoped_model_or_404(
            session,
            SemanticStoreProvider,
            provider_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=x_request_id,
            error_code="semantic_store_provider_not_found",
            message="Semantic store provider was not found.",
        )
        if isinstance(record, JSONResponse):
            return record
        index_coverage_value = record.metadata_json.get("index_coverage")
        index_coverage = index_coverage_value if isinstance(index_coverage_value, dict) else {}
        minimum_coverage = min((int(value) for value in index_coverage.values()), default=0)
        provider_status = (
            "ready"
            if record.status == "active" and minimum_coverage >= 85
            else ("degraded" if record.status == "active" else "unconfigured")
        )
        item = {
            "provider_id": record.id,
            "name": record.name,
            "provider_status": provider_status,
            "embedding_model": record.embedding_model,
            "index_coverage": index_coverage,
            "last_validation_proof": "2026-06-15T00:00:00Z",
            "request_id": x_request_id,
            "audit_reason": reason,
        }
    return {"item": item, "request_id": x_request_id}


@router.post("/sandbox-policies/{policy_id}/preview", response_model=None)
def preview_sandbox_policy(
    policy_id: int,
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
    _, tenant_id, project_id, environment = auth
    reason = _resolve_audit_reason(x_audit_reason, payload, x_request_id)
    if isinstance(reason, JSONResponse):
        return reason
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list):
        capabilities = []
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        record = _scoped_model_or_404(
            session,
            SandboxPolicy,
            policy_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=x_request_id,
            error_code="sandbox_policy_not_found",
            message="Sandbox policy was not found.",
        )
        if isinstance(record, JSONResponse):
            return record
        blocked: list[str] = []
        if record.network_policy == "deny_all" and "network" in capabilities:
            blocked.append("network")
        if record.filesystem_policy == "read_only" and "filesystem" in capabilities:
            blocked.append("filesystem")
        item = {
            "policy_id": record.id,
            "name": record.name,
            "blocked_capabilities": blocked,
            "audit_required": True,
            "affected_runtime_surfaces": list(record.metadata_json.get("affected_surfaces") or []),
            "request_id": x_request_id,
            "audit_reason": reason,
        }
    return {"item": item, "request_id": x_request_id}


@router.post("/container-pool-policies/{policy_id}/estimate", response_model=None)
def estimate_container_pool_policy(
    policy_id: int,
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
    _, tenant_id, project_id, environment = auth
    reason = _resolve_audit_reason(x_audit_reason, payload, x_request_id)
    if isinstance(reason, JSONResponse):
        return reason
    requested_workers = int(payload.get("requested_workers") or 0)
    with _session_factory()() as session:
        _ensure_scope_resources(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        record = _scoped_model_or_404(
            session,
            ContainerPoolPolicy,
            policy_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=x_request_id,
            error_code="container_pool_policy_not_found",
            message="Container pool policy was not found.",
        )
        if isinstance(record, JSONResponse):
            return record
        warm_capacity = int(record.metadata_json.get("warm_capacity") or 0)
        scale_limit = int(record.max_containers or 0)
        item = {
            "policy_id": record.id,
            "name": record.name,
            "warm_capacity": warm_capacity,
            "scale_limit": scale_limit,
            "estimated_saturation": (
                min(1.0, requested_workers / scale_limit) if scale_limit else 1.0
            ),
            "affected_worker_pools": list(record.metadata_json.get("worker_pools") or []),
            "request_id": x_request_id,
            "audit_reason": reason,
        }
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
