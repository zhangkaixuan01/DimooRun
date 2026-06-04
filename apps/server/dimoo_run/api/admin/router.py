import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Response
from sqlalchemy import Boolean, Float, Integer, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import dimoo_run.domain.models as domain_models
from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    default_api_key_authenticator,
    enforce_console_actor,
)
from dimoo_run.core.config import Settings
from dimoo_run.domain.models import (
    AuditLog,
    ConsolePermission,
    ConsoleRole,
    ConsoleRolePermission,
    Environment,
    Project,
    Tenant,
)
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.persistence.repositories import (
    AuditLogRepository,
    EnvironmentRepository,
    ProjectRepository,
    TenantRepository,
)
from dimoo_run.security.api_keys import APIKeyError, APIKeyScopeError, AuthenticatedActor

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]

_AUDIT_FIELD_NAMES = {
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "is_deleted",
    "deleted_at",
    "deleted_by",
}


@dataclass(frozen=True)
class AdminDbCollectionSpec:
    model: type[Any]
    defaults: dict[str, Any] = field(default_factory=dict)
    required_fields: tuple[str, ...] = ()
    parent_refs: dict[str, type[Any]] = field(default_factory=dict)
    expose_name_from_metadata: bool = False
    environment_in_metadata: bool = True

_COLLECTIONS: dict[str, dict[int, dict[str, Any]]] = {
    "policies": {},
    "tenants": {},
    "projects": {},
    "environments": {},
    "artifacts": {},
    "human_tasks": {},
    "model_gateways": {},
    "published_surfaces": {},
    "ingress_routes": {},
    "catalog_items": {},
    "datasets": {},
    "dataset_items": {},
    "experiments": {},
    "replay_jobs": {},
    "schedules": {},
    "batch_runs": {},
    "notification_channels": {},
    "alert_rules": {},
    "backup_plans": {},
    "restore_jobs": {},
    "webhook_subscriptions": {},
    "incidents": {},
    "users": {},
    "roles": {},
    "permissions": {},
    "secrets": {},
    "tools": {},
    "prompt_assets": {},
    "config_assets": {},
    "template_assets": {},
    "audit_logs": {},
    "evaluation_results": {},
    "feedback": {},
    "semantic_store_providers": {},
    "observability_exporters": {},
    "sandbox_policies": {},
    "container_pool_policies": {},
}
_COLLECTION_SEQUENCES: dict[str, int] = {collection: 0 for collection in _COLLECTIONS}
_SLUG_SEQUENCES: dict[str, int] = {}

