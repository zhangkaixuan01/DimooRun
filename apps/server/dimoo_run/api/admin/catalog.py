from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
)
from dimoo_run.catalog.asset_lifecycle import (
    AssetLifecycleError,
    approve_asset,
    archive_asset,
    asset_detail,
    deprecate_asset,
    find_asset,
    publish_asset,
    rollback_asset,
    validate_asset,
)
from dimoo_run.core.config import Settings
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.security.api_keys import AuthenticatedActor

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]


def _session() -> Session:
    session_factory = create_session_factory(Settings.from_env().database.url)
    session = session_factory()
    if Settings.from_env().runtime.mode == "dev":
        Base.metadata.create_all(session.get_bind())
    return session


def _scope(
    tenant_id: int | None,
    project_id: int | None,
    request_id: str | None,
) -> tuple[int, int] | JSONResponse:
    if tenant_id is not None and project_id is not None:
        return tenant_id, project_id
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "scope_headers_required",
            "message": "X-Tenant-Id and X-Project-Id are required.",
            "request_id": request_id,
        },
    )


def _audit_reason(payload: dict[str, Any], request_id: str | None) -> str | JSONResponse:
    reason = str(payload.get("audit_reason") or "").strip()
    if reason:
        return reason
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "audit_reason_required",
            "message": "Asset lifecycle writes require an audit_reason.",
            "request_id": request_id,
            "details": {"field": "audit_reason"},
        },
    )


def _error(exc: AssetLifecycleError, request_id: str | None) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.code,
            "message": exc.message,
            "request_id": request_id,
        },
    )


def _get_record(
    session: Session,
    *,
    item_id: int,
    tenant_id: int,
    project_id: int,
    request_id: str | None,
) -> Any:
    record = find_asset(
        session,
        kind="catalog",
        asset_id=item_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    if record is None:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "catalog_item_not_found",
                "message": "Catalog item was not found in scope.",
                "request_id": request_id,
            },
        )
    return record


