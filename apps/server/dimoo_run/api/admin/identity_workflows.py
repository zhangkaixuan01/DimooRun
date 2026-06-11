from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from dimoo_run.api.admin.router import (
    _append_identity_audit,
    _scope_denied,
    _serialize_api_key,
)
from dimoo_run.api.console.common import AuditReasonHeader
from dimoo_run.api.dependencies import (
    RequestIdHeader,
    default_api_key_authenticator,
    enforce_console_actor,
    get_console_operator_by_session,
    revoke_console_session,
)
from dimoo_run.domain.models import (
    ConsoleOperator,
    ConsoleOperatorSession,
    ConsolePermission,
    ConsoleRole,
    ConsoleRolePermission,
)
from dimoo_run.identity.console import default_console_identity_service
from dimoo_run.identity.permission_matrix import role_matrix_preview
from dimoo_run.persistence.database import create_session_factory
from dimoo_run.security.api_keys import AuthenticatedActor

router = APIRouter(
    prefix="/v1/identity/workflows",
    tags=["identity-workflows"],
    dependencies=[Depends(enforce_console_actor)],
)
IdentityPayload = Annotated[dict[str, Any] | None, Body()]


def _session_factory() -> sessionmaker[Session]:
    from dimoo_run.core.config import Settings

    return create_session_factory(Settings.from_env().database.url)


