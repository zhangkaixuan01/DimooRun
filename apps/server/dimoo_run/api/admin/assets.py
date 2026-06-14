from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
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
    AssetKind,
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


def _kind_label(kind: AssetKind) -> str:
    return {
        "prompt": "prompt_asset",
        "config": "config_asset",
        "template": "template_asset",
    }[kind]


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
    kind: AssetKind,
    asset_id: int,
    tenant_id: int,
    project_id: int,
    request_id: str | None,
) -> Any:
    record = find_asset(
        session,
        kind=kind,
        asset_id=asset_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    if record is None:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": f"{_kind_label(kind)}_not_found",
                "message": f"{_kind_label(kind)} was not found in scope.",
                "request_id": request_id,
            },
        )
    return record


def _detail(kind: AssetKind, path: str) -> Any:
    @router.get(path)
    def _handler(
        asset_id: int,
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
                kind=kind,
                asset_id=asset_id,
                tenant_id=tenant_id,
                project_id=project_id,
                request_id=x_request_id,
            )
            if isinstance(record, JSONResponse):
                return record
            return asset_detail(session, kind=kind, record=record, environment=x_environment)
        finally:
            session.close()


def _validate(kind: AssetKind, path: str) -> Any:
    @router.post(path)
    def _handler(
        asset_id: int,
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
        tenant_id, project_id = scoped
        session = _session()
        try:
            record = _get_record(
                session,
                kind=kind,
                asset_id=asset_id,
                tenant_id=tenant_id,
                project_id=project_id,
                request_id=x_request_id,
            )
            if isinstance(record, JSONResponse):
                return record
            result = validate_asset(
                session,
                kind=kind,
                record=record,
                actor_id=actor.actor_id if actor else None,
                audit_reason=str((payload or {}).get("audit_reason") or "").strip() or None,
                environment=x_environment,
            )
            session.commit()
            return result
        except AssetLifecycleError as exc:
            session.rollback()
            return _error(exc, x_request_id)
        finally:
            session.close()


def _write(kind: AssetKind, path: str, action: str) -> Any:
    @router.post(path)
    def _handler(
        asset_id: int,
        payload: AdminPayload = None,
        actor: Annotated[AuthenticatedActor | None, Depends(enforce_console_actor)] = None,
        x_request_id: RequestIdHeader = None,
        x_tenant_id: TenantIdHeader = None,
        x_project_id: ProjectIdHeader = None,
    ) -> Any:
        scoped = _scope(x_tenant_id, x_project_id, x_request_id)
        if isinstance(scoped, JSONResponse):
            return scoped
        data = payload or {}
        reason = _audit_reason(data, x_request_id)
        if isinstance(reason, JSONResponse):
            return reason
        tenant_id, project_id = scoped
        session = _session()
        try:
            record = _get_record(
                session,
                kind=kind,
                asset_id=asset_id,
                tenant_id=tenant_id,
                project_id=project_id,
                request_id=x_request_id,
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
                    kind=kind,
                    record=record,
                    actor_id=actor.actor_id if actor else None,
                    audit_reason=reason,
                )
            elif action == "deprecate":
                result = deprecate_asset(
                    session,
                    kind=kind,
                    record=record,
                    actor_id=actor.actor_id if actor else None,
                    audit_reason=reason,
                )
            elif action == "archive":
                result = archive_asset(
                    session,
                    kind=kind,
                    record=record,
                    actor_id=actor.actor_id if actor else None,
                    audit_reason=reason,
                )
            else:
                result = rollback_asset(
                    session,
                    kind=kind,
                    record=record,
                    actor_id=actor.actor_id if actor else None,
                    audit_reason=reason,
                    target_version=str(data.get("target_version") or "").strip() or None,
                )
            session.commit()
            return result
        except AssetLifecycleError as exc:
            session.rollback()
            return _error(exc, x_request_id)
        finally:
            session.close()


_detail("prompt", "/v1/assets/prompts/{asset_id}")
_detail("config", "/v1/assets/configs/{asset_id}")
_detail("template", "/v1/assets/templates/{asset_id}")

_validate("prompt", "/v1/assets/prompts/{asset_id}/validate")
_validate("config", "/v1/assets/configs/{asset_id}/validate")
_validate("template", "/v1/assets/templates/{asset_id}/validate")

_write("prompt", "/v1/assets/prompts/{asset_id}/approve", "approve")
_write("config", "/v1/assets/configs/{asset_id}/approve", "approve")
_write("template", "/v1/assets/templates/{asset_id}/approve", "approve")

_write("prompt", "/v1/assets/prompts/{asset_id}/publish", "publish")
_write("config", "/v1/assets/configs/{asset_id}/publish", "publish")
_write("template", "/v1/assets/templates/{asset_id}/publish", "publish")

_write("prompt", "/v1/assets/prompts/{asset_id}/deprecate", "deprecate")
_write("config", "/v1/assets/configs/{asset_id}/deprecate", "deprecate")
_write("template", "/v1/assets/templates/{asset_id}/deprecate", "deprecate")

_write("prompt", "/v1/assets/prompts/{asset_id}/archive", "archive")
_write("config", "/v1/assets/configs/{asset_id}/archive", "archive")
_write("template", "/v1/assets/templates/{asset_id}/archive", "archive")

_write("prompt", "/v1/assets/prompts/{asset_id}/rollback", "rollback")
_write("config", "/v1/assets/configs/{asset_id}/rollback", "rollback")
_write("template", "/v1/assets/templates/{asset_id}/rollback", "rollback")
