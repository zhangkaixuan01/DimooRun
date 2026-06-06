from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
)

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]
ALLOWED_STORAGE_REF_SCHEMES = ["s3://", "minio://"]
ALLOWED_BACKUP_TARGETS = ["audit_logs", "datasets", "events", "runs", "tasks"]
ALLOWED_RESTORE_SCOPES = ["organization", "tenant", "project", "environment"]
BACKUP_REF_PREFIX = "backup://"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _targets(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if isinstance(item, str) and item.strip() and item.strip() == item
    ]


def _invalid_target_items(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [str(value)]
    return [
        str(item)
        for item in value
        if not isinstance(item, str) or not item.strip() or item.strip() != item
    ]


def _optional_int(value: Any) -> int | None | bool:
    if value is None:
        return None
    if isinstance(value, bool):
        return False
    if isinstance(value, float):
        return False
    if isinstance(value, str):
        if value.strip() != value or not value.isdigit():
            return False
        if len(value) > 1 and value.startswith("0"):
            return False
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return False
    if parsed <= 0:
        return False
    return parsed


def _normalized_optional_int(value: Any) -> int | None:
    parsed = _optional_int(value.strip() if isinstance(value, str) else value)
    if parsed is False:
        return None
    return parsed


def _storage_ref_valid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    ref = value.strip()
    if ref != value:
        return False
    return any(ref.startswith(scheme) for scheme in ALLOWED_STORAGE_REF_SCHEMES) and (
        _storage_ref_identity_present(value) is True
    )


def _normalized_storage_ref(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip()


def _storage_ref_identity_present(value: Any) -> bool:
    normalized = _normalized_storage_ref(value)
    if normalized is None:
        return False
    for scheme in ALLOWED_STORAGE_REF_SCHEMES:
        if normalized.startswith(scheme):
            identity_parts = normalized[len(scheme) :].split("/")
            return (
                len(identity_parts) >= 2
                and all(part.strip() for part in identity_parts)
                and not any(part.strip() in {".", ".."} for part in identity_parts)
                and not any("?" in part or "#" in part for part in identity_parts)
            )
    return False


def _unsupported_backup_targets(targets: list[str]) -> list[str]:
    allowed = set(ALLOWED_BACKUP_TARGETS)
    return [target for target in targets if target not in allowed]


def _duplicate_targets(targets: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for target in targets:
        if target in seen and target not in duplicates:
            duplicates.append(target)
        seen.add(target)
    return duplicates


def _optional_bool_valid(value: Any) -> bool:
    return value is None or isinstance(value, bool)


def _optional_scope(value: Any, *, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        return str(value)
    return value


def _normalized_scope(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _scope_proof(
    *,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "environment": environment,
        "proof_generated_at": _now(),
    }


def _backup_scope_proof(
    *,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
    scope: str,
) -> dict[str, Any]:
    return {
        **_scope_proof(
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        ),
        "backup_scope": scope,
    }


def _restore_scope_proof(
    *,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
    scope: str,
) -> dict[str, Any]:
    return {
        **_scope_proof(
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        ),
        "restore_scope": scope,
    }


def _missing_scope_headers(
    *,
    project_id: int | None,
    environment: str | None,
    scope: str,
) -> list[str]:
    if scope == "project" and project_id is None:
        return ["X-Project-Id"]
    if scope == "environment" and not environment:
        return ["X-Environment"]
    return []


def _scope_from_backup_ref(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.rstrip("/").rsplit("/", maxsplit=1)[-1]
    if candidate in set(ALLOWED_RESTORE_SCOPES):
        return candidate
    return None


def _backup_ref_valid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    ref = value.strip()
    if ref != value:
        return False
    return ref.startswith(BACKUP_REF_PREFIX) and _backup_ref_identity_present(value)


def _normalized_backup_ref(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip()


def _backup_ref_identity_present(value: Any) -> bool:
    normalized = _normalized_backup_ref(value)
    if normalized is None or not normalized.startswith(BACKUP_REF_PREFIX):
        return False
    raw_identity = normalized[len(BACKUP_REF_PREFIX) :]
    if raw_identity.endswith("/"):
        return False
    identity = normalized[len(BACKUP_REF_PREFIX) :].strip("/")
    if not identity:
        return False
    identity_parts = identity.split("/")
    if any(not part.strip() for part in identity_parts):
        return False
    if any(part.strip() in {".", ".."} for part in identity_parts):
        return False
    if any("?" in part or "#" in part for part in identity_parts):
        return False
    scope = _scope_from_backup_ref(normalized)
    if scope is None:
        return bool(identity)
    prefix = identity[: -len(scope)].strip("/")
    return bool(prefix)


def _restore_confirmation_phrase(
    *,
    scope: str,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> str:
    match scope:
        case "tenant":
            return f"RESTORE TENANT {tenant_id or 0}"
        case "environment":
            return f"RESTORE ENVIRONMENT {environment or 'unknown'}"
        case "organization":
            return "RESTORE ORGANIZATION"
        case _:
            return f"RESTORE PROJECT {project_id or 0}"


@router.post("/v1/backups/dry-run")
def dry_run_backup(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    data = payload or {}
    targets = _targets(data.get("targets"))
    plan_id = _optional_int(data.get("plan_id"))
    plan_id_valid = plan_id is not False
    scope = _optional_scope(data.get("scope"), default="project")
    scope_valid = scope in ALLOWED_RESTORE_SCOPES
    missing_scope_headers = _missing_scope_headers(
        project_id=x_project_id,
        environment=x_environment,
        scope=scope,
    )
    targets_selected = bool(targets)
    storage_ref_valid = _storage_ref_valid(data.get("storage_ref"))
    unsupported_targets = _unsupported_backup_targets(targets)
    invalid_targets = _invalid_target_items(data.get("targets"))
    duplicate_targets = _duplicate_targets(targets)
    valid = (
        not missing_scope_headers
        and plan_id_valid
        and scope_valid
        and targets_selected
        and storage_ref_valid
        and not invalid_targets
        and not unsupported_targets
        and not duplicate_targets
    )
    body = {
        "status": "ready" if valid else "blocked",
        "plan_id": plan_id,
        "targets": targets,
        "storage_ref": data.get("storage_ref"),
        "scope_proof": _backup_scope_proof(
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            environment=x_environment,
            scope=scope,
        ),
        "validation": {
            "valid": valid,
            "checks": [
                "scope_headers_present",
                "plan_id_valid",
                "storage_ref_present",
                "targets_selected",
            ],
            "missing_scope_headers": missing_scope_headers,
            "plan_id_valid": plan_id_valid,
            "plan_id_normalized": _normalized_optional_int(data.get("plan_id")),
            "scope_valid": scope_valid,
            "scope_normalized": _normalized_scope(data.get("scope")),
            "allowed_scopes": ALLOWED_RESTORE_SCOPES,
            "storage_ref_valid": storage_ref_valid,
            "storage_ref_normalized": _normalized_storage_ref(data.get("storage_ref")),
            "storage_ref_identity_present": _storage_ref_identity_present(
                data.get("storage_ref")
            ),
            "allowed_storage_ref_schemes": ALLOWED_STORAGE_REF_SCHEMES,
            "targets_selected": targets_selected,
            "invalid_targets": invalid_targets,
            "unsupported_targets": unsupported_targets,
            "duplicate_targets": duplicate_targets,
            "allowed_targets": ALLOWED_BACKUP_TARGETS,
        },
        "disabled_action_reason": (
            "scope_headers_required"
            if missing_scope_headers
            else "backup_plan_id_invalid"
            if not plan_id_valid
            else "backup_scope_invalid"
            if not scope_valid
            else "storage_ref_invalid"
            if not storage_ref_valid
            else "backup_targets_invalid"
            if invalid_targets or unsupported_targets
            else "backup_targets_required"
            if not targets_selected
            else "backup_targets_duplicate"
            if duplicate_targets
            else None
        ),
        "audit": {
            "action": "backup.dry_run",
            "resource_type": "backup_plan",
            "resource_id": plan_id,
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
        "request_id": x_request_id,
    }
    if missing_scope_headers:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "backup_scope_headers_required",
                "message": "Scoped backup dry-run requires explicit scope headers.",
                **body,
            },
        )
    if not plan_id_valid:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "backup_plan_id_invalid",
                "message": "Backup dry-run plan_id must be an integer when provided.",
                **body,
            },
        )
    if not scope_valid:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "backup_scope_invalid",
                "message": "Backup dry-run requires a supported scope.",
                **body,
            },
        )
    if not storage_ref_valid:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "backup_storage_ref_invalid",
                "message": "Backup dry-run requires a durable object storage reference.",
                **body,
            },
        )
    if invalid_targets or unsupported_targets:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "backup_targets_invalid",
                "message": "Backup dry-run includes unsupported targets.",
                **body,
            },
        )
    if not targets_selected:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "backup_targets_required",
                "message": "Backup dry-run requires at least one target.",
                **body,
            },
        )
    if duplicate_targets:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "backup_targets_duplicate",
                "message": "Backup dry-run targets must not contain duplicates.",
                **body,
            },
        )
    return body


