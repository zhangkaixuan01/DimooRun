import os
from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from dimoo_run.api.dependencies import (
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    default_api_key_authenticator,
    enforce_console_actor,
)
from dimoo_run.core.config import Settings
from dimoo_run.domain.models import (
    ConsolePermission,
    ConsoleRole,
    ConsoleRolePermission,
    Environment,
    Project,
    Tenant,
)
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.persistence.repositories import (
    EnvironmentRepository,
    ProjectRepository,
    TenantRepository,
)
from dimoo_run.security.api_keys import APIKeyScopeError

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]

_COLLECTIONS: dict[str, dict[str, dict[str, Any]]] = {
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
    "service_accounts": {},
    "api_keys": {},
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


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _resource_id(collection: str) -> str:
    return f"{collection.rstrip('s')}_{uuid4().hex[:12]}"


def _default_scope() -> tuple[str, str, str]:
    return (
        os.getenv("DIMOORUN_DEFAULT_TENANT_ID", "tenant_1"),
        os.getenv("DIMOORUN_DEFAULT_PROJECT_ID", "project_1"),
        os.getenv("DIMOORUN_DEFAULT_ENVIRONMENT", "local"),
    )


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
    tenant_id, project_id, environment = _default_scope()
    if session.get(Tenant, tenant_id) is None:
        session.add(
            Tenant(
                id=tenant_id,
                name=os.getenv("DIMOORUN_DEFAULT_TENANT_NAME", "Default Tenant"),
                slug=tenant_id,
                status="active",
            )
        )
    if session.get(Project, project_id) is None:
        session.add(
            Project(
                id=project_id,
                tenant_id=tenant_id,
                name=os.getenv("DIMOORUN_DEFAULT_PROJECT_NAME", "Default Project"),
                slug=project_id,
                status="active",
            )
        )
    if session.get(Environment, environment) is None:
        session.add(
            Environment(
                id=environment,
                tenant_id=tenant_id,
                project_id=project_id,
                name=environment,
                environment=environment,
                status="active",
                metadata_json={"seeded": True},
            )
        )
    session.commit()


def _scope_not_found(
    collection: str,
    resource_id: str,
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


def _machine_identity_not_found(
    collection: str,
    resource_id: str,
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
    tenant_id: str | None,
    project_id: str | None,
) -> dict[str, Any]:
    session = _open_scope_session()
    try:
        _seed_scope_resources(session)
        items: Sequence[Tenant | Project | Environment]
        if collection == "tenants":
            items = TenantRepository(session).list_active()
        elif collection == "projects":
            default_tenant_id, _, _ = _default_scope()
            items = ProjectRepository(session).list_by_tenant(tenant_id or default_tenant_id)
        else:
            default_tenant_id, default_project_id, _ = _default_scope()
            items = EnvironmentRepository(session).list_by_project(
                tenant_id or default_tenant_id,
                project_id or default_project_id,
            )
        serialized = [_serialize_scope_resource(item) for item in items]
        return {"items": serialized, "count": len(serialized), "request_id": request_id}
    finally:
        session.close()


def _create_scope_resource(
    collection: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    session = _open_scope_session()
    data = payload or {}
    try:
        _seed_scope_resources(session)
        if collection == "tenants":
            resource: Tenant | Project | Environment = Tenant(
                id=str(data.get("id") or _resource_id(collection)),
                name=str(data.get("name") or "Tenant"),
                slug=str(data.get("slug") or data.get("id") or _resource_id(collection)),
                status=str(data.get("status") or "active"),
            )
        elif collection == "projects":
            tenant_id, _, _ = _default_scope()
            resource = Project(
                id=str(data.get("id") or _resource_id(collection)),
                tenant_id=str(data.get("tenant_id") or tenant_id),
                name=str(data.get("name") or "Project"),
                slug=str(data.get("slug") or data.get("id") or _resource_id(collection)),
                status=str(data.get("status") or "active"),
            )
        else:
            tenant_id, project_id, _ = _default_scope()
            environment = str(data.get("environment") or _resource_id(collection))
            resource = Environment(
                id=str(data.get("id") or environment),
                tenant_id=str(data.get("tenant_id") or tenant_id),
                project_id=str(data.get("project_id") or project_id),
                name=str(data.get("name") or environment),
                environment=environment,
                status=str(data.get("status") or "active"),
                metadata_json=dict(data.get("metadata") or {}),
            )
        session.add(resource)
        session.commit()
        response.status_code = 201
        return {"item": _serialize_scope_resource(resource), "request_id": request_id}
    except IntegrityError:
        session.rollback()
        return _scope_conflict(collection, request_id, response)
    finally:
        session.close()


def _update_scope_resource(
    collection: str,
    resource_id: str,
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
    resource_id: str,
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
                id=str(data.get("id") or _resource_id(collection)),
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
                id=str(data.get("id") or _resource_id(collection)),
                code=code,
                resource=str(data.get("resource") or resource_name),
                action=str(data.get("action") or action),
                description=(
                    str(data["description"]) if data.get("description") is not None else None
                ),
                status=str(data.get("status") or "active"),
            )
        session.add(resource)
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
    resource_id: str,
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
                                id=_resource_id("role_permissions"),
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
    resource_id: str,
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


def _list(
    collection: str,
    request_id: str | None,
    tenant_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    if collection in {"tenants", "projects", "environments"}:
        return _list_scope_collection(collection, request_id, tenant_id, project_id)
    if collection in {"roles", "permissions"}:
        return _list_console_identity_collection(collection, request_id)
    return {
        "items": list(_COLLECTIONS[collection].values()),
        "count": len(_COLLECTIONS[collection]),
        "request_id": request_id,
    }


def _create(
    collection: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    if collection in {"tenants", "projects", "environments"}:
        return _create_scope_resource(collection, payload, request_id, response)
    if collection in {"roles", "permissions"}:
        return _create_console_identity_resource(collection, payload, request_id, response)
    response.status_code = 201
    resource = {
        "id": str((payload or {}).get("id") or _resource_id(collection)),
        "status": str((payload or {}).get("status") or "active"),
        "created_at": _now(),
        "updated_at": _now(),
        "metadata": dict((payload or {}).get("metadata") or {}),
        **{key: value for key, value in (payload or {}).items() if key != "metadata"},
    }
    _COLLECTIONS[collection][resource["id"]] = resource
    return {"item": resource, "request_id": request_id}


def _update(
    collection: str,
    resource_id: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    response: Response,
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
    resource = _COLLECTIONS[collection].get(resource_id)
    if resource is None:
        response.status_code = 404
        return {
            "error_code": "resource_not_found",
            "message": "Resource was not found.",
            "request_id": request_id,
            "details": {"collection": collection, "id": resource_id},
        }
    for key, value in (payload or {}).items():
        if key != "id":
            resource[key] = value
    resource["updated_at"] = _now()
    return {"item": resource, "request_id": request_id}


def _delete(
    collection: str,
    resource_id: str,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    if collection in {"tenants", "projects", "environments"}:
        return _delete_scope_resource(collection, resource_id, request_id, response)
    if collection in {"roles", "permissions"}:
        return _delete_console_identity_resource(collection, resource_id, request_id, response)
    resource = _COLLECTIONS[collection].get(resource_id)
    if resource is None:
        response.status_code = 404
        return {
            "error_code": "resource_not_found",
            "message": "Resource was not found.",
            "request_id": request_id,
            "details": {"collection": collection, "id": resource_id},
        }
    resource["status"] = "deleted"
    resource["deleted_at"] = _now()
    resource["updated_at"] = _now()
    return {"item": resource, "request_id": request_id}


def _get(
    collection: str,
    resource_id: str,
    request_id: str | None,
    response: Response,
) -> dict[str, Any]:
    resource = _COLLECTIONS[collection].get(resource_id)
    if resource is None:
        response.status_code = 404
        return {
            "error_code": "resource_not_found",
            "message": "Resource was not found.",
            "request_id": request_id,
            "details": {"collection": collection, "id": resource_id},
        }
    return {"item": resource, "request_id": request_id}


@router.get("/policies")
def list_policies(x_request_id: RequestIdHeader = None) -> dict[str, Any]:
    return _list("policies", x_request_id)


@router.post("/policies", status_code=201)
def create_policy(
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    return _create("policies", payload, x_request_id, response)


@router.patch("/policies/{policy_id}")
def update_policy(
    policy_id: str,
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    return _update("policies", policy_id, payload, x_request_id, response)


@router.delete("/policies/{policy_id}")
def delete_policy(
    policy_id: str,
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    return _delete("policies", policy_id, x_request_id, response)


@router.get("/artifacts/{artifact_id}")
def get_artifact(
    artifact_id: str,
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    return _get("artifacts", artifact_id, x_request_id, response)


@router.get("/human-tasks")
def list_human_tasks(x_request_id: RequestIdHeader = None) -> dict[str, Any]:
    return _list("human_tasks", x_request_id)


@router.post("/human-tasks/{task_id}/approve")
def approve_human_task(
    task_id: str,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    return _record_human_decision(
        task_id,
        decision="approved",
        payload=payload,
        request_id=x_request_id,
    )


@router.post("/human-tasks/{task_id}/reject")
def reject_human_task(
    task_id: str,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    return _record_human_decision(
        task_id,
        decision="rejected",
        payload=payload,
        request_id=x_request_id,
    )


def _record_human_decision(
    task_id: str,
    *,
    decision: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
) -> dict[str, Any]:
    task = _COLLECTIONS["human_tasks"].setdefault(
        task_id,
        {
            "id": task_id,
            "status": "pending",
            "created_at": _now(),
            "metadata": {},
        },
    )
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
        "key_prefix": record.id[:8],
        "scopes": sorted(record.scopes),
        "status": record.status,
        "created_by": record.created_by,
        "created_at": record.created_at.isoformat(),
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
    }


@router.get("/identity/service-accounts")
def list_identity_service_accounts(x_request_id: RequestIdHeader = None) -> dict[str, Any]:
    service_accounts = default_api_key_authenticator().service_accounts.list()
    items = [_serialize_service_account(record) for record in service_accounts]
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.post("/identity/service-accounts", status_code=201)
def create_identity_service_account(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    tenant_id, project_id, _ = _default_scope()
    record = default_api_key_authenticator().service_accounts.create(
        tenant_id=str(data.get("tenant_id") or tenant_id),
        project_id=str(data.get("project_id") or project_id),
        name=str(data.get("name") or "Service Account"),
        permissions=set(data.get("permissions") or ["agent:read"]),
        created_by="console",
    )
    return {"item": _serialize_service_account(record), "request_id": x_request_id}


@router.patch("/identity/service-accounts/{service_account_id}")
def update_identity_service_account(
    service_account_id: str,
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
    if data.get("status") is not None:
        registry.set_status(service_account_id, str(data["status"]))
        if record.status != "active":
            for key in default_api_key_authenticator().list_keys(
                owner_type="service_account",
                owner_id=service_account_id,
            ):
                default_api_key_authenticator().disable_key(key.id, actor_id="console")
    return {"item": _serialize_service_account(record), "request_id": x_request_id}


@router.get("/identity/service-accounts/{service_account_id}/api-keys")
def list_identity_service_account_api_keys(
    service_account_id: str,
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    try:
        default_api_key_authenticator().service_accounts.get(service_account_id)
    except KeyError:
        return _machine_identity_not_found(
            "service_accounts",
            service_account_id,
            x_request_id,
            response,
        )
    keys = default_api_key_authenticator().list_keys(
        owner_type="service_account",
        owner_id=service_account_id,
    )
    items = [_serialize_api_key(record) for record in keys]
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.post("/identity/service-accounts/{service_account_id}/api-keys", status_code=201)
def create_identity_service_account_api_key(
    service_account_id: str,
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
    try:
        plain_key, record = default_api_key_authenticator().create_key(
            tenant_id=owner.tenant_id,
            project_id=owner.project_id,
            name=str(data.get("name") or "API Key"),
            owner_type="service_account",
            owner_id=service_account_id,
            scopes=set(data.get("scopes") or []),
            created_by="console",
        )
    except APIKeyScopeError as exc:
        response.status_code = 403
        return {
            "error_code": str(exc),
            "message": "API key scopes must be a subset of the service account permissions.",
            "request_id": x_request_id,
            "details": {"service_account_id": service_account_id},
        }
    return {
        "item": _serialize_api_key(record),
        "plain_key": plain_key,
        "request_id": x_request_id,
    }


@router.post("/identity/service-accounts/{service_account_id}/api-keys/{key_id}/disable")
def disable_identity_service_account_api_key(
    service_account_id: str,
    key_id: str,
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    record = next(
        (
            key
            for key in default_api_key_authenticator().keys.values()
            if key.id == key_id
            and key.owner_type == "service_account"
            and key.owner_id == service_account_id
        ),
        None,
    )
    if record is None:
        return _machine_identity_not_found("api_keys", key_id, x_request_id, response)
    default_api_key_authenticator().disable_key(key_id, actor_id="console")
    return {"item": _serialize_api_key(record), "request_id": x_request_id}


def register_collection_routes(path: str, collection: str) -> None:
    async def get_items(
        x_request_id: RequestIdHeader = None,
        x_tenant_id: TenantIdHeader = None,
        x_project_id: ProjectIdHeader = None,
    ) -> dict[str, Any]:
        return _list(collection, x_request_id, x_tenant_id, x_project_id)

    async def create_item(
        response: Response,
        payload: AdminPayload = None,
        x_request_id: RequestIdHeader = None,
    ) -> dict[str, Any]:
        return _create(collection, payload, x_request_id, response)

    async def update_item(
        resource_id: str,
        response: Response,
        payload: AdminPayload = None,
        x_request_id: RequestIdHeader = None,
    ) -> dict[str, Any]:
        return _update(collection, resource_id, payload, x_request_id, response)

    async def delete_item(
        resource_id: str,
        response: Response,
        x_request_id: RequestIdHeader = None,
    ) -> dict[str, Any]:
        return _delete(collection, resource_id, x_request_id, response)

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
    ("/service-accounts", "service_accounts"),
    ("/api-keys", "api_keys"),
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
def list_catalog_items(x_request_id: RequestIdHeader = None) -> dict[str, Any]:
    return _list("catalog_items", x_request_id)


@router.post("/catalog/items", status_code=201)
def create_catalog_item(
    response: Response,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    return _create("catalog_items", payload, x_request_id, response)


@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge_incident(
    incident_id: str,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    return _record_incident_decision(
        incident_id,
        status="acknowledged",
        payload=payload,
        request_id=x_request_id,
    )


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(
    incident_id: str,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    return _record_incident_decision(
        incident_id,
        status="resolved",
        payload=payload,
        request_id=x_request_id,
    )


def _record_incident_decision(
    incident_id: str,
    *,
    status: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
) -> dict[str, Any]:
    incident = _COLLECTIONS["incidents"].setdefault(
        incident_id,
        {
            "id": incident_id,
            "status": "open",
            "created_at": _now(),
            "metadata": {},
        },
    )
    incident["status"] = status
    incident["decision_payload"] = dict((payload or {}).get("decision_payload") or {})
    incident["updated_at"] = _now()
    return {"item": incident, "request_id": request_id}