_DB_COLLECTIONS: dict[str, AdminDbCollectionSpec] = {
    "policies": AdminDbCollectionSpec(
        domain_models.Policy,
        defaults={
            "type": "admin",
            "resource_type": "generic",
            "action": "manage",
            "decision": "allow",
            "priority": 100,
            "condition_json": {},
            "metadata_json": {},
        },
        expose_name_from_metadata=True,
    ),
    "model_gateways": AdminDbCollectionSpec(
        domain_models.ModelGateway,
        defaults={
            "provider_type": "openai",
            "base_url": "https://api.openai.com/v1",
            "credential_ref": "secret:unset",
            "metadata_json": {},
        },
    ),
    "catalog_items": AdminDbCollectionSpec(
        domain_models.CatalogItem,
        defaults={
            "type": "tool",
            "provider": "local",
            "version": "1.0.0",
            "schema_json": {},
            "capabilities_json": {},
            "risk_level": "medium",
            "required_secrets_json": [],
            "required_permissions_json": [],
            "runtime_requirements_json": {},
        },
    ),
    "published_surfaces": AdminDbCollectionSpec(
        domain_models.PublishedSurface,
        defaults={"type": "http", "metadata_json": {}},
        required_fields=("deployment_id",),
        parent_refs={"deployment_id": domain_models.Deployment},
        expose_name_from_metadata=True,
        environment_in_metadata=False,
    ),
    "ingress_routes": AdminDbCollectionSpec(
        domain_models.IngressRoute,
        defaults={"auth_mode": "api_key", "access_log_enabled": True, "metadata_json": {}},
        required_fields=("surface_id", "path"),
        parent_refs={"surface_id": domain_models.PublishedSurface},
        expose_name_from_metadata=True,
        environment_in_metadata=False,
    ),
    "artifacts": AdminDbCollectionSpec(
        domain_models.Artifact,
        defaults={
            "artifact_type": "file",
            "mime_type": "application/octet-stream",
            "size_bytes": 0,
            "storage_uri": "artifact:unset",
            "checksum": "unset",
            "visibility_level": "internal",
            "metadata_json": {},
        },
        parent_refs={"run_id": domain_models.Run},
        expose_name_from_metadata=True,
    ),
    "human_tasks": AdminDbCollectionSpec(
        domain_models.HumanTask,
        defaults={"type": "approval", "status": "pending"},
        expose_name_from_metadata=True,
    ),
    "datasets": AdminDbCollectionSpec(
        domain_models.Dataset,
        defaults={"source": "manual", "schema_json": {}, "visibility_level": "internal"},
    ),
    "dataset_items": AdminDbCollectionSpec(
        domain_models.DatasetItem,
        defaults={"metadata_json": {}},
        required_fields=("dataset_id", "input_ref"),
        parent_refs={"dataset_id": domain_models.Dataset, "source_run_id": domain_models.Run},
        expose_name_from_metadata=True,
    ),
    "experiments": AdminDbCollectionSpec(
        domain_models.Experiment,
        defaults={"evaluator_config_json": {}, "status": "draft"},
        required_fields=("name", "agent_id", "candidate_agent_version_id", "dataset_id"),
        parent_refs={
            "agent_id": domain_models.Agent,
            "baseline_agent_version_id": domain_models.AgentVersion,
            "candidate_agent_version_id": domain_models.AgentVersion,
            "dataset_id": domain_models.Dataset,
        },
    ),
    "evaluation_results": AdminDbCollectionSpec(
        domain_models.EvaluationResult,
        defaults={"metadata_json": {}},
        required_fields=("experiment_run_id", "evaluator_name", "score", "passed"),
        parent_refs={"experiment_run_id": domain_models.ExperimentRun},
        expose_name_from_metadata=True,
    ),
    "feedback": AdminDbCollectionSpec(
        domain_models.Feedback,
        defaults={"source": "console", "metadata_json": {}},
        required_fields=("run_id",),
        parent_refs={"run_id": domain_models.Run},
        expose_name_from_metadata=True,
    ),
    "tools": AdminDbCollectionSpec(
        domain_models.Tool,
        defaults={"schema_json": {}, "risk_level": "read"},
    ),
    "secrets": AdminDbCollectionSpec(
        domain_models.Secret,
        defaults={"provider": "external", "scope": "project"},
    ),
    "prompt_assets": AdminDbCollectionSpec(
        domain_models.PromptAsset,
        defaults={
            "version": "1.0.0",
            "content_ref": "inline:unset",
            "variables_schema_json": {},
            "metadata_json": {},
        },
    ),
    "config_assets": AdminDbCollectionSpec(
        domain_models.ConfigAsset,
        defaults={
            "version": "1.0.0",
            "schema_json": {},
            "content_ref": "inline:unset",
            "metadata_json": {},
        },
        environment_in_metadata=False,
    ),
    "template_assets": AdminDbCollectionSpec(
        domain_models.Template,
        defaults={
            "type": "template",
            "version": "1.0.0",
            "content_ref": "inline:unset",
            "schema_json": {},
            "metadata_json": {},
        },
    ),
    "semantic_store_providers": AdminDbCollectionSpec(
        domain_models.SemanticStoreProvider,
        defaults={
            "embedding_model": "text-embedding-3-small",
            "connection_ref": "secret:unset",
            "metadata_json": {},
        },
    ),
    "observability_exporters": AdminDbCollectionSpec(
        domain_models.ObservabilityExporter,
        defaults={"exporter_type": "otlp", "target_ref": "unset", "metadata_json": {}},
    ),
    "sandbox_policies": AdminDbCollectionSpec(
        domain_models.SandboxPolicy,
        defaults={
            "isolation_level": "process",
            "network_policy": "deny_all",
            "filesystem_policy": "read_only",
            "metadata_json": {},
        },
    ),
    "container_pool_policies": AdminDbCollectionSpec(
        domain_models.ContainerPoolPolicy,
        defaults={
            "max_containers": 10,
            "cpu_limit": "1000m",
            "memory_limit": "1Gi",
            "idle_timeout_seconds": 300,
            "metadata_json": {},
        },
    ),
    "notification_channels": AdminDbCollectionSpec(
        domain_models.NotificationChannel,
        defaults={"type": "webhook", "target_ref": "unset", "metadata_json": {}},
    ),
    "alert_rules": AdminDbCollectionSpec(
        domain_models.AlertRule,
        defaults={"signal": "runtime.error_rate", "threshold": 1.0, "metadata_json": {}},
        required_fields=("name", "channel_id"),
        parent_refs={"channel_id": domain_models.NotificationChannel},
    ),
    "webhook_subscriptions": AdminDbCollectionSpec(
        domain_models.WebhookSubscription,
        defaults={
            "event_types_json": [],
            "target_url": "https://example.invalid/webhook",
            "secret_ref": "secret:unset",
            "retry_policy_json": {},
            "permissions_json": [],
            "rate_limit_json": {},
            "metadata_json": {},
        },
    ),
    "backup_plans": AdminDbCollectionSpec(
        domain_models.BackupPlan,
        defaults={
            "scope": "project",
            "targets_json": [],
            "schedule": "0 0 * * *",
            "retention_days": 7,
            "storage_ref": "object-store:default",
            "metadata_json": {},
        },
    ),
    "restore_jobs": AdminDbCollectionSpec(
        domain_models.RestoreJob,
        defaults={"backup_ref": "backup:unset", "restore_scope": "project", "metadata_json": {}},
        expose_name_from_metadata=True,
    ),
    "incidents": AdminDbCollectionSpec(
        domain_models.IncidentEvent,
        defaults={
            "signal": "manual",
            "severity": "info",
            "source_ref": "console",
            "value": 0.0,
            "metadata_json": {},
        },
        expose_name_from_metadata=True,
    ),
    "schedules": AdminDbCollectionSpec(
        domain_models.ScheduledRuns,
        defaults={"metadata_json": {}},
        expose_name_from_metadata=True,
    ),
    "batch_runs": AdminDbCollectionSpec(
        domain_models.BatchRuns,
        defaults={"metadata_json": {}},
        expose_name_from_metadata=True,
    ),
    "replay_jobs": AdminDbCollectionSpec(
        domain_models.ReplayJob,
        defaults={"override_config_json": {}, "metadata_json": {}},
        required_fields=("source_run_id", "candidate_agent_version_id"),
        parent_refs={
            "source_run_id": domain_models.Run,
            "source_agent_version_id": domain_models.AgentVersion,
            "candidate_agent_version_id": domain_models.AgentVersion,
            "replay_run_id": domain_models.Run,
        },
        expose_name_from_metadata=True,
    ),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _next_collection_id(collection: str) -> int:
    _COLLECTION_SEQUENCES[collection] = _COLLECTION_SEQUENCES.get(collection, 0) + 1
    return _COLLECTION_SEQUENCES[collection]


def _default_slug(collection: str) -> str:
    _SLUG_SEQUENCES[collection] = _SLUG_SEQUENCES.get(collection, 0) + 1
    return f"{collection.rstrip('s')}-{_SLUG_SEQUENCES[collection]}"


def _default_scope() -> tuple[str, str, str]:
    return (
        os.getenv("DIMOORUN_DEFAULT_TENANT_SLUG", "default-tenant"),
        os.getenv("DIMOORUN_DEFAULT_PROJECT_SLUG", "default-project"),
        os.getenv("DIMOORUN_DEFAULT_ENVIRONMENT", "local"),
    )


def _actor_can_access_target(
    actor: AuthenticatedActor,
    tenant_id: int,
    project_id: int | None,
) -> bool:
    if "*" in actor.scopes:
        return True
    if actor.tenant_id != tenant_id:
        return False
    if (
        actor.project_id is not None
        and project_id is not None
        and actor.project_id != project_id
    ):
        return False
    return True


def _scope_denied(
    request_id: str | None,
    tenant_id: int,
    project_id: int | None,
) -> dict[str, Any]:
    return {
        "error_code": "scope_not_allowed",
        "message": "The target tenant or project is not allowed for this operator.",
        "request_id": request_id,
        "details": {"tenant_id": tenant_id, "project_id": project_id},
    }


def _resource_not_found(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    response.status_code = 404
    return {
        "error_code": "resource_not_found",
        "message": "Resource was not found.",
        "request_id": request_id,
        "details": {"collection": collection, "id": resource_id},
    }


def _resource_in_scope(
    resource: dict[str, Any],
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> bool:
    if tenant_id is not None and resource.get("tenant_id") != tenant_id:
        return False
    if project_id is not None and resource.get("project_id") != project_id:
        return False
    if environment is not None and resource.get("environment") not in {None, environment}:
        return False
    return True


def _append_identity_audit(
    actor: AuthenticatedActor,
    *,
    action: str,
    resource_type: str,
    resource_id: int | None,
    request_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session = _open_scope_session()
    try:
        AuditLogRepository(session).append(
            tenant_id=actor.tenant_id,
            project_id=actor.project_id,
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result="allow",
            request_id=request_id,
            metadata=metadata or {},
        )
        session.commit()
    finally:
        session.close()


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


@lru_cache(maxsize=4)
def _scope_session_factory(database_url: str) -> sessionmaker[Session]:
    return create_session_factory(database_url)


def _open_scope_session() -> Session:
    settings = Settings.from_env()
    session_factory = _scope_session_factory(settings.database.url)
    session = session_factory()
    if settings.runtime.mode == "dev":
        engine = session.get_bind()
        Base.metadata.create_all(engine)
    return session


def _seed_scope_resources(session: Session) -> None:
    tenant_slug, project_slug, environment = _default_scope()
    tenant = _tenant_by_slug(session, tenant_slug)
    if tenant is None:
        tenant = Tenant(
            name=os.getenv("DIMOORUN_DEFAULT_TENANT_NAME", "Default Tenant"),
            slug=tenant_slug,
            status="active",
        )
        session.add(tenant)
        session.flush()
    project = _project_by_slug(session, project_slug, tenant.id)
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
    session.commit()


def _tenant_by_id(session: Session, tenant_id: int | None) -> Tenant | None:
    if tenant_id is None:
        return None
    return session.get(Tenant, tenant_id)


def _project_by_id(
    session: Session, project_id: int | None, tenant_id: int | None = None
) -> Project | None:
    if project_id is None:
        return None
    project = session.get(Project, project_id)
    if tenant_id is not None:
        return project if project is not None and project.tenant_id == tenant_id else None
    return project


def _tenant_by_slug(session: Session, slug: str) -> Tenant | None:
    return session.scalar(select(Tenant).where(Tenant.slug == slug))


def _project_by_slug(session: Session, slug: str, tenant_id: int) -> Project | None:
    return session.scalar(
        select(Project).where(Project.tenant_id == tenant_id, Project.slug == slug)
    )


def _resolve_scope_ids(
    session: Session, tenant_id: int | None, project_id: int | None
) -> tuple[int | None, int | None]:
    tenant = _tenant_by_id(session, tenant_id)
    project = _project_by_id(session, project_id, tenant.id if tenant is not None else None)
    return (
        tenant.id if tenant is not None else tenant_id,
        project.id if project is not None else project_id,
    )


def _scope_not_found(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    response.status_code = 404
    return {
        "error_code": "resource_not_found",
        "message": "Resource was not found.",
        "request_id": request_id,
        "details": {"collection": collection, "id": resource_id},
    }


def _scope_conflict(
    collection: str,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    response.status_code = 409
    return {
        "error_code": "resource_conflict",
        "message": "Resource violates a unique scope constraint.",
        "request_id": request_id,
        "details": {"collection": collection},
    }


def _validation_error(
    collection: str,
    request_id: str | None,
    response: Response,
    details: dict[str, Any],
) -> dict[str, Any]:
    response.status_code = 400
    return {
        "error_code": "invalid_admin_resource",
        "message": "Admin resource payload is invalid.",
        "request_id": request_id,
        "details": {"collection": collection, **details},
    }


def _machine_identity_not_found(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    return _scope_not_found(collection, resource_id, request_id, response)


def _serialize_scope_resource(resource: Tenant | Project | Environment) -> dict[str, Any]:
    item = {
        "id": resource.id,
        "name": getattr(resource, "name", None),
        "status": getattr(resource, "status", "active"),
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
    }
    if isinstance(resource, Tenant):
        item["slug"] = resource.slug
    if isinstance(resource, Project):
        item["tenant_id"] = resource.tenant_id
        item["slug"] = resource.slug
    if isinstance(resource, Environment):
        item["tenant_id"] = resource.tenant_id
        item["project_id"] = resource.project_id
        item["environment"] = resource.environment
        item["metadata"] = resource.metadata_json
    return item


def _list_scope_collection(
    collection: str,
    request_id: str | None,
    tenant_id: int | None,
    project_id: int | None,
) -> dict[str, Any]:
    session = _open_scope_session()
    try:
        _seed_scope_resources(session)
        items: Sequence[Tenant | Project | Environment]
        if collection == "tenants":
            items = TenantRepository(session).list_active()
        elif collection == "projects":
            resolved_tenant_id, _ = _resolve_scope_ids(session, tenant_id, project_id)
            items = (
                ProjectRepository(session).list_by_tenant(resolved_tenant_id)
                if resolved_tenant_id is not None
                else []
            )
        else:
            resolved_tenant_id, resolved_project_id = _resolve_scope_ids(
                session, tenant_id, project_id
            )
            items = EnvironmentRepository(session).list_by_project(
                resolved_tenant_id,
                resolved_project_id,
            ) if resolved_tenant_id is not None and resolved_project_id is not None else []
        serialized = [_serialize_scope_resource(item) for item in items]
        return {"items": serialized, "count": len(serialized), "request_id": request_id}
    finally:
        session.close()


def _create_scope_resource(
    collection: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
    actor: AuthenticatedActor,
) -> dict[str, Any]:
    session = _open_scope_session()
    data = payload or {}
    try:
        _seed_scope_resources(session)
        if collection == "tenants":
            slug = str(data.get("slug") or _default_slug(collection))
            if "*" not in actor.scopes:
                response.status_code = 403
                return {
                    "error_code": "permission_denied",
                    "message": "Global scope is required to create a tenant.",
                    "request_id": request_id,
                    "details": {},
                }
            resource: Tenant | Project | Environment = Tenant(
                name=str(data.get("name") or "Tenant"),
                slug=slug,
                status=str(data.get("status") or "active"),
            )
        elif collection == "projects":
            target_tenant_id = int(data.get("tenant_id") or actor.tenant_id)
            if not _actor_can_access_target(actor, target_tenant_id, None):
                response.status_code = 403
                return _scope_denied(request_id, target_tenant_id, None)
            tenant = _tenant_by_id(session, target_tenant_id)
            if tenant is None:
                response.status_code = 404
                return _scope_not_found("tenants", target_tenant_id, request_id, response)
            resource = Project(
                tenant_id=tenant.id,
                name=str(data.get("name") or "Project"),
                slug=str(data.get("slug") or _default_slug(collection)),
                status=str(data.get("status") or "active"),
            )
        else:
            target_tenant_id = int(data.get("tenant_id") or actor.tenant_id)
            raw_project_id = data.get("project_id") or actor.project_id
            target_project_id = int(raw_project_id) if raw_project_id is not None else None
            if not target_project_id:
                response.status_code = 400
                return {
                    "error_code": "project_scope_required",
                    "message": "A project scope is required to create an environment.",
                    "request_id": request_id,
                    "details": {},
                }
            if not _actor_can_access_target(actor, target_tenant_id, target_project_id):
                response.status_code = 403
                return _scope_denied(request_id, target_tenant_id, target_project_id)
            tenant = _tenant_by_id(session, target_tenant_id)
            project = _project_by_id(
                session, target_project_id, tenant.id if tenant is not None else None
            )
            if tenant is None or project is None:
                response.status_code = 404
                return _scope_not_found("projects", target_project_id, request_id, response)
            environment = str(data.get("environment") or _default_slug(collection))
            resource = Environment(
                tenant_id=tenant.id,
                project_id=project.id,
                name=str(data.get("name") or environment),
                environment=environment,
                status=str(data.get("status") or "active"),
                metadata_json=dict(data.get("metadata") or {}),
            )
        session.add(resource)
        session.flush()
        session.commit()
        _append_identity_audit(
            actor,
            action=f"identity.{collection}.create",
            resource_type=collection.rstrip("s"),
            resource_id=resource.id,
            request_id=request_id,
        )
        response.status_code = 201
        return {"item": _serialize_scope_resource(resource), "request_id": request_id}
    except IntegrityError:
        session.rollback()
        return _scope_conflict(collection, request_id, response)
    finally:
        session.close()


def _update_scope_resource(
    collection: str,
    resource_id: int,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    session = _open_scope_session()
    try:
        _seed_scope_resources(session)
        resource: Tenant | Project | Environment | None
        if collection == "tenants":
            resource = session.get(Tenant, resource_id)
        elif collection == "projects":
            resource = session.get(Project, resource_id)
        else:
            resource = session.get(Environment, resource_id)
        if resource is None or resource.is_deleted:
            return _scope_not_found(collection, resource_id, request_id, response)
        for key, value in (payload or {}).items():
            if key == "metadata" and isinstance(resource, Environment):
                resource.metadata_json = dict(value or {})
            elif key != "id" and hasattr(resource, key):
                setattr(resource, key, value)
        session.commit()
        return {"item": _serialize_scope_resource(resource), "request_id": request_id}
    except IntegrityError:
        session.rollback()
        return _scope_conflict(collection, request_id, response)
    finally:
        session.close()


def _delete_scope_resource(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    session = _open_scope_session()
    try:
        _seed_scope_resources(session)
        resource: Tenant | Project | Environment | None
        if collection == "tenants":
            resource = session.get(Tenant, resource_id)
        elif collection == "projects":
            resource = session.get(Project, resource_id)
        else:
            resource = session.get(Environment, resource_id)
        if resource is None or resource.is_deleted:
            return _scope_not_found(collection, resource_id, request_id, response)
        resource.status = "deleted"
        resource.is_deleted = True
        resource.deleted_at = datetime.now(UTC)
        session.commit()
        return {"item": _serialize_scope_resource(resource), "request_id": request_id}
    finally:
        session.close()


def _serialize_console_identity_resource(
    session: Session,
    resource: ConsoleRole | ConsolePermission,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": resource.id,
        "status": resource.status,
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
    }
    if isinstance(resource, ConsoleRole):
        item["name"] = resource.name
        item["description"] = resource.description
        permissions = session.scalars(
            select(ConsolePermission.code)
            .join(
                ConsoleRolePermission,
                ConsoleRolePermission.permission_id == ConsolePermission.id,
            )
            .where(
                ConsoleRolePermission.role_id == resource.id,
                ConsoleRolePermission.is_deleted.is_(False),
                ConsolePermission.is_deleted.is_(False),
            )
            .order_by(ConsolePermission.code)
        )
        item["permissions"] = list(permissions)
    else:
        item["name"] = resource.code
        item["code"] = resource.code
        item["resource"] = resource.resource
        item["action"] = resource.action
        item["description"] = resource.description
    return item


def _list_console_identity_collection(
    collection: str,
    request_id: str | None,
) -> dict[str, Any]:
    session = _open_scope_session()
    try:
        if collection == "roles":
            items = list(
                session.scalars(
                    select(ConsoleRole)
                    .where(ConsoleRole.is_deleted.is_(False))
                    .order_by(ConsoleRole.name)
                )
            )
        else:
            items = list(
                session.scalars(
                    select(ConsolePermission)
                    .where(ConsolePermission.is_deleted.is_(False))
                    .order_by(ConsolePermission.code)
                )
            )
        serialized = [_serialize_console_identity_resource(session, item) for item in items]
        return {"items": serialized, "count": len(serialized), "request_id": request_id}
    finally:
        session.close()


def _serialize_audit_log(record: AuditLog) -> dict[str, Any]:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "project_id": record.project_id,
        "actor_id": record.actor_id,
        "actor_type": record.actor_type,
        "action": record.action,
        "resource_type": record.resource_type,
        "resource_id": record.resource_id,
        "result": record.result,
        "request_id": record.request_id,
        "metadata": record.metadata_json,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _list_audit_logs(
    request_id: str | None,
    tenant_id: int | None = None,
    project_id: int | None = None,
) -> dict[str, Any]:
    session = _open_scope_session()
    try:
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)
        if project_id is not None:
            query = query.where(AuditLog.project_id == project_id)
        items = list(session.scalars(query))
        serialized = [_serialize_audit_log(item) for item in items]
        return {"items": serialized, "count": len(serialized), "request_id": request_id}
    finally:
        session.close()


def _create_console_identity_resource(
    collection: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    session = _open_scope_session()
    data = payload or {}
    try:
        if collection == "roles":
            resource: ConsoleRole | ConsolePermission = ConsoleRole(
                name=str(data.get("name") or data.get("code") or "role"),
                description=(
                    str(data["description"]) if data.get("description") is not None else None
                ),
                status=str(data.get("status") or "active"),
            )
        else:
            code = str(data.get("code") or data.get("name") or "permission:use")
            resource_name, action = _permission_parts(code)
            resource = ConsolePermission(
                code=code,
                resource=str(data.get("resource") or resource_name),
                action=str(data.get("action") or action),
                description=(
                    str(data["description"]) if data.get("description") is not None else None
                ),
                status=str(data.get("status") or "active"),
            )
        session.add(resource)
        session.flush()
        session.commit()
        response.status_code = 201
        return {
            "item": _serialize_console_identity_resource(session, resource),
            "request_id": request_id,
        }
    except IntegrityError:
        session.rollback()
        return _scope_conflict(collection, request_id, response)
    finally:
        session.close()


def _update_console_identity_resource(
    collection: str,
    resource_id: int,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    session = _open_scope_session()
    try:
        resource: ConsoleRole | ConsolePermission | None
        if collection == "roles":
            resource = session.get(ConsoleRole, resource_id)
        else:
            resource = session.get(ConsolePermission, resource_id)
        if resource is None or resource.is_deleted:
            return _scope_not_found(collection, resource_id, request_id, response)
        for key, value in (payload or {}).items():
            if key == "permissions" and isinstance(resource, ConsoleRole):
                session.query(ConsoleRolePermission).filter(
                    ConsoleRolePermission.role_id == resource.id
                ).delete()
                for code in list(value or []):
                    permission = session.scalar(
                        select(ConsolePermission).where(ConsolePermission.code == str(code))
                    )
                    if permission is not None:
                        session.add(
                            ConsoleRolePermission(
                                role_id=resource.id,
                                permission_id=permission.id,
                            )
                        )
            elif key == "name" and isinstance(resource, ConsolePermission):
                resource.code = str(value)
            elif key != "id" and hasattr(resource, key):
                setattr(resource, key, value)
        session.commit()
        return {
            "item": _serialize_console_identity_resource(session, resource),
            "request_id": request_id,
        }
    except IntegrityError:
        session.rollback()
        return _scope_conflict(collection, request_id, response)
    finally:
        session.close()


def _delete_console_identity_resource(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    session = _open_scope_session()
    try:
        resource: ConsoleRole | ConsolePermission | None
        if collection == "roles":
            resource = session.get(ConsoleRole, resource_id)
        else:
            resource = session.get(ConsolePermission, resource_id)
        if resource is None or resource.is_deleted:
            return _scope_not_found(collection, resource_id, request_id, response)
        resource.status = "deleted"
        resource.is_deleted = True
        resource.deleted_at = datetime.now(UTC)
        session.commit()
        return {
            "item": _serialize_console_identity_resource(session, resource),
            "request_id": request_id,
        }
    finally:
        session.close()


def _permission_parts(code: str) -> tuple[str, str]:
    if code == "*":
        return "*", "*"
    if ":" in code:
        resource, action = code.rsplit(":", 1)
        return resource, action
    return code, "use"


def _model_columns(model: type[Any]) -> set[str]:
    return set(model.__table__.columns.keys())


def _coerce_column_value(model: type[Any], key: str, value: Any) -> Any:
    column = model.__table__.columns.get(key)
    if column is None or value is None or value == "":
        return value
    if isinstance(column.type, Integer):
        return int(value)
    if isinstance(column.type, Float):
        return float(value)
    if isinstance(column.type, Boolean):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return value


def _public_field_name(column_name: str) -> str:
    if column_name.endswith("_json"):
        return column_name.removesuffix("_json")
    return column_name


def _db_record_environment(record: Any) -> str | None:
    if hasattr(record, "environment"):
        return record.environment
    metadata = getattr(record, "metadata_json", None)
    if isinstance(metadata, dict):
        value = metadata.get("_environment")
        return str(value) if value is not None else None
    return None


def _db_record_in_scope(
    record: Any,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> bool:
    if (
        tenant_id is not None
        and hasattr(record, "tenant_id")
        and record.tenant_id != tenant_id
    ):
        return False
    if (
        project_id is not None
        and hasattr(record, "project_id")
        and record.project_id != project_id
    ):
        return False
    record_environment = _db_record_environment(record)
    if environment is not None and record_environment not in {None, environment}:
        return False
    return True


def _serialize_db_admin_record(record: Any, spec: AdminDbCollectionSpec) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for column in record.__table__.columns:
        key = column.name
        if key in {"is_deleted", "deleted_at", "deleted_by"}:
            continue
        value = getattr(record, key)
        if isinstance(value, datetime):
            value = value.isoformat()
        item[_public_field_name(key)] = value
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        if spec.expose_name_from_metadata and not item.get("name"):
            item["name"] = metadata.get("name")
        if "environment" not in item:
            item["environment"] = metadata.get("_environment")
        item["metadata"] = {key: value for key, value in metadata.items() if key != "_environment"}
    elif "environment" not in item:
        item["environment"] = None
    return item


def _db_payload_attrs(
    collection: str,
    spec: AdminDbCollectionSpec,
    payload: dict[str, Any] | None,
    *,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
    actor: AuthenticatedActor | None,
    existing: Any | None = None,
) -> dict[str, Any]:
    data = payload or {}
    columns = _model_columns(spec.model)
    attrs: dict[str, Any] = {} if existing is not None else dict(spec.defaults)
    if existing is None:
        if "tenant_id" in columns:
            attrs["tenant_id"] = tenant_id
        if "project_id" in columns:
            attrs["project_id"] = project_id
        if "created_by" in columns and actor is not None:
            attrs["created_by"] = actor.actor_id
    if "updated_by" in columns and actor is not None:
        attrs["updated_by"] = actor.actor_id
    if "environment" in columns and environment is not None:
        attrs["environment"] = environment

    metadata = dict(getattr(existing, "metadata_json", None) or attrs.get("metadata_json") or {})
    if isinstance(data.get("metadata"), dict):
        metadata.update(dict(data["metadata"]))
    if "name" in data and "name" not in columns:
        metadata["name"] = data["name"]
    if spec.environment_in_metadata and environment is not None and "environment" not in columns:
        metadata["_environment"] = environment

    for key, value in data.items():
        if key in {"id", "tenant_id", "project_id", "environment", "metadata"}:
            continue
        if key in columns and key not in _AUDIT_FIELD_NAMES:
            attrs[key] = _coerce_column_value(spec.model, key, value)
        json_column = f"{key}_json"
        if json_column in columns:
            attrs[json_column] = value
    if "metadata_json" in columns:
        attrs["metadata_json"] = metadata
    if "status" in columns and "status" not in attrs and (existing is None or "status" in data):
        attrs["status"] = str(data.get("status") or "active")
    return attrs


def _validate_db_payload(
    collection: str,
    spec: AdminDbCollectionSpec,
    payload: dict[str, Any] | None,
    session: Session,
    *,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
    request_id: str | None,
    response: Response,
    existing: Any | None = None,
) -> dict[str, Any] | None:
    data = payload or {}
    missing = [
        field_name
        for field_name in spec.required_fields
        if existing is None and (data.get(field_name) is None or data.get(field_name) == "")
    ]
    if missing:
        return _validation_error(
            collection,
            request_id,
            response,
            {"missing_fields": missing},
        )
    for field_name, parent_model in spec.parent_refs.items():
        value = data.get(field_name)
        if value is None or value == "":
            continue
        parent = session.get(parent_model, int(value))
        if parent is None or getattr(parent, "is_deleted", False):
            return _validation_error(
                collection,
                request_id,
                response,
                {"field": field_name, "reason": "parent_not_found", "parent_id": value},
            )
        if not _db_record_in_scope(parent, tenant_id, project_id, environment):
            return _validation_error(
                collection,
                request_id,
                response,
                {"field": field_name, "reason": "parent_out_of_scope", "parent_id": value},
            )
    return None


def _list_db_collection(
    collection: str,
    request_id: str | None,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any]:
    spec = _DB_COLLECTIONS[collection]
    session = _open_scope_session()
    try:
        _seed_scope_resources(session)
        resolved_tenant_id, resolved_project_id = _resolve_scope_ids(session, tenant_id, project_id)
        model = spec.model
        statement = select(model)
        if hasattr(model, "is_deleted"):
            statement = statement.where(model.is_deleted.is_(False))
        if tenant_id is not None and hasattr(model, "tenant_id"):
            statement = statement.where(model.tenant_id == resolved_tenant_id)
        if project_id is not None and hasattr(model, "project_id"):
            statement = statement.where(model.project_id == resolved_project_id)
        if hasattr(model, "created_at"):
            statement = statement.order_by(model.created_at.desc())
        records = [
            record
            for record in session.scalars(statement)
            if _db_record_in_scope(record, resolved_tenant_id, resolved_project_id, environment)
        ]
        items = [_serialize_db_admin_record(record, spec) for record in records]
        return {"items": items, "count": len(items), "request_id": request_id}
    finally:
        session.close()


def _create_db_record(
    collection: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
    actor: AuthenticatedActor | None,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any]:
    spec = _DB_COLLECTIONS[collection]
    session = _open_scope_session()
    try:
        _seed_scope_resources(session)
        resolved_tenant_id, resolved_project_id = _resolve_scope_ids(session, tenant_id, project_id)
        validation_error = _validate_db_payload(
            collection,
            spec,
            payload,
            session,
            tenant_id=resolved_tenant_id,
            project_id=resolved_project_id,
            environment=environment,
            request_id=request_id,
            response=response,
        )
        if validation_error is not None:
            return validation_error
        record = spec.model(
            **_db_payload_attrs(
                collection,
                spec,
                payload,
                tenant_id=resolved_tenant_id,
                project_id=resolved_project_id,
                environment=environment,
                actor=actor,
            )
        )
        session.add(record)
        session.flush()
        session.commit()
        response.status_code = 201
        return {"item": _serialize_db_admin_record(record, spec), "request_id": request_id}
    except IntegrityError:
        session.rollback()
        return _scope_conflict(collection, request_id, response)
    finally:
        session.close()


def _get_db_record_or_error(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
    session: Session,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> Any | dict[str, Any]:
    spec = _DB_COLLECTIONS[collection]
    record = session.get(spec.model, resource_id)
    if (
        record is None
        or getattr(record, "is_deleted", False)
        or not _db_record_in_scope(record, tenant_id, project_id, environment)
    ):
        return _resource_not_found(collection, resource_id, request_id, response)
    return record


def _update_db_record(
    collection: str,
    resource_id: int,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
    actor: AuthenticatedActor | None,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any]:
    spec = _DB_COLLECTIONS[collection]
    session = _open_scope_session()
    try:
        _seed_scope_resources(session)
        resolved_tenant_id, resolved_project_id = _resolve_scope_ids(session, tenant_id, project_id)
        result = _get_db_record_or_error(
            collection,
            resource_id,
            request_id,
            response,
            session,
            resolved_tenant_id,
            resolved_project_id,
            environment,
        )
        if isinstance(result, dict):
            return result
        validation_error = _validate_db_payload(
            collection,
            spec,
            payload,
            session,
            tenant_id=resolved_tenant_id,
            project_id=resolved_project_id,
            environment=environment,
            request_id=request_id,
            response=response,
            existing=result,
        )
        if validation_error is not None:
            return validation_error
        attrs = _db_payload_attrs(
            collection,
            spec,
            payload,
            tenant_id=resolved_tenant_id,
            project_id=resolved_project_id,
            environment=environment,
            actor=actor,
            existing=result,
        )
        for key, value in attrs.items():
            if key not in {"id", "tenant_id", "project_id", "created_by"}:
                setattr(result, key, value)
        session.commit()
        return {"item": _serialize_db_admin_record(result, spec), "request_id": request_id}
    except IntegrityError:
        session.rollback()
        return _scope_conflict(collection, request_id, response)
    finally:
        session.close()


def _delete_db_record(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
    actor: AuthenticatedActor | None,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any]:
    spec = _DB_COLLECTIONS[collection]
    session = _open_scope_session()
    try:
        _seed_scope_resources(session)
        resolved_tenant_id, resolved_project_id = _resolve_scope_ids(session, tenant_id, project_id)
        result = _get_db_record_or_error(
            collection,
            resource_id,
            request_id,
            response,
            session,
            resolved_tenant_id,
            resolved_project_id,
            environment,
        )
        if isinstance(result, dict):
            return result
        if hasattr(result, "status"):
            result.status = "deleted"
        if hasattr(result, "is_deleted"):
            result.is_deleted = True
        if hasattr(result, "deleted_at"):
            result.deleted_at = datetime.now(UTC)
        if hasattr(result, "deleted_by") and actor is not None:
            result.deleted_by = actor.actor_id
        session.commit()
        return {"item": _serialize_db_admin_record(result, spec), "request_id": request_id}
    finally:
        session.close()


def _get_db_record(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any]:
    spec = _DB_COLLECTIONS[collection]
    session = _open_scope_session()
    try:
        _seed_scope_resources(session)
        resolved_tenant_id, resolved_project_id = _resolve_scope_ids(session, tenant_id, project_id)
        result = _get_db_record_or_error(
            collection,
            resource_id,
            request_id,
            response,
            session,
            resolved_tenant_id,
            resolved_project_id,
            environment,
        )
        if isinstance(result, dict):
            return result
        return {"item": _serialize_db_admin_record(result, spec), "request_id": request_id}
    finally:
        session.close()


def _list(
    collection: str,
    request_id: str | None,
    tenant_id: int | None = None,
    project_id: int | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    if collection in {"tenants", "projects", "environments"}:
        return _list_scope_collection(collection, request_id, tenant_id, project_id)
    if collection in {"roles", "permissions"}:
        return _list_console_identity_collection(collection, request_id)
    if collection == "audit_logs":
        return _list_audit_logs(request_id, tenant_id, project_id)
    if collection in _DB_COLLECTIONS:
        return _list_db_collection(collection, request_id, tenant_id, project_id, environment)
    items = [
        item
        for item in _COLLECTIONS[collection].values()
        if _resource_in_scope(item, tenant_id, project_id, environment)
    ]
    return {"items": items, "count": len(items), "request_id": request_id}


def _create(
    collection: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
    actor: AuthenticatedActor | None = None,
    tenant_id: int | None = None,
    project_id: int | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    if collection in {"tenants", "projects", "environments"}:
        assert actor is not None
        return _create_scope_resource(collection, payload, request_id, response, actor)
    if collection in {"roles", "permissions"}:
        return _create_console_identity_resource(collection, payload, request_id, response)
    if collection in _DB_COLLECTIONS:
        return _create_db_record(
            collection,
            payload,
            request_id,
            response,
            actor,
            tenant_id,
            project_id,
            environment,
        )
    response.status_code = 201
    resource_id = int((payload or {}).get("id") or _next_collection_id(collection))
    resource = {
        "id": resource_id,
        "status": str((payload or {}).get("status") or "active"),
        "tenant_id": tenant_id,
        "project_id": project_id,
        "environment": environment,
        "created_at": _now(),
        "updated_at": _now(),
        "metadata": dict((payload or {}).get("metadata") or {}),
        **{
            key: value
            for key, value in (payload or {}).items()
            if key not in {"metadata", "tenant_id", "project_id", "environment"}
        },
    }
    _COLLECTIONS[collection][resource_id] = resource
    return {"item": resource, "request_id": request_id}


def _update(
    collection: str,
    resource_id: int,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
    tenant_id: int | None = None,
    project_id: int | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    if collection in {"tenants", "projects", "environments"}:
        return _update_scope_resource(collection, resource_id, payload, request_id, response)
    if collection in {"roles", "permissions"}:
        return _update_console_identity_resource(
            collection,
            resource_id,
            payload,
            request_id,
            response,
        )
    if collection in _DB_COLLECTIONS:
        return _update_db_record(
            collection,
            resource_id,
            payload,
            request_id,
            response,
            None,
            tenant_id,
            project_id,
            environment,
        )
    resource = _COLLECTIONS[collection].get(resource_id)
    if resource is None or not _resource_in_scope(resource, tenant_id, project_id, environment):
        return _resource_not_found(collection, resource_id, request_id, response)
    for key, value in (payload or {}).items():
        if key not in {"id", "tenant_id", "project_id", "environment"}:
            resource[key] = value
    resource["updated_at"] = _now()
    return {"item": resource, "request_id": request_id}


def _delete(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
    tenant_id: int | None = None,
    project_id: int | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    if collection in {"tenants", "projects", "environments"}:
        return _delete_scope_resource(collection, resource_id, request_id, response)
    if collection in {"roles", "permissions"}:
        return _delete_console_identity_resource(collection, resource_id, request_id, response)
    if collection in _DB_COLLECTIONS:
        return _delete_db_record(
            collection,
            resource_id,
            request_id,
            response,
            None,
            tenant_id,
            project_id,
            environment,
        )
    resource = _COLLECTIONS[collection].get(resource_id)
    if resource is None or not _resource_in_scope(resource, tenant_id, project_id, environment):
        return _resource_not_found(collection, resource_id, request_id, response)
    resource["status"] = "deleted"
    resource["deleted_at"] = _now()
    resource["updated_at"] = _now()
    return {"item": resource, "request_id": request_id}


def _get(
    collection: str,
    resource_id: int,
    request_id: str | None,
    response: Response,
    tenant_id: int | None = None,
    project_id: int | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    if collection in _DB_COLLECTIONS:
        return _get_db_record(
            collection,
            resource_id,
            request_id,
            response,
            tenant_id,
            project_id,
            environment,
        )
    resource = _COLLECTIONS[collection].get(resource_id)
    if resource is None or not _resource_in_scope(resource, tenant_id, project_id, environment):
        return _resource_not_found(collection, resource_id, request_id, response)
    return {"item": resource, "request_id": request_id}


@router.get("/policies")
def list_policies(
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _list("policies", x_request_id, x_tenant_id, x_project_id, x_environment)


@router.post("/policies", status_code=201)
def create_policy(
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _create(
        "policies",
        payload,
        x_request_id,
        response,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
    )


@router.patch("/policies/{policy_id}")
def update_policy(
    policy_id: str,
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _update(
        "policies",
        policy_id,
        payload,
        x_request_id,
        response,
        x_tenant_id,
        x_project_id,
        x_environment,
    )


@router.delete("/policies/{policy_id}")
def delete_policy(
    policy_id: str,
    response: Response,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _delete(
        "policies",
        policy_id,
        x_request_id,
        response,
        x_tenant_id,
        x_project_id,
        x_environment,
    )


@router.get("/artifacts/{artifact_id}")
def get_artifact(
    artifact_id: int,
    response: Response,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _get(
        "artifacts",
        artifact_id,
        x_request_id,
        response,
        x_tenant_id,
        x_project_id,
        x_environment,
    )


@router.get("/human-tasks")
def list_human_tasks(
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _list("human_tasks", x_request_id, x_tenant_id, x_project_id, x_environment)


@router.post("/human-tasks/{task_id}/approve")
def approve_human_task(
    task_id: int,
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _record_human_decision(
        task_id,
        decision="approved",
        payload=payload,
        request_id=x_request_id,
        response=response,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
    )


@router.post("/human-tasks/{task_id}/reject")
def reject_human_task(
    task_id: int,
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _record_human_decision(
        task_id,
        decision="rejected",
        payload=payload,
        request_id=x_request_id,
        response=response,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
    )


def _record_human_decision(
    task_id: int,
    *,
    decision: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any]:
    if "human_tasks" in _DB_COLLECTIONS:
        spec = _DB_COLLECTIONS["human_tasks"]
        session = _open_scope_session()
        try:
            _seed_scope_resources(session)
            task = session.get(spec.model, task_id)
            if task is not None and (
                getattr(task, "is_deleted", False)
                or not _db_record_in_scope(task, tenant_id, project_id, environment)
            ):
                return _resource_not_found("human_tasks", task_id, request_id, response)
            if task is None:
                task = spec.model(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    type=str((payload or {}).get("type") or "approval"),
                    status=decision,
                    decision_ref="inline:decision",
                )
                session.add(task)
            else:
                task.status = decision
                task.decision_ref = "inline:decision"
            session.commit()
            return {
                "item": _serialize_db_admin_record(task, spec),
                "request_id": request_id,
                "audit_required": True,
            }
        except IntegrityError:
            session.rollback()
            return _scope_conflict("human_tasks", request_id, response)
        finally:
            session.close()

    task = _COLLECTIONS["human_tasks"].get(task_id)
    if task is not None and not _resource_in_scope(task, tenant_id, project_id, environment):
        return _resource_not_found("human_tasks", task_id, request_id, response)
    if task is None:
        task = {
            "id": task_id,
            "status": "pending",
            "tenant_id": tenant_id,
            "project_id": project_id,
            "environment": environment,
            "created_at": _now(),
            "metadata": {},
        }
        _COLLECTIONS["human_tasks"][task_id] = task
    task["status"] = decision
    task["decision_payload"] = dict((payload or {}).get("decision_payload") or {})
    task["updated_at"] = _now()
    return {
        "item": task,
        "request_id": request_id,
        "audit_required": True,
    }


def _serialize_service_account(record: Any) -> dict[str, Any]:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "project_id": record.project_id,
        "name": record.name,
        "permissions": sorted(record.permissions),
        "status": record.status,
        "created_by": record.created_by,
        "created_at": record.created_at.isoformat(),
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
    }


def _serialize_api_key(record: Any) -> dict[str, Any]:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "project_id": record.project_id,
        "name": record.name,
        "owner_type": record.owner_type,
        "owner_id": record.owner_id,
        "key_prefix": record.key_prefix,
        "scopes": sorted(record.scopes),
        "status": record.status,
        "created_by": record.created_by,
        "created_at": record.created_at.isoformat(),
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
    }


@router.get("/api-keys")
def list_api_keys(
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    keys = default_api_key_authenticator().list_keys()
    items = [
        _serialize_api_key(record)
        for record in keys
        if _actor_can_access_target(actor, record.tenant_id, record.project_id)
    ]
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.get("/identity/service-accounts")
def list_identity_service_accounts(
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    service_accounts = default_api_key_authenticator().service_accounts.list()
    items = [
        _serialize_service_account(record)
        for record in service_accounts
        if _actor_can_access_target(actor, record.tenant_id, record.project_id)
    ]
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.post("/identity/service-accounts", status_code=201)
def create_identity_service_account(
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    target_tenant_id = int(data.get("tenant_id") or actor.tenant_id)
    raw_project_id = data.get("project_id") or actor.project_id
    target_project_id = int(raw_project_id) if raw_project_id is not None else None
    if target_project_id is None:
        response.status_code = 400
        return {
            "error_code": "project_scope_required",
            "message": "A project scope is required to create a service account.",
            "request_id": x_request_id,
            "details": {},
        }
    if not _actor_can_access_target(actor, target_tenant_id, target_project_id):
        response.status_code = 403
        return _scope_denied(x_request_id, target_tenant_id, target_project_id)
    record = default_api_key_authenticator().service_accounts.create(
        tenant_id=target_tenant_id,
        project_id=target_project_id,
        name=str(data.get("name") or "Service Account"),
        permissions=set(data.get("permissions") or ["agent:read"]),
        created_by=actor.actor_id,
    )
    _append_identity_audit(
        actor,
        action="identity.service_account.create",
        resource_type="service_account",
        resource_id=record.id,
        request_id=x_request_id,
        metadata={"permissions": sorted(record.permissions)},
    )
    return {"item": _serialize_service_account(record), "request_id": x_request_id}


@router.patch("/identity/service-accounts/{service_account_id}")
def update_identity_service_account(
    service_account_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    registry = default_api_key_authenticator().service_accounts
    try:
        record = registry.get(service_account_id)
    except KeyError:
        return _machine_identity_not_found(
            "service_accounts",
            service_account_id,
            x_request_id,
            response,
        )
    if not _actor_can_access_target(actor, record.tenant_id, record.project_id):
        response.status_code = 403
        return _scope_denied(x_request_id, record.tenant_id, record.project_id)
    if data.get("status") is not None:
        record = registry.update(
            service_account_id,
            name=str(data["name"]) if data.get("name") is not None else None,
            permissions=set(data["permissions"]) if data.get("permissions") is not None else None,
            status=str(data["status"]),
        )
        if record.status != "active":
            for key in default_api_key_authenticator().list_keys(
                owner_type="service_account",
                owner_id=service_account_id,
            ):
                default_api_key_authenticator().disable_key(key.id, actor_id="console")
        elif data.get("permissions") is not None:
            _disable_api_keys_outside_service_account_permissions(service_account_id, record, actor)
        _append_identity_audit(
            actor,
            action="identity.service_account.update",
            resource_type="service_account",
            resource_id=service_account_id,
            request_id=x_request_id,
            metadata={"status": data["status"]},
        )
    elif data.get("name") is not None or data.get("permissions") is not None:
        record = registry.update(
            service_account_id,
            name=str(data["name"]) if data.get("name") is not None else None,
            permissions=set(data["permissions"]) if data.get("permissions") is not None else None,
        )
        if data.get("permissions") is not None:
            _disable_api_keys_outside_service_account_permissions(service_account_id, record, actor)
        _append_identity_audit(
            actor,
            action="identity.service_account.update",
            resource_type="service_account",
            resource_id=service_account_id,
            request_id=x_request_id,
            metadata={"permissions": sorted(record.permissions)},
        )
    return {"item": _serialize_service_account(record), "request_id": x_request_id}


def _disable_api_keys_outside_service_account_permissions(
    service_account_id: int,
    record: Any,
    actor: AuthenticatedActor,
) -> None:
    for key in default_api_key_authenticator().list_keys(
        owner_type="service_account",
        owner_id=service_account_id,
    ):
        if not set(key.scopes).issubset(record.permissions):
            default_api_key_authenticator().disable_key(key.id, actor_id=actor.actor_id)


@router.delete("/identity/service-accounts/{service_account_id}")
def delete_identity_service_account(
    service_account_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    registry = default_api_key_authenticator().service_accounts
    try:
        record = registry.get(service_account_id)
    except KeyError:
        return _machine_identity_not_found(
            "service_accounts",
            service_account_id,
            x_request_id,
            response,
        )
    if not _actor_can_access_target(actor, record.tenant_id, record.project_id):
        response.status_code = 403
        return _scope_denied(x_request_id, record.tenant_id, record.project_id)
    record = registry.delete(service_account_id)
    for key in default_api_key_authenticator().list_keys(
        owner_type="service_account",
        owner_id=service_account_id,
    ):
        default_api_key_authenticator().disable_key(key.id, actor_id=actor.actor_id)
    _append_identity_audit(
        actor,
        action="identity.service_account.delete",
        resource_type="service_account",
        resource_id=service_account_id,
        request_id=x_request_id,
    )
    return {"item": _serialize_service_account(record), "request_id": x_request_id}


@router.get("/identity/service-accounts/{service_account_id}/api-keys")
def list_identity_service_account_api_keys(
    service_account_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    try:
        owner = default_api_key_authenticator().service_accounts.get(service_account_id)
    except KeyError:
        return _machine_identity_not_found(
            "service_accounts",
            service_account_id,
            x_request_id,
            response,
        )
    if not _actor_can_access_target(actor, owner.tenant_id, owner.project_id):
        response.status_code = 403
        return _scope_denied(x_request_id, owner.tenant_id, owner.project_id)
    keys = default_api_key_authenticator().list_keys(
        owner_type="service_account",
        owner_id=service_account_id,
    )
    items = [_serialize_api_key(record) for record in keys]
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.post("/identity/service-accounts/{service_account_id}/api-keys", status_code=201)
def create_identity_service_account_api_key(
    service_account_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    try:
        owner = default_api_key_authenticator().service_accounts.get(service_account_id)
    except KeyError:
        return _machine_identity_not_found(
            "service_accounts",
            service_account_id,
            x_request_id,
            response,
        )
    if not _actor_can_access_target(actor, owner.tenant_id, owner.project_id):
        response.status_code = 403
        return _scope_denied(x_request_id, owner.tenant_id, owner.project_id)
    try:
        plain_key, record = default_api_key_authenticator().create_key(
            tenant_id=owner.tenant_id,
            project_id=owner.project_id,
            name=str(data.get("name") or "API Key"),
            owner_type="service_account",
            owner_id=service_account_id,
            scopes=set(data.get("scopes") or []),
            created_by=actor.actor_id,
            expires_at=_parse_optional_datetime(data.get("expires_at")),
        )
    except APIKeyScopeError as exc:
        response.status_code = 403
        return {
            "error_code": str(exc),
            "message": "API key scopes must be a subset of the service account permissions.",
            "request_id": x_request_id,
            "details": {"service_account_id": service_account_id},
        }
    _append_identity_audit(
        actor,
        action="identity.api_key.create",
        resource_type="api_key",
        resource_id=record.id,
        request_id=x_request_id,
        metadata={"service_account_id": service_account_id, "scopes": sorted(record.scopes)},
    )
    return {
        "item": _serialize_api_key(record),
        "plain_key": plain_key,
        "request_id": x_request_id,
    }


@router.post("/identity/service-accounts/{service_account_id}/api-keys/{key_id}/disable")
def disable_identity_service_account_api_key(
    service_account_id: int,
    key_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    record = _get_service_account_api_key(service_account_id, key_id)
    if record is None:
        return _machine_identity_not_found("api_keys", key_id, x_request_id, response)
    if not _actor_can_access_target(actor, record.tenant_id, record.project_id):
        response.status_code = 403
        return _scope_denied(x_request_id, record.tenant_id, record.project_id)
    record = default_api_key_authenticator().disable_key(key_id, actor_id=actor.actor_id)
    _append_identity_audit(
        actor,
        action="identity.api_key.disable",
        resource_type="api_key",
        resource_id=key_id,
        request_id=x_request_id,
        metadata={"service_account_id": service_account_id},
    )
    return {"item": _serialize_api_key(record), "request_id": x_request_id}


@router.post("/identity/service-accounts/{service_account_id}/api-keys/{key_id}/enable")
def enable_identity_service_account_api_key(
    service_account_id: int,
    key_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    record = _get_service_account_api_key(service_account_id, key_id)
    if record is None:
        return _machine_identity_not_found("api_keys", key_id, x_request_id, response)
    if not _actor_can_access_target(actor, record.tenant_id, record.project_id):
        response.status_code = 403
        return _scope_denied(x_request_id, record.tenant_id, record.project_id)
    try:
        record = default_api_key_authenticator().enable_key(key_id, actor_id=actor.actor_id)
    except (APIKeyError, KeyError) as exc:
        response.status_code = 403 if isinstance(exc, APIKeyError) else 404
        return {
            "error_code": str(exc) if isinstance(exc, APIKeyError) else "api_key_not_found",
            "message": "API key cannot be enabled for the current service account permissions.",
            "request_id": x_request_id,
            "details": {"service_account_id": service_account_id, "api_key_id": key_id},
        }
    _append_identity_audit(
        actor,
        action="identity.api_key.enable",
        resource_type="api_key",
        resource_id=key_id,
        request_id=x_request_id,
        metadata={"service_account_id": service_account_id},
    )
    return {"item": _serialize_api_key(record), "request_id": x_request_id}


@router.delete("/identity/service-accounts/{service_account_id}/api-keys/{key_id}")
def delete_identity_service_account_api_key(
    service_account_id: int,
    key_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    record = _get_service_account_api_key(service_account_id, key_id)
    if record is None:
        return _machine_identity_not_found("api_keys", key_id, x_request_id, response)
    if not _actor_can_access_target(actor, record.tenant_id, record.project_id):
        response.status_code = 403
        return _scope_denied(x_request_id, record.tenant_id, record.project_id)
    record = default_api_key_authenticator().delete_key(key_id, actor_id=actor.actor_id)
    _append_identity_audit(
        actor,
        action="identity.api_key.delete",
        resource_type="api_key",
        resource_id=key_id,
        request_id=x_request_id,
        metadata={"service_account_id": service_account_id},
    )
    return {"item": _serialize_api_key(record), "request_id": x_request_id}


def _get_service_account_api_key(service_account_id: int, key_id: int) -> Any | None:
    return next(
        (
            key
            for key in default_api_key_authenticator().list_keys(
                owner_type="service_account",
                owner_id=service_account_id,
            )
            if key.id == key_id
        ),
        None,
    )


def register_collection_routes(path: str, collection: str) -> None:
    async def get_items(
        x_request_id: RequestIdHeader = None,
        x_tenant_id: TenantIdHeader = None,
        x_project_id: ProjectIdHeader = None,
        x_environment: EnvironmentHeader = None,
    ) -> dict[str, Any]:
        return _list(collection, x_request_id, x_tenant_id, x_project_id, x_environment)

    async def create_item(
        response: Response,
        actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
        payload: AdminPayload = None,
        x_request_id: RequestIdHeader = None,
        x_tenant_id: TenantIdHeader = None,
        x_project_id: ProjectIdHeader = None,
        x_environment: EnvironmentHeader = None,
    ) -> dict[str, Any]:
        return _create(
            collection,
            payload,
            x_request_id,
            response,
            actor,
            x_tenant_id,
            x_project_id,
            x_environment,
        )

    async def update_item(
        resource_id: int,
        response: Response,
        payload: AdminPayload = None,
        x_request_id: RequestIdHeader = None,
        x_tenant_id: TenantIdHeader = None,
        x_project_id: ProjectIdHeader = None,
        x_environment: EnvironmentHeader = None,
    ) -> dict[str, Any]:
        return _update(
            collection,
            resource_id,
            payload,
            x_request_id,
            response,
            x_tenant_id,
            x_project_id,
            x_environment,
        )

    async def delete_item(
        resource_id: int,
        response: Response,
        x_request_id: RequestIdHeader = None,
        x_tenant_id: TenantIdHeader = None,
        x_project_id: ProjectIdHeader = None,
        x_environment: EnvironmentHeader = None,
    ) -> dict[str, Any]:
        return _delete(
            collection,
            resource_id,
            x_request_id,
            response,
            x_tenant_id,
            x_project_id,
            x_environment,
        )

    router.add_api_route(path, get_items, methods=["GET"])
    router.add_api_route(path, create_item, methods=["POST"], status_code=201)
    router.add_api_route(f"{path}/{{resource_id}}", update_item, methods=["PATCH"])
    router.add_api_route(f"{path}/{{resource_id}}", delete_item, methods=["DELETE"])


for _path, _collection in [
    ("/identity/tenants", "tenants"),
    ("/identity/projects", "projects"),
    ("/identity/environments", "environments"),
    ("/model-gateways", "model_gateways"),
    ("/artifacts", "artifacts"),
    ("/published-surfaces", "published_surfaces"),
    ("/ingress-routes", "ingress_routes"),
    ("/datasets", "datasets"),
    ("/dataset-items", "dataset_items"),
    ("/experiments", "experiments"),
    ("/replay-jobs", "replay_jobs"),
    ("/schedules", "schedules"),
    ("/batch-runs", "batch_runs"),
    ("/notifications/channels", "notification_channels"),
    ("/alerts/rules", "alert_rules"),
    ("/backups/plans", "backup_plans"),
    ("/backups/restore-jobs", "restore_jobs"),
    ("/webhooks/subscriptions", "webhook_subscriptions"),
    ("/incidents", "incidents"),
    ("/identity/users", "users"),
    ("/identity/roles", "roles"),
    ("/identity/permissions", "permissions"),
    ("/secrets", "secrets"),
    ("/tools", "tools"),
    ("/assets/prompts", "prompt_assets"),
    ("/assets/configs", "config_assets"),
    ("/assets/templates", "template_assets"),
    ("/audit-logs", "audit_logs"),
    ("/evaluations/results", "evaluation_results"),
    ("/feedback", "feedback"),
    ("/semantic-store/providers", "semantic_store_providers"),
    ("/observability/exporters", "observability_exporters"),
    ("/sandbox/policies", "sandbox_policies"),
    ("/container-pool/policies", "container_pool_policies"),
]:
    register_collection_routes(_path, _collection)


@router.get("/catalog/items")
def list_catalog_items(
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _list("catalog_items", x_request_id, x_tenant_id, x_project_id, x_environment)


@router.post("/catalog/items", status_code=201)
def create_catalog_item(
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _create(
        "catalog_items",
        payload,
        x_request_id,
        response,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
    )


@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge_incident(
    incident_id: int,
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _record_incident_decision(
        incident_id,
        status="acknowledged",
        payload=payload,
        request_id=x_request_id,
        response=response,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
    )


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(
    incident_id: int,
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    return _record_incident_decision(
        incident_id,
        status="resolved",
        payload=payload,
        request_id=x_request_id,
        response=response,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
    )


def _record_incident_decision(
    incident_id: int,
    *,
    status: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any]:
    if "incidents" in _DB_COLLECTIONS:
        spec = _DB_COLLECTIONS["incidents"]
        session = _open_scope_session()
        try:
            _seed_scope_resources(session)
            incident = session.get(spec.model, incident_id)
            if incident is not None and (
                getattr(incident, "is_deleted", False)
                or not _db_record_in_scope(incident, tenant_id, project_id, environment)
            ):
                return _resource_not_found("incidents", incident_id, request_id, response)
            decision_payload = dict((payload or {}).get("decision_payload") or {})
            if incident is None:
                incident = spec.model(
                    **_db_payload_attrs(
                        "incidents",
                        spec,
                        {
                            "name": f"Incident {incident_id}",
                            "status": status,
                            "metadata": {"decision_payload": decision_payload},
                        },
                        tenant_id=tenant_id,
                        project_id=project_id,
                        environment=environment,
                        actor=None,
                    )
                )
                session.add(incident)
            else:
                incident.status = status
                metadata = dict(getattr(incident, "metadata_json", None) or {})
                metadata["decision_payload"] = decision_payload
                if environment is not None and "environment" not in _model_columns(spec.model):
                    metadata["_environment"] = environment
                incident.metadata_json = metadata
            session.commit()
            return {
                "item": _serialize_db_admin_record(incident, spec),
                "request_id": request_id,
            }
        except IntegrityError:
            session.rollback()
            return _scope_conflict("incidents", request_id, response)
        finally:
            session.close()

    incident = _COLLECTIONS["incidents"].get(incident_id)
    if incident is not None and not _resource_in_scope(
        incident,
        tenant_id,
        project_id,
        environment,
    ):
        return _resource_not_found("incidents", incident_id, request_id, response)
    if incident is None:
        incident = {
            "id": incident_id,
            "status": "open",
            "tenant_id": tenant_id,
            "project_id": project_id,
            "environment": environment,
            "created_at": _now(),
            "metadata": {},
        }
        _COLLECTIONS["incidents"][incident_id] = incident
    incident["status"] = status
    incident["decision_payload"] = dict((payload or {}).get("decision_payload") or {})
    incident["updated_at"] = _now()
    return {"item": incident, "request_id": request_id}