@router.post("/roles/{role_id}/preview", response_model=None)
def preview_role_matrix(
    role_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    payload: IdentityPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    requested = payload or {}
    permission_codes = [str(code) for code in requested.get("permissions") or []]
    with _session_factory()() as session:
        try:
            preview = role_matrix_preview(
                session,
                role_id=role_id,
                permission_codes=permission_codes,
                current_operator_id=int(actor.actor_id) if actor.actor_type == "operator" else None,
            )
        except KeyError:
            return _not_found("role_not_found", "Role was not found.", role_id, x_request_id)
    return {
        "item": {
            "role_id": preview.role_id,
            "role_name": preview.role_name,
            "current_permissions": preview.current_permissions,
            "preview_permissions": preview.preview_permissions,
            "change": {
                "added": preview.change.added,
                "removed": preview.change.removed,
                "unchanged": preview.change.unchanged,
            },
            "affected_operators": [
                {
                    "operator_id": item.operator_id,
                    "email": item.email,
                    "name": item.name,
                    "current_permissions": item.current_permissions,
                    "preview_permissions": item.preview_permissions,
                }
                for item in preview.affected_operators
            ],
            "affected_service_accounts": preview.affected_service_accounts,
            "warnings": preview.warnings,
            "policy_conflicts": [
                warning
                for warning in preview.warnings
                if warning["code"] == "self_lockout_risk"
            ],
        },
        "request_id": x_request_id,
    }


@router.post("/roles/{role_id}/apply", response_model=None)
def apply_role_matrix(
    role_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    payload: IdentityPayload = None,
    x_request_id: RequestIdHeader = None,
    x_audit_reason: AuditReasonHeader = None,
) -> dict[str, Any] | JSONResponse:
    requested = payload or {}
    permission_codes = [str(code) for code in requested.get("permissions") or []]
    if not (x_audit_reason or "").strip():
        return _validation_error(
            "audit_reason_required",
            "Audit reason is required for role permission changes.",
            x_request_id,
            {"field": "audit_reason"},
        )
    with _session_factory()() as session:
        try:
            preview = role_matrix_preview(
                session,
                role_id=role_id,
                permission_codes=permission_codes,
                current_operator_id=int(actor.actor_id) if actor.actor_type == "operator" else None,
            )
        except KeyError:
            return _not_found("role_not_found", "Role was not found.", role_id, x_request_id)
        if any(warning["code"] == "self_lockout_risk" for warning in preview.warnings):
            return JSONResponse(
                status_code=409,
                content={
                    "error_code": "self_lockout_blocked",
                    "message": (
                        "Current operator cannot remove permissions required "
                        "for identity governance."
                    ),
                    "request_id": x_request_id,
                    "details": {"warnings": preview.warnings},
                },
            )
        role = session.get(ConsoleRole, role_id)
        assert role is not None
        session.execute(
            delete(ConsoleRolePermission).where(
                ConsoleRolePermission.role_id == role_id
            )
        )
        for code in preview.preview_permissions:
            permission = session.scalar(
                select(ConsolePermission).where(ConsolePermission.code == code)
            )
            if permission is None:
                resource, action = _permission_parts(code)
                permission = ConsolePermission(
                    code=code,
                    resource=resource,
                    action=action,
                    description=None,
                    status="active",
                    created_at=_now(),
                    updated_at=_now(),
                )
                session.add(permission)
                session.flush()
            session.add(
                ConsoleRolePermission(
                    role_id=role_id,
                    permission_id=permission.id,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
        role.updated_at = _now()
        session.commit()
        _append_identity_audit(
            actor,
            action="identity.role.permissions.apply",
            resource_type="console_role",
            resource_id=role_id,
            request_id=x_request_id,
            metadata={
                "audit_reason": x_audit_reason,
                "added": preview.change.added,
                "removed": preview.change.removed,
            },
        )
        return {
            "item": {
                "role_id": preview.role_id,
                "role_name": preview.role_name,
                "permissions": preview.preview_permissions,
                "change": {
                    "added": preview.change.added,
                    "removed": preview.change.removed,
                    "unchanged": preview.change.unchanged,
                },
                "affected_operators": [
                    {
                        "operator_id": item.operator_id,
                        "email": item.email,
                        "name": item.name,
                    }
                    for item in preview.affected_operators
                ],
            },
            "request_id": x_request_id,
        }


@router.post("/sessions/revoke-self", response_model=None)
def revoke_own_session(
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    payload: IdentityPayload = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    token = str((payload or {}).get("token") or "")
    if not token.startswith("sess_"):
        return _validation_error(
            "session_token_required",
            "A console session token is required to revoke the current session.",
            x_request_id,
            {"field": "token"},
        )
    operator = get_console_operator_by_session(token)
    if operator is None or str(operator.id) != actor.actor_id:
        return JSONResponse(
            status_code=403,
            content={
                "error_code": "session_not_owned",
                "message": "The supplied session does not belong to the current operator.",
                "request_id": x_request_id,
                "details": {},
            },
        )
    revoke_console_session(token)
    _append_identity_audit(
        actor,
        action="identity.session.revoke_self",
        resource_type="console_session",
        resource_id=None,
        request_id=x_request_id,
    )
    return {"ok": True, "request_id": x_request_id}


@router.post("/operators/{operator_id}/sessions/{session_id}/revoke", response_model=None)
def revoke_operator_session(
    operator_id: int,
    session_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    with _session_factory()() as session:
        operator = session.get(ConsoleOperator, operator_id)
        session_model = session.get(ConsoleOperatorSession, session_id)
        if (
            operator is None
            or operator.is_deleted
            or session_model is None
            or session_model.operator_id != operator_id
        ):
            return _not_found(
                "operator_session_not_found",
                "Operator session was not found.",
                session_id,
                x_request_id,
            )
        if (
            actor.actor_type == "operator"
            and str(operator_id) == actor.actor_id
            and _active_identity_admin_session_count(session, operator_id) <= 1
        ):
            return JSONResponse(
                status_code=409,
                content={
                    "error_code": "self_lockout_blocked",
                    "message": "Current operator cannot revoke the last active identity session.",
                    "request_id": x_request_id,
                    "details": {"operator_id": operator_id, "session_id": session_id},
                },
            )
        session_model.revoked_at = _now()
        session_model.revoke_reason = "admin_revoked"
        session_model.updated_at = _now()
        session.commit()
        cache = getattr(default_console_identity_service(), "_cache", None)
        if cache is not None:
            cache.delete(session_model.token_hash)
    _append_identity_audit(
        actor,
        action="identity.session.revoke",
        resource_type="console_session",
        resource_id=session_id,
        request_id=x_request_id,
        metadata={"operator_id": operator_id},
    )
    return {"ok": True, "request_id": x_request_id}


@router.post("/service-accounts/{service_account_id}/api-keys/{key_id}/rotate", response_model=None)
def rotate_service_account_api_key(
    service_account_id: int,
    key_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    payload: IdentityPayload = None,
    x_request_id: RequestIdHeader = None,
    x_audit_reason: AuditReasonHeader = None,
) -> dict[str, Any] | JSONResponse:
    if not (x_audit_reason or "").strip():
        return _validation_error(
            "audit_reason_required",
            "Audit reason is required for API key rotation.",
            x_request_id,
            {"field": "audit_reason"},
        )
    auth = default_api_key_authenticator()
    try:
        owner = auth.service_accounts.get(service_account_id)
    except KeyError:
        return _not_found(
            "service_account_not_found",
            "Service account was not found.",
            service_account_id,
            x_request_id,
        )
    if not _actor_can_access_target(actor, owner.tenant_id, owner.project_id):
        return JSONResponse(
            status_code=403,
            content=_scope_denied(x_request_id, owner.tenant_id, owner.project_id),
        )
    current = _get_api_key_or_none(auth, key_id, service_account_id)
    if current is None:
        return _not_found("api_key_not_found", "API key was not found.", key_id, x_request_id)
    requested = payload or {}
    scopes = set(str(scope) for scope in requested.get("scopes") or current.scopes)
    expires_at = _parse_optional_datetime(requested.get("expires_at")) or current.expires_at
    plain_key, rotated = auth.create_key(
        tenant_id=current.tenant_id,
        project_id=current.project_id,
        name=str(requested.get("name") or f"{current.name}-rotated"),
        owner_type=current.owner_type,
        owner_id=current.owner_id,
        scopes=scopes,
        created_by=actor.actor_id,
        expires_at=expires_at,
    )
    auth.disable_key(key_id, actor_id=actor.actor_id)
    _append_identity_audit(
        actor,
        action="identity.api_key.rotate",
        resource_type="api_key",
        resource_id=rotated.id,
        request_id=x_request_id,
        metadata={
            "audit_reason": x_audit_reason,
            "service_account_id": service_account_id,
            "rotated_from_key_id": key_id,
            "scope_diff": {
                "added": sorted(scopes - current.scopes),
                "removed": sorted(current.scopes - scopes),
                "unchanged": sorted(current.scopes & scopes),
            },
        },
    )
    return {
        "item": _serialize_api_key(rotated),
        "plain_key": plain_key,
        "rotated_from": _serialize_api_key(current),
        "scope_diff": {
            "added": sorted(scopes - current.scopes),
            "removed": sorted(current.scopes - scopes),
            "unchanged": sorted(current.scopes & scopes),
        },
        "request_id": x_request_id,
    }


@router.post(
    "/service-accounts/{service_account_id}/api-keys/{key_id}/force-expire",
    response_model=None,
)
def force_expire_service_account_api_key(
    service_account_id: int,
    key_id: int,
    actor: Annotated[AuthenticatedActor, Depends(enforce_console_actor)],
    x_request_id: RequestIdHeader = None,
    x_audit_reason: AuditReasonHeader = None,
) -> dict[str, Any] | JSONResponse:
    if not (x_audit_reason or "").strip():
        return _validation_error(
            "audit_reason_required",
            "Audit reason is required for API key expiry.",
            x_request_id,
            {"field": "audit_reason"},
        )
    auth = default_api_key_authenticator()
    try:
        owner = auth.service_accounts.get(service_account_id)
    except KeyError:
        return _not_found(
            "service_account_not_found",
            "Service account was not found.",
            service_account_id,
            x_request_id,
        )
    if not _actor_can_access_target(actor, owner.tenant_id, owner.project_id):
        return JSONResponse(
            status_code=403,
            content=_scope_denied(x_request_id, owner.tenant_id, owner.project_id),
        )
    try:
        record = auth.expire_key(key_id, actor_id=actor.actor_id)
    except KeyError:
        return _not_found("api_key_not_found", "API key was not found.", key_id, x_request_id)
    _append_identity_audit(
        actor,
        action="identity.api_key.force_expire",
        resource_type="api_key",
        resource_id=key_id,
        request_id=x_request_id,
        metadata={"audit_reason": x_audit_reason, "service_account_id": service_account_id},
    )
    return {"item": _serialize_api_key(record), "request_id": x_request_id}


def _not_found(
    error_code: str,
    message: str,
    resource_id: int,
    request_id: str | None,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error_code": error_code,
            "message": message,
            "request_id": request_id,
            "details": {"id": resource_id},
        },
    )


def _validation_error(
    error_code: str,
    message: str,
    request_id: str | None,
    details: dict[str, Any],
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error_code": error_code,
            "message": message,
            "request_id": request_id,
            "details": details,
        },
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
    if actor.project_id is not None and project_id is not None and actor.project_id != project_id:
        return False
    return True


def _get_api_key_or_none(authenticator: Any, key_id: int, owner_id: int) -> Any | None:
    return next(
        (
            key
            for key in authenticator.list_keys(owner_type="service_account", owner_id=owner_id)
            if key.id == key_id
        ),
        None,
    )


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _permission_parts(code: str) -> tuple[str, str]:
    if code == "*":
        return "*", "*"
    if ":" in code:
        left, right = code.rsplit(":", 1)
        return left, right
    return code, "use"


def _active_identity_admin_session_count(session: Any, operator_id: int) -> int:
    now = _now()
    return int(
        session.scalar(
            select(func.count())
            .where(
                ConsoleOperatorSession.operator_id == operator_id,
                ConsoleOperatorSession.revoked_at.is_(None),
                ConsoleOperatorSession.expires_at > now,
            )
        )
        or 0
    )