@router.get("/v1/catalog/items/{item_id}")
def get_catalog_item_detail(
    item_id: int,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    scoped = _scope(x_tenant_id, x_project_id, x_request_id)
    if isinstance(scoped, JSONResponse):
        return scoped
    tenant_id, project_id = scoped
    session = _session()
    try:
        record = _get_record(
            session,
            item_id=item_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=x_request_id,
        )
        if isinstance(record, JSONResponse):
            return record
        return asset_detail(
            session,
            kind="catalog",
            record=record,
            environment=x_environment,
        )
    finally:
        session.close()


@router.post("/v1/catalog/items/{item_id}/validate")
def validate_catalog_item(
    item_id: int,
    payload: AdminPayload = None,
    actor: Annotated[AuthenticatedActor | None, Depends(enforce_console_actor)] = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    scoped = _scope(x_tenant_id, x_project_id, x_request_id)
    if isinstance(scoped, JSONResponse):
        return scoped
    data = payload or {}
    tenant_id, project_id = scoped
    session = _session()
    try:
        record = _get_record(
            session,
            item_id=item_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=x_request_id,
        )
        if isinstance(record, JSONResponse):
            return record
        result = validate_asset(
            session,
            kind="catalog",
            record=record,
            actor_id=actor.actor_id if actor else None,
            audit_reason=str(data.get("audit_reason") or "").strip() or None,
            environment=x_environment,
        )
        session.commit()
        return result
    except AssetLifecycleError as exc:
        session.rollback()
        return _error(exc, x_request_id)
    finally:
        session.close()


def _catalog_lifecycle_write(
    *,
    action: str,
    item_id: int,
    payload: dict[str, Any],
    actor: AuthenticatedActor | None,
    request_id: str | None,
    tenant_id: int,
    project_id: int,
) -> Any:
    reason = _audit_reason(payload, request_id)
    if isinstance(reason, JSONResponse):
        return reason
    session = _session()
    try:
        record = _get_record(
            session,
            item_id=item_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
        )
        if isinstance(record, JSONResponse):
            return record
        if action == "approve":
            result = approve_asset(
                session,
                record=record,
                actor_id=actor.actor_id if actor else None,
                audit_reason=reason,
            )
        elif action == "publish":
            result = publish_asset(
                session,
                kind="catalog",
                record=record,
                actor_id=actor.actor_id if actor else None,
                audit_reason=reason,
            )
        elif action == "deprecate":
            result = deprecate_asset(
                session,
                kind="catalog",
                record=record,
                actor_id=actor.actor_id if actor else None,
                audit_reason=reason,
            )
        elif action == "archive":
            result = archive_asset(
                session,
                kind="catalog",
                record=record,
                actor_id=actor.actor_id if actor else None,
                audit_reason=reason,
            )
        else:
            result = rollback_asset(
                session,
                kind="catalog",
                record=record,
                actor_id=actor.actor_id if actor else None,
                audit_reason=reason,
                target_version=str(payload.get("target_version") or "").strip() or None,
            )
        session.commit()
        return result
    except AssetLifecycleError as exc:
        session.rollback()
        return _error(exc, request_id)
    finally:
        session.close()


@router.post("/v1/catalog/items/{item_id}/approve", status_code=status.HTTP_200_OK)
def approve_catalog_item(
    item_id: int,
    payload: AdminPayload = None,
    actor: Annotated[AuthenticatedActor | None, Depends(enforce_console_actor)] = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    scoped = _scope(x_tenant_id, x_project_id, x_request_id)
    if isinstance(scoped, JSONResponse):
        return scoped
    tenant_id, project_id = scoped
    return _catalog_lifecycle_write(
        action="approve",
        item_id=item_id,
        payload=payload or {},
        actor=actor,
        request_id=x_request_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )


@router.post("/v1/catalog/items/{item_id}/publish")
def publish_catalog_item(
    item_id: int,
    payload: AdminPayload = None,
    actor: Annotated[AuthenticatedActor | None, Depends(enforce_console_actor)] = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    scoped = _scope(x_tenant_id, x_project_id, x_request_id)
    if isinstance(scoped, JSONResponse):
        return scoped
    tenant_id, project_id = scoped
    return _catalog_lifecycle_write(
        action="publish",
        item_id=item_id,
        payload=payload or {},
        actor=actor,
        request_id=x_request_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )


@router.post("/v1/catalog/items/{item_id}/deprecate")
def deprecate_catalog_item(
    item_id: int,
    payload: AdminPayload = None,
    actor: Annotated[AuthenticatedActor | None, Depends(enforce_console_actor)] = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    scoped = _scope(x_tenant_id, x_project_id, x_request_id)
    if isinstance(scoped, JSONResponse):
        return scoped
    tenant_id, project_id = scoped
    return _catalog_lifecycle_write(
        action="deprecate",
        item_id=item_id,
        payload=payload or {},
        actor=actor,
        request_id=x_request_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )


@router.post("/v1/catalog/items/{item_id}/archive")
def archive_catalog_item(
    item_id: int,
    payload: AdminPayload = None,
    actor: Annotated[AuthenticatedActor | None, Depends(enforce_console_actor)] = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    scoped = _scope(x_tenant_id, x_project_id, x_request_id)
    if isinstance(scoped, JSONResponse):
        return scoped
    tenant_id, project_id = scoped
    return _catalog_lifecycle_write(
        action="archive",
        item_id=item_id,
        payload=payload or {},
        actor=actor,
        request_id=x_request_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )


@router.post("/v1/catalog/items/{item_id}/rollback")
def rollback_catalog_item(
    item_id: int,
    payload: AdminPayload = None,
    actor: Annotated[AuthenticatedActor | None, Depends(enforce_console_actor)] = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    scoped = _scope(x_tenant_id, x_project_id, x_request_id)
    if isinstance(scoped, JSONResponse):
        return scoped
    tenant_id, project_id = scoped
    return _catalog_lifecycle_write(
        action="rollback",
        item_id=item_id,
        payload=payload or {},
        actor=actor,
        request_id=x_request_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )
