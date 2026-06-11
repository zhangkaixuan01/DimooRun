import os
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from dimoo_run.core.config import Settings
from dimoo_run.core.startup_checks import validate_production_settings
from dimoo_run.domain.models import (
    AuditLog,
    Deployment,
    PlatformControlSetting,
    PublishedSurface,
    WorkerSnapshot,
)

ScopeKind = Literal["organization", "project", "environment"]

_DEFAULT_CONFIG: dict[ScopeKind, dict[str, Any]] = {
    "organization": {
        "default_runtime_mode": "governed",
        "default_queue": "default",
        "default_artifact_retention_days": 30,
    },
    "project": {
        "default_model_gateway": "default",
        "default_secret_provider": "external",
        "change_review_policy": "two_person",
    },
    "environment": {
        "default_deployment_strategy": "rolling",
        "freeze_writes": False,
        "default_route_visibility": "internal",
    },
}

_DANGEROUS_ACTIONS: dict[str, dict[str, Any]] = {
    "freeze_environment_writes": {
        "scope_kind": "environment",
        "risk_level": "critical",
        "confirmation_template": "freeze {environment} writes",
        "blocked_by": (),
        "rollback_hint": "Disable the freeze after maintenance and redeploy blocked changes.",
    },
    "rotate_object_store_credentials": {
        "scope_kind": "organization",
        "risk_level": "critical",
        "confirmation_template": "rotate object store credentials",
        "blocked_by": ("object_store", "secret_provider"),
        "rollback_hint": "Restore the previous object-store secret ref before retrying uploads.",
    },
}

