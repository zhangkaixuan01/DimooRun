from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends

from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
)

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]
_SECRET_REFS: dict[tuple[int | None, int | None, str], str] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _valid_ref(value: object) -> bool:
    return isinstance(value, str) and "://" in value and not value.startswith("plaintext")


def _secret_key(
    tenant_id: int | None,
    project_id: int | None,
    name: str,
) -> tuple[int | None, int | None, str]:
    return (tenant_id, project_id, name)


@router.post("/v1/secrets/validate")
def validate_secret(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    name = str(data.get("name") or "")
    ref = str(data.get("ref") or "")
    key = _secret_key(x_tenant_id, x_project_id, name)
    if _valid_ref(ref):
        _SECRET_REFS[key] = ref
    raw_access_context = data.get("access_context")
    access_context = raw_access_context if isinstance(raw_access_context, dict) else {}
    disabled_action_reason = None if _valid_ref(ref) else "secret_ref_must_use_external_uri"
    return {
        "validation": {
            "valid": _valid_ref(ref),
            "provider": data.get("provider") or "external",
            "ref": ref,
            "disabled_action_reason": disabled_action_reason,
        },
        "secret_value": None,
        "last_used": {
            "at": _now(),
            "used_by": access_context.get("used_by"),
        },
        "access_audit": {
            "action": "secret.validate",
            "resource_type": "secret",
            "resource_id": name,
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
    }


@router.post("/v1/secrets/rotate")
def rotate_secret(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    name = str(data.get("name") or "")
    ref = str(data.get("ref") or "")
    key = _secret_key(x_tenant_id, x_project_id, name)
    previous_ref = _SECRET_REFS.get(key)
    valid_ref = _valid_ref(ref)
    current_ref = ref if valid_ref else previous_ref
    if valid_ref:
        _SECRET_REFS[key] = ref
    rotation: dict[str, Any] = {
        "status": "rotated" if valid_ref else "blocked",
        "previous_ref": previous_ref,
        "current_ref": current_ref,
        "reason": data.get("rotation_reason"),
    }
    if not valid_ref:
        rotation["rejected_ref"] = ref
        rotation["disabled_action_reason"] = "secret_ref_must_use_external_uri"
    return {
        "rotation": rotation,
        "last_used": {
            "at": _now(),
            "used_by": data.get("name"),
        },
        "access_audit": {
            "action": "secret.rotate",
            "resource_type": "secret",
            "resource_id": name,
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
    }