@router.post("/v1/backups/restore-dry-run")
def dry_run_restore(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    data = payload or {}
    restore_scope = _optional_scope(data.get("restore_scope"), default="project")
    restore_scope_valid = restore_scope in ALLOWED_RESTORE_SCOPES
    missing_scope_headers = _missing_scope_headers(
        project_id=x_project_id,
        environment=x_environment,
        scope=restore_scope,
    )
    backup_ref_valid = _backup_ref_valid(data.get("backup_ref"))
    backup_scope = _scope_from_backup_ref(data.get("backup_ref"))
    backup_ref_scope_present = backup_scope is not None
    scope_matches_backup = backup_scope == restore_scope
    targets = _targets(data.get("targets"))
    targets_selected = bool(targets)
    unsupported_targets = _unsupported_backup_targets(targets)
    invalid_targets = _invalid_target_items(data.get("targets"))
    duplicate_targets = _duplicate_targets(targets)
    destructive_valid = _optional_bool_valid(data.get("destructive"))
    destructive = data.get("destructive") is True if destructive_valid else False
    required_confirmation = _restore_confirmation_phrase(
        scope=restore_scope,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
    )
    confirmed = not destructive or data.get("confirmation") == required_confirmation
    validation = {
        "valid": (
            not missing_scope_headers
            and restore_scope_valid
            and backup_ref_valid
            and backup_ref_scope_present
            and scope_matches_backup
            and targets_selected
            and not invalid_targets
            and not unsupported_targets
            and not duplicate_targets
            and destructive_valid
            and confirmed
        ),
        "destructive": destructive,
        "destructive_valid": destructive_valid,
        "destructive_confirmation_required": required_confirmation if destructive else None,
        "checks": [
            "backup_ref_present",
            "scope_headers_present",
            "backup_ref_scope_present",
            "scope_matches_backup",
            "targets_selected",
            "confirmation",
        ],
        "missing_scope_headers": missing_scope_headers,
        "restore_scope_valid": restore_scope_valid,
        "restore_scope_normalized": _normalized_scope(data.get("restore_scope")),
        "allowed_restore_scopes": ALLOWED_RESTORE_SCOPES,
        "backup_ref_valid": backup_ref_valid,
        "allowed_backup_ref_prefix": BACKUP_REF_PREFIX,
        "backup_ref_normalized": _normalized_backup_ref(data.get("backup_ref")),
        "backup_ref_identity_present": _backup_ref_identity_present(data.get("backup_ref")),
        "backup_scope": backup_scope,
        "backup_ref_scope_present": backup_ref_scope_present,
        "restore_scope": restore_scope,
        "targets_selected": targets_selected,
        "invalid_targets": invalid_targets,
        "unsupported_targets": unsupported_targets,
        "duplicate_targets": duplicate_targets,
        "allowed_targets": ALLOWED_BACKUP_TARGETS,
    }
    body = {
        "status": "ready" if validation["valid"] else "blocked",
        "backup_ref": data.get("backup_ref"),
        "targets": targets,
        "scope_proof": _restore_scope_proof(
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            environment=x_environment,
            scope=restore_scope,
        ),
        "validation": validation,
        "disabled_action_reason": (
            "scope_headers_required"
            if missing_scope_headers
            else "restore_scope_invalid"
            if not restore_scope_valid
            else "backup_ref_invalid"
            if not backup_ref_valid
            else "backup_ref_scope_required"
            if not backup_ref_scope_present
            else "restore_scope_mismatch"
            if not scope_matches_backup
            else "restore_targets_invalid"
            if invalid_targets or unsupported_targets
            else "restore_targets_required"
            if not targets_selected
            else "restore_targets_duplicate"
            if duplicate_targets
            else "destructive_flag_invalid"
            if not destructive_valid
            else "destructive_restore_confirmation_required"
            if not confirmed
            else None
        ),
        "audit": {
            "action": "restore.dry_run",
            "resource_type": "restore_job",
            "resource_id": data.get("backup_ref"),
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
        "request_id": x_request_id,
    }
    if missing_scope_headers:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "restore_scope_headers_required",
                "message": "Scoped restore dry-run requires explicit scope headers.",
                **body,
            },
        )
    if not restore_scope_valid:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "restore_scope_invalid",
                "message": "Restore dry-run requires a supported restore_scope.",
                **body,
            },
        )
    if not backup_ref_valid:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "restore_backup_ref_invalid",
                "message": "Restore dry-run requires a backup:// reference.",
                **body,
            },
        )
    if not backup_ref_scope_present:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "restore_backup_ref_scope_required",
                "message": "Restore dry-run requires a backup_ref ending in a supported scope.",
                **body,
            },
        )
    if not scope_matches_backup:
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "restore_scope_mismatch",
                "message": "Restore scope must match the backup reference scope.",
                **body,
            },
        )
    if invalid_targets or unsupported_targets:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "restore_targets_invalid",
                "message": "Restore dry-run includes unsupported targets.",
                **body,
            },
        )
    if not targets_selected:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "restore_targets_required",
                "message": "Restore dry-run requires at least one target.",
                **body,
            },
        )
    if duplicate_targets:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "restore_targets_duplicate",
                "message": "Restore dry-run targets must not contain duplicates.",
                **body,
            },
        )
    if not destructive_valid:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "restore_destructive_flag_invalid",
                "message": "Restore dry-run destructive flag must be a boolean when provided.",
                **body,
            },
        )
    if not confirmed:
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "destructive_restore_confirmation_required",
                "message": "Destructive restore requires the exact confirmation phrase.",
                "details": {"validation": validation},
                **body,
            },
        )
    return body