def build_platform_settings_snapshot(
    session: Session,
    *,
    settings: Settings,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> dict[str, Any]:
    safety_warnings = validate_production_settings(settings)
    scoped = list_scoped_setting_views(
        session,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    project_defaults = _select_scope(scoped, "project")
    environment_defaults = _select_scope(scoped, "environment")
    return {
        "runtime_mode": settings.runtime.mode,
        "runtime_environment": settings.runtime.environment,
        "database_mode": _database_mode(settings.database.url),
        "queue_backend": _queue_backend(settings),
        "object_store": {
            "backend": settings.object_store.backend,
            "endpoint_url": settings.object_store.endpoint_url,
            "bucket": settings.object_store.bucket,
        },
        "secret_provider": {
            "provider": os.getenv("DIMOORUN_SECRET_PROVIDER", "memory"),
            "default_scope": str(
                project_defaults["config"].get("default_secret_provider", "external")
            ),
        },
        "model_gateway_provider": {
            "provider": os.getenv("DIMOORUN_MODEL_GATEWAY_PROVIDER", "builtin"),
            "default_gateway": str(
                project_defaults["config"].get("default_model_gateway", "default")
            ),
        },
        "artifact_retention": {
            "days": int(scoped[0]["config"].get("default_artifact_retention_days", 30)),
            "backend": settings.object_store.backend,
        },
        "trace_retention": {
            "days": int(os.getenv("DIMOORUN_TRACE_RETENTION_DAYS", "14")),
            "exporters": settings.observability.exporters,
        },
        "cors": {
            "origins": settings.console.cors_origins,
            "allow_credentials": True,
        },
        "runtime_write_protected": settings.runtime.mode == "production",
        "production_safety": {
            "status": "safe" if not safety_warnings else "unsafe",
            "warnings": safety_warnings,
        },
        "scope_defaults": scoped,
        "danger_state": {
            "freeze_writes": bool(environment_defaults["config"].get("freeze_writes", False)),
            "updated_at": environment_defaults["updated_at"],
        },
    }


def list_scoped_setting_views(
    session: Session,
    *,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> list[dict[str, Any]]:
    views = [
        _setting_view(
            _ensure_scope_setting(
                session,
                tenant_id=tenant_id,
                project_id=None,
                environment=None,
                scope_kind="organization",
            )
        ),
        _setting_view(
            _ensure_scope_setting(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=None,
                scope_kind="project",
            )
        ),
        _setting_view(
            _ensure_scope_setting(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
                scope_kind="environment",
            )
        ),
    ]
    session.commit()
    return views


def write_scoped_setting(
    session: Session,
    *,
    settings: Settings,
    tenant_id: int,
    project_id: int,
    environment: str,
    scope_kind: ScopeKind,
    config: dict[str, Any],
    actor_id: str,
    request_id: str | None,
    audit_reason: str | None,
) -> dict[str, Any]:
    if settings.runtime.mode == "production" and scope_kind != "environment":
        raise ValueError("Production mode only allows environment-scoped defaults to change.")
    record = _ensure_scope_setting(
        session,
        tenant_id=tenant_id,
        project_id=project_id if scope_kind != "organization" else None,
        environment=environment if scope_kind == "environment" else None,
        scope_kind=scope_kind,
    )
    merged = dict(record.config_json or {})
    merged.update(config)
    record.config_json = merged
    metadata = dict(record.metadata_json or {})
    if audit_reason:
        metadata["last_audit_reason"] = audit_reason
    metadata["last_request_id"] = request_id
    record.metadata_json = metadata
    record.updated_by = actor_id
    session.flush()
    _write_audit(
        session,
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor_id,
        request_id=request_id,
        action=f"platform.settings.{scope_kind}.update",
        resource_id=record.id,
        metadata={
            "scope_kind": scope_kind,
            "config": config,
            "audit_reason": audit_reason or "",
        },
    )
    session.commit()
    return _setting_view(record)


def build_dangerous_action_preview(
    session: Session,
    *,
    settings: Settings,
    tenant_id: int,
    project_id: int,
    environment: str,
    action: str,
) -> dict[str, Any]:
    spec = _DANGEROUS_ACTIONS.get(action)
    if spec is None:
        raise KeyError(action)
    providers = {
        item["provider"]: item
        for item in _provider_snapshots_for_preflight(
            session,
            settings=settings,
            tenant_id=tenant_id,
            project_id=project_id,
        )
    }
    blocked_reasons: list[str] = []
    for provider_name in spec["blocked_by"]:
        status = str(providers.get(provider_name, {}).get("status", "offline"))
        if status not in {"healthy", "ready"}:
            blocked_reasons.append(f"{provider_name} is not healthy enough for this action.")
    confirmation_phrase = str(spec["confirmation_template"]).format(environment=environment)
    affected = _affected_resources(
        session,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    return {
        "action": action,
        "scope_kind": spec["scope_kind"],
        "risk_level": spec["risk_level"],
        "available": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "confirmation_phrase": confirmation_phrase,
        "affected_resources": affected,
        "rollback_notes": spec["rollback_hint"],
        "audit_required": True,
    }


def apply_dangerous_action(
    session: Session,
    *,
    settings: Settings,
    tenant_id: int,
    project_id: int,
    environment: str,
    action: str,
    confirmation: str,
    rollback_notes: str,
    audit_reason: str,
    actor_id: str,
    request_id: str | None,
) -> dict[str, Any]:
    preview = build_dangerous_action_preview(
        session,
        settings=settings,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        action=action,
    )
    if not preview["available"]:
        raise RuntimeError(str(preview["blocked_reasons"][0]))
    if confirmation.strip() != preview["confirmation_phrase"]:
        raise ValueError("Confirmation phrase does not match.")
    if not audit_reason.strip():
        raise ValueError("Audit reason is required.")
    if not rollback_notes.strip():
        raise ValueError("Rollback notes are required.")
    if action == "freeze_environment_writes":
        setting = write_scoped_setting(
            session,
            settings=settings,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
            scope_kind="environment",
            config={"freeze_writes": True},
            actor_id=actor_id,
            request_id=request_id,
            audit_reason=audit_reason,
        )
        return {
            "action": action,
            "status": "applied",
            "scope_setting": setting,
            "rollback_notes": rollback_notes,
            "request_id": request_id,
        }
    if action == "rotate_object_store_credentials":
        _write_audit(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor_id,
            request_id=request_id,
            action="platform.settings.object_store.rotate",
            resource_id=None,
            metadata={"rollback_notes": rollback_notes, "audit_reason": audit_reason},
        )
        session.commit()
        return {
            "action": action,
            "status": "planned",
            "request_id": request_id,
            "rollback_notes": rollback_notes,
        }
    raise KeyError(action)


def _database_mode(database_url: str) -> str:
    if database_url.startswith("sqlite"):
        return "sqlite"
    if database_url.startswith("postgresql"):
        return "postgresql"
    return "external"


def _queue_backend(settings: Settings) -> str:
    return os.getenv(
        "DIMOORUN_QUEUE_BACKEND",
        "redis" if settings.runtime.native_runtime_store == "sqlalchemy" else "memory",
    )


def _ensure_scope_setting(
    session: Session,
    *,
    tenant_id: int,
    project_id: int | None,
    environment: str | None,
    scope_kind: ScopeKind,
) -> PlatformControlSetting:
    statement: Select[tuple[PlatformControlSetting]] = select(PlatformControlSetting).where(
        PlatformControlSetting.tenant_id == tenant_id,
        PlatformControlSetting.project_id == project_id,
        PlatformControlSetting.environment == environment,
        PlatformControlSetting.scope_kind == scope_kind,
        PlatformControlSetting.setting_key == "defaults",
        PlatformControlSetting.is_deleted.is_(False),
    )
    record = session.scalar(statement)
    if record is not None:
        return record
    record = PlatformControlSetting(
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        scope_kind=scope_kind,
        setting_key="defaults",
        config_json=dict(_DEFAULT_CONFIG[scope_kind]),
        metadata_json={"seeded": True},
    )
    session.add(record)
    session.flush()
    return record


def _setting_view(record: PlatformControlSetting) -> dict[str, Any]:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "project_id": record.project_id,
        "environment": record.environment,
        "scope_kind": record.scope_kind,
        "setting_key": record.setting_key,
        "config": dict(record.config_json or {}),
        "metadata": dict(record.metadata_json or {}),
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _select_scope(items: Sequence[dict[str, Any]], scope_kind: ScopeKind) -> dict[str, Any]:
    return next(item for item in items if item["scope_kind"] == scope_kind)


def _affected_resources(
    session: Session,
    *,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> list[dict[str, Any]]:
    deployment_count = session.scalar(
        select(func.count(Deployment.id)).where(
            Deployment.tenant_id == tenant_id,
            Deployment.project_id == project_id,
            Deployment.environment == environment,
            Deployment.is_deleted.is_(False),
        )
    ) or 0
    surface_count = session.scalar(
        select(func.count(PublishedSurface.id)).where(
            PublishedSurface.tenant_id == tenant_id,
            PublishedSurface.project_id == project_id,
            PublishedSurface.is_deleted.is_(False),
        )
    ) or 0
    worker_count = session.scalar(
        select(func.count(WorkerSnapshot.id)).where(
            WorkerSnapshot.tenant_id == tenant_id,
            WorkerSnapshot.project_id == project_id,
            WorkerSnapshot.environment == environment,
            WorkerSnapshot.is_deleted.is_(False),
        )
    ) or 0
    return [
        {"label": "Deployments", "count": int(deployment_count)},
        {"label": "Published surfaces", "count": int(surface_count)},
        {"label": "Workers", "count": int(worker_count)},
    ]


def _provider_snapshots_for_preflight(
    session: Session,
    *,
    settings: Settings,
    tenant_id: int,
    project_id: int,
) -> list[dict[str, Any]]:
    from dimoo_run.platform.provider_status import build_provider_status_views

    return build_provider_status_views(
        session,
        settings=settings,
        tenant_id=tenant_id,
        project_id=project_id,
    )


def _write_audit(
    session: Session,
    *,
    tenant_id: int,
    project_id: int | None,
    actor_id: str,
    request_id: str | None,
    action: str,
    resource_id: int | None,
    metadata: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor_id,
            actor_type="operator",
            action=action,
            resource_type="platform_control_setting",
            resource_id=resource_id,
            result="allowed",
            request_id=request_id,
            metadata_json=metadata,
            created_at=datetime.now(UTC),
        )
    )
