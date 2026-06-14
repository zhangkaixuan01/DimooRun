from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from dimoo_run.domain.models import (
    AgentVersion,
    CatalogItem,
    ConfigAsset,
    Deployment,
    ModelGateway,
    Policy,
    PromptAsset,
    Template,
)

AssetKind = Literal["catalog", "prompt", "config", "template"]
AssetRecord = CatalogItem | PromptAsset | ConfigAsset | Template

LIFECYCLE_SEQUENCE = {
    "draft": 0,
    "validated": 1,
    "approved": 2,
    "published": 3,
    "deprecated": 4,
    "archived": 5,
}

USAGE_REF_KEYS: dict[AssetKind, tuple[str, ...]] = {
    "catalog": ("catalog_item_refs",),
    "prompt": ("prompt_asset_refs",),
    "config": ("config_asset_refs",),
    "template": ("template_asset_refs",),
}


class AssetLifecycleError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_asset_kind(value: str) -> AssetKind:
    mapping = {
        "catalog": "catalog",
        "catalog_item": "catalog",
        "catalog_items": "catalog",
        "prompt": "prompt",
        "prompts": "prompt",
        "prompt_asset": "prompt",
        "config": "config",
        "configs": "config",
        "config_asset": "config",
        "template": "template",
        "templates": "template",
        "template_asset": "template",
    }
    normalized = mapping.get(value)
    if normalized is None:
        raise AssetLifecycleError(
            "asset_kind_invalid",
            f"Unsupported asset kind: {value}",
        )
    return cast(AssetKind, normalized)


def _metadata(record: AssetRecord) -> dict[str, Any]:
    if isinstance(record, CatalogItem):
        requirements = dict(record.runtime_requirements_json or {})
        return dict(requirements.get("_asset_metadata") or {})
    return dict(record.metadata_json or {})


def _write_metadata(record: AssetRecord, metadata: dict[str, Any]) -> None:
    if isinstance(record, CatalogItem):
        requirements = dict(record.runtime_requirements_json or {})
        requirements["_asset_metadata"] = metadata
        record.runtime_requirements_json = requirements
        return
    record.metadata_json = metadata


def _lifecycle(record: AssetRecord) -> dict[str, Any]:
    if isinstance(record, CatalogItem):
        metadata = _metadata(record)
        lifecycle = dict(metadata.get("lifecycle") or {})
        lifecycle["status"] = record.status
        return lifecycle
    lifecycle = dict(_metadata(record).get("lifecycle") or {})
    lifecycle.setdefault("status", "draft")
    return lifecycle


def _set_lifecycle(
    record: AssetRecord,
    *,
    status: str,
    actor_id: str | None,
    audit_reason: str | None,
    action: str,
) -> dict[str, Any]:
    metadata = _metadata(record)
    lifecycle = dict(metadata.get("lifecycle") or {})
    timestamp = _utcnow_iso()
    previous_status = lifecycle.get("status") or _status(record)
    lifecycle.update(
        {
            "status": status,
            "updated_at": timestamp,
            "updated_by": actor_id,
            "last_action": action,
            "last_audit_reason": audit_reason,
        }
    )
    if action == "validate":
        lifecycle["validated_at"] = timestamp
    elif action == "approve":
        lifecycle["approved_at"] = timestamp
    elif action == "publish":
        lifecycle["published_at"] = timestamp
    elif action == "deprecate":
        lifecycle["deprecated_at"] = timestamp
    elif action == "archive":
        lifecycle["archived_at"] = timestamp
    elif action == "rollback":
        lifecycle["rolled_back_at"] = timestamp
    history = list(lifecycle.get("history") or [])
    history.append(
        {
            "at": timestamp,
            "action": action,
            "actor_id": actor_id,
            "audit_reason": audit_reason,
            "from_status": previous_status,
            "to_status": status,
        }
    )
    lifecycle["history"] = history
    metadata["lifecycle"] = lifecycle
    _write_metadata(record, metadata)
    if isinstance(record, CatalogItem):
        record.status = status
    return lifecycle


def _set_validation(
    record: AssetRecord,
    *,
    validation: dict[str, Any],
) -> None:
    metadata = _metadata(record)
    metadata["validation"] = validation
    _write_metadata(record, metadata)


def _status(record: AssetRecord) -> str:
    if isinstance(record, CatalogItem):
        return record.status
    return str(_lifecycle(record).get("status") or "draft")


def _record_name(record: AssetRecord) -> str:
    return str(record.name)


def _record_version(record: AssetRecord) -> str:
    return str(record.version)


def _record_type(record: AssetRecord) -> str | None:
    return str(record.type) if isinstance(record, (CatalogItem, Template)) else None


def _group_filters(statement: Select[Any], kind: AssetKind, record: AssetRecord) -> Select[Any]:
    if kind == "catalog":
        catalog_record = cast(CatalogItem, record)
        return statement.where(
            CatalogItem.tenant_id == record.tenant_id,
            CatalogItem.project_id == record.project_id,
            CatalogItem.name == _record_name(record),
            CatalogItem.type == catalog_record.type,
            CatalogItem.is_deleted.is_(False),
        )
    if kind == "prompt":
        return statement.where(
            PromptAsset.tenant_id == record.tenant_id,
            PromptAsset.project_id == record.project_id,
            PromptAsset.name == _record_name(record),
            PromptAsset.is_deleted.is_(False),
        )
    if kind == "config":
        return statement.where(
            ConfigAsset.tenant_id == record.tenant_id,
            ConfigAsset.project_id == record.project_id,
            ConfigAsset.name == _record_name(record),
            ConfigAsset.is_deleted.is_(False),
        )
    template_record = cast(Template, record)
    return statement.where(
        Template.tenant_id == record.tenant_id,
        Template.project_id == record.project_id,
        Template.name == _record_name(record),
        Template.type == template_record.type,
        Template.is_deleted.is_(False),
    )


def _version_history(session: Session, kind: AssetKind, record: AssetRecord) -> list[AssetRecord]:
    if kind == "catalog":
        statement = _group_filters(select(CatalogItem), kind, record).order_by(
            CatalogItem.created_at.asc(),
            CatalogItem.id.asc(),
        )
    elif kind == "prompt":
        statement = _group_filters(select(PromptAsset), kind, record).order_by(
            PromptAsset.created_at.asc(),
            PromptAsset.id.asc(),
        )
    elif kind == "config":
        statement = _group_filters(select(ConfigAsset), kind, record).order_by(
            ConfigAsset.created_at.asc(),
            ConfigAsset.id.asc(),
        )
    else:
        statement = _group_filters(select(Template), kind, record).order_by(
            Template.created_at.asc(),
            Template.id.asc(),
        )
    return list(session.scalars(statement))


def _diff(before: dict[str, Any] | None, after: dict[str, Any]) -> dict[str, Any]:
    previous = before or {}
    changed_fields: list[dict[str, Any]] = []
    for key in sorted(set(previous) | set(after)):
        if previous.get(key) == after.get(key):
            continue
        changed_fields.append(
            {
                "field": key,
                "before": previous.get(key),
                "after": after.get(key),
            }
        )
    return {"changed_fields": changed_fields, "has_changes": bool(changed_fields)}


def _record_snapshot(record: AssetRecord) -> dict[str, Any]:
    lifecycle = _lifecycle(record)
    snapshot: dict[str, Any] = {
        "name": _record_name(record),
        "version": _record_version(record),
        "status": _status(record),
        "lifecycle_status": lifecycle.get("status"),
    }
    if isinstance(record, CatalogItem):
        snapshot.update(
            {
                "type": record.type,
                "provider": record.provider,
                "risk_level": record.risk_level,
                "required_secrets": list(record.required_secrets_json or []),
                "required_permissions": list(record.required_permissions_json or []),
                "runtime_requirements": {
                    key: value
                    for key, value in dict(record.runtime_requirements_json or {}).items()
                    if not str(key).startswith("_")
                },
            }
        )
    elif isinstance(record, PromptAsset):
        snapshot.update(
            {
                "content_ref": record.content_ref,
                "variables_schema": dict(record.variables_schema_json or {}),
                "visibility_level": record.visibility_level,
            }
        )
    elif isinstance(record, ConfigAsset):
        snapshot.update(
            {
                "content_ref": record.content_ref,
                "schema": dict(record.schema_json or {}),
                "environment": record.environment,
            }
        )
    else:
        snapshot.update(
            {
                "type": record.type,
                "content_ref": record.content_ref,
                "schema": dict(record.schema_json or {}),
            }
        )
    return snapshot


def _validation_sources(
    record: AssetRecord,
) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    metadata = _metadata(record)
    if isinstance(record, CatalogItem):
        data = dict(record.runtime_requirements_json or {})
        return (
            data,
            list(record.required_secrets_json or []),
            list(data.get("model_gateway_refs") or []),
            list(data.get("policy_refs") or []),
        )
    data = metadata
    return (
        data,
        list(data.get("secret_refs") or []),
        list(data.get("model_gateway_refs") or []),
        list(data.get("policy_refs") or []),
    )


def _dependency_refs(record: AssetRecord) -> list[dict[str, Any]]:
    data, _, _, _ = _validation_sources(record)
    dependencies = data.get("dependencies") or []
    return [dependency for dependency in dependencies if isinstance(dependency, dict)]


def _contains_asset_reference(
    value: Any,
    *,
    name: str,
    version: str,
    asset_type: str | None,
) -> bool:
    if isinstance(value, str):
        return value in {f"{name}:{version}", f"{name}@{version}"}
    if isinstance(value, dict):
        if value.get("name") == name and value.get("version") == version:
            if asset_type is None:
                return True
            return value.get("type") in {None, asset_type}
        return any(
            _contains_asset_reference(item, name=name, version=version, asset_type=asset_type)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(
            _contains_asset_reference(item, name=name, version=version, asset_type=asset_type)
            for item in value
        )
    return False


def _usage_entries(
    session: Session,
    *,
    kind: AssetKind,
    record: AssetRecord,
) -> list[dict[str, Any]]:
    name = _record_name(record)
    version = _record_version(record)
    asset_type = _record_type(record)
    entries: list[dict[str, Any]] = []
    ref_keys = USAGE_REF_KEYS[kind]

    deployments = session.scalars(
        select(Deployment).where(
            Deployment.tenant_id == record.tenant_id,
            Deployment.project_id == record.project_id,
            Deployment.is_deleted.is_(False),
        )
    )
    for deployment in deployments:
        for key in ref_keys:
            if _contains_asset_reference(
                deployment.config_json.get(key),
                name=name,
                version=version,
                asset_type=asset_type,
            ):
                entries.append(
                    {
                        "resource_kind": "deployment",
                        "resource_id": deployment.id,
                        "environment": deployment.environment,
                        "status": deployment.desired_status,
                        "active": deployment.desired_status not in {"draft", "stopped"},
                    }
                )
                break

    versions = session.scalars(
        select(AgentVersion).join(Deployment, isouter=True).where(
            AgentVersion.agent_id.is_not(None),
            AgentVersion.is_deleted.is_(False),
        )
    )
    for version_record in versions:
        if _contains_asset_reference(
            version_record.manifest_json,
            name=name,
            version=version,
            asset_type=asset_type,
        ):
            entries.append(
                {
                    "resource_kind": "agent_version",
                    "resource_id": version_record.id,
                    "environment": None,
                    "status": version_record.status,
                    "active": version_record.status not in {"draft", "archived"},
                }
            )
    return entries


def _risk_flags(record: AssetRecord, used_by: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    if _record_version(record) == "latest":
        flags.append("floating_version")
    if any(entry["resource_kind"] == "deployment" and entry["active"] for entry in used_by):
        flags.append("active_deployment_dependency")
    if isinstance(record, CatalogItem) and record.risk_level in {"high", "critical"}:
        flags.append("high_risk_component")
    lifecycle = _lifecycle(record)
    if lifecycle.get("status") in {"deprecated", "archived"}:
        flags.append(f"lifecycle_{lifecycle['status']}")
    return flags


def _validation_result(
    session: Session,
    *,
    kind: AssetKind,
    record: AssetRecord,
    environment: str | None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    name = _record_name(record)
    version = _record_version(record)
    lifecycle = _lifecycle(record)

    if version == "latest":
        issues.append(
            {
                "code": "explicit_version_required",
                "field": "version",
                "message": "latest is not allowed.",
            }
        )
    if isinstance(record, PromptAsset) and not isinstance(record.variables_schema_json, dict):
        issues.append(
            {
                "code": "variables_schema_invalid",
                "field": "variables_schema_json",
                "message": "variables schema must be an object.",
            }
        )
    if isinstance(record, (ConfigAsset, Template, CatalogItem)):
        schema = (
            record.schema_json
            if isinstance(record, (ConfigAsset, Template))
            else record.schema_json
        )
        if not isinstance(schema, dict):
            issues.append(
                {
                    "code": "schema_invalid",
                    "field": "schema_json",
                    "message": "schema must be an object.",
                }
            )
    if (
        isinstance(record, ConfigAsset)
        and environment
        and record.environment
        and record.environment != environment
    ):
        issues.append(
            {
                "code": "environment_scope_mismatch",
                "field": "environment",
                "message": "Config asset environment does not match the selected environment.",
            }
        )

    _, secret_refs, gateway_refs, policy_refs = _validation_sources(record)
    for secret_ref in secret_refs:
        if not isinstance(secret_ref, str) or not secret_ref.startswith("secret:"):
            issues.append(
                {
                    "code": "secret_ref_invalid",
                    "field": "secret_refs",
                    "message": f"Invalid secret ref: {secret_ref}",
                }
            )

    gateway_names = {
        gateway.name
        for gateway in session.scalars(
            select(ModelGateway).where(
                ModelGateway.tenant_id == record.tenant_id,
                ModelGateway.project_id == record.project_id,
                ModelGateway.is_deleted.is_(False),
            )
        )
    }
    for gateway_ref in gateway_refs:
        if not isinstance(gateway_ref, str) or gateway_ref not in gateway_names:
            issues.append(
                {
                    "code": "model_gateway_ref_invalid",
                    "field": "model_gateway_refs",
                    "message": f"Unknown model gateway ref: {gateway_ref}",
                }
            )

    policy_names = {
        str((policy.metadata_json or {}).get("name"))
        for policy in session.scalars(
            select(Policy).where(
                Policy.tenant_id == record.tenant_id,
                Policy.project_id == record.project_id,
                Policy.is_deleted.is_(False),
            )
        )
        if (policy.metadata_json or {}).get("name")
    }
    for policy_ref in policy_refs:
        if not isinstance(policy_ref, str) or policy_ref not in policy_names:
            issues.append(
                {
                    "code": "policy_ref_invalid",
                    "field": "policy_refs",
                    "message": f"Unknown policy ref: {policy_ref}",
                }
            )

    for dependency in _dependency_refs(record):
        dependency_kind_raw = str(dependency.get("kind") or dependency.get("asset_kind") or "")
        dependency_name = str(dependency.get("name") or "")
        dependency_version = str(dependency.get("version") or "")
        if not dependency_kind_raw or not dependency_name or not dependency_version:
            issues.append(
                {
                    "code": "dependency_ref_invalid",
                    "field": "dependencies",
                    "message": "Dependency refs must include kind, name, and version.",
                }
            )
            continue
        if dependency_version == "latest":
            issues.append(
                {
                    "code": "dependency_version_invalid",
                    "field": "dependencies",
                    "message": f"{dependency_name} uses forbidden version latest.",
                }
            )
            continue
        try:
            dependency_kind = _normalize_asset_kind(dependency_kind_raw)
        except AssetLifecycleError:
            issues.append(
                {
                    "code": "dependency_kind_invalid",
                    "field": "dependencies",
                    "message": f"Unsupported dependency kind: {dependency_kind_raw}",
                }
            )
            continue
        dependency_record = find_asset_by_name_version(
            session,
            kind=dependency_kind,
            tenant_id=record.tenant_id,
            project_id=cast(int, record.project_id),
            name=dependency_name,
            version=dependency_version,
            asset_type=str(dependency.get("type") or "") or None,
        )
        if dependency_record is None:
            issues.append(
                {
                    "code": "dependency_missing",
                    "field": "dependencies",
                    "message": (
                        f"Dependency {dependency_kind}:{dependency_name}:"
                        f"{dependency_version} was not found."
                    ),
                }
            )

    status = "passed" if not issues else "failed"
    return {
        "status": status,
        "validated_at": _utcnow_iso(),
        "issues": issues,
        "version": version,
        "name": name,
        "lifecycle_status": lifecycle.get("status"),
    }


def find_asset(
    session: Session,
    *,
    kind: AssetKind,
    asset_id: int,
    tenant_id: int,
    project_id: int,
) -> AssetRecord | None:
    record: AssetRecord | None
    if kind == "catalog":
        record = session.get(CatalogItem, asset_id)
    elif kind == "prompt":
        record = session.get(PromptAsset, asset_id)
    elif kind == "config":
        record = session.get(ConfigAsset, asset_id)
    else:
        record = session.get(Template, asset_id)
    if record is None or record.is_deleted:
        return None
    if record.tenant_id != tenant_id or record.project_id != project_id:
        return None
    return record


def find_asset_by_name_version(
    session: Session,
    *,
    kind: AssetKind,
    tenant_id: int,
    project_id: int,
    name: str,
    version: str,
    asset_type: str | None = None,
) -> AssetRecord | None:
    statement: Any
    if kind == "catalog":
        statement = select(CatalogItem).where(
            CatalogItem.tenant_id == tenant_id,
            CatalogItem.project_id == project_id,
            CatalogItem.name == name,
            CatalogItem.version == version,
            CatalogItem.is_deleted.is_(False),
        )
        if asset_type:
            statement = statement.where(CatalogItem.type == asset_type)
        return cast(AssetRecord | None, session.scalar(statement))
    if kind == "prompt":
        statement = select(PromptAsset).where(
            PromptAsset.tenant_id == tenant_id,
            PromptAsset.project_id == project_id,
            PromptAsset.name == name,
            PromptAsset.version == version,
            PromptAsset.is_deleted.is_(False),
        )
        return cast(AssetRecord | None, session.scalar(statement))
    if kind == "config":
        statement = select(ConfigAsset).where(
            ConfigAsset.tenant_id == tenant_id,
            ConfigAsset.project_id == project_id,
            ConfigAsset.name == name,
            ConfigAsset.version == version,
            ConfigAsset.is_deleted.is_(False),
        )
        return cast(AssetRecord | None, session.scalar(statement))
    statement = select(Template).where(
        Template.tenant_id == tenant_id,
        Template.project_id == project_id,
        Template.name == name,
        Template.version == version,
        Template.is_deleted.is_(False),
    )
    if asset_type:
        statement = statement.where(Template.type == asset_type)
    return cast(AssetRecord | None, session.scalar(statement))


def _filtered_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if key not in {"lifecycle", "validation"}
    }


def asset_detail(
    session: Session,
    *,
    kind: AssetKind,
    record: AssetRecord,
    environment: str | None,
) -> dict[str, Any]:
    metadata = _metadata(record)
    lifecycle = _lifecycle(record)
    validation = dict(metadata.get("validation") or {})
    dependencies = _dependency_refs(record)
    used_by = _usage_entries(session, kind=kind, record=record)
    history = _version_history(session, kind, record)
    previous = None
    for candidate in history:
        if candidate.id == record.id:
            break
        previous = candidate
    return {
        "item": serialize_asset(record),
        "lifecycle": lifecycle,
        "validation": validation,
        "dependencies": dependencies,
        "used_by": used_by,
        "risk_flags": _risk_flags(record, used_by),
        "version_history": [serialize_asset(candidate) for candidate in history],
        "diff_to_previous": _diff(
            _record_snapshot(previous) if previous is not None else None,
            _record_snapshot(record),
        ),
        "environment": environment,
    }


def serialize_asset(record: AssetRecord) -> dict[str, Any]:
    metadata = _metadata(record)
    item: dict[str, Any] = {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "project_id": record.project_id,
        "name": _record_name(record),
        "version": _record_version(record),
        "status": _status(record),
        "lifecycle": _lifecycle(record),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
    if isinstance(record, CatalogItem):
        item.update(
            {
                "kind": "catalog",
                "type": record.type,
                "provider": record.provider,
                "schema": dict(record.schema_json or {}),
                "capabilities": dict(record.capabilities_json or {}),
                "risk_level": record.risk_level,
                "required_secrets": list(record.required_secrets_json or []),
                "required_permissions": list(record.required_permissions_json or []),
                "runtime_requirements": {
                    key: value
                    for key, value in dict(record.runtime_requirements_json or {}).items()
                    if not str(key).startswith("_")
                },
            }
        )
    elif isinstance(record, PromptAsset):
        item.update(
            {
                "kind": "prompt",
                "content_ref": record.content_ref,
                "variables_schema": dict(record.variables_schema_json or {}),
                "visibility_level": record.visibility_level,
                "metadata": _filtered_metadata(metadata),
            }
        )
    elif isinstance(record, ConfigAsset):
        item.update(
            {
                "kind": "config",
                "content_ref": record.content_ref,
                "schema": dict(record.schema_json or {}),
                "environment": record.environment,
                "metadata": _filtered_metadata(metadata),
            }
        )
    else:
        item.update(
            {
                "kind": "template",
                "type": record.type,
                "content_ref": record.content_ref,
                "schema": dict(record.schema_json or {}),
                "metadata": _filtered_metadata(metadata),
            }
        )
    return item


def validate_asset(
    session: Session,
    *,
    kind: AssetKind,
    record: AssetRecord,
    actor_id: str | None,
    audit_reason: str | None,
    environment: str | None,
) -> dict[str, Any]:
    validation = _validation_result(session, kind=kind, record=record, environment=environment)
    _set_validation(record, validation=validation)
    next_status = "validated" if validation["status"] == "passed" else _status(record)
    lifecycle = _set_lifecycle(
        record,
        status=next_status,
        actor_id=actor_id,
        audit_reason=audit_reason,
        action="validate",
    )
    if isinstance(record, CatalogItem):
        record.status = next_status
    session.flush()
    return {"validation": validation, "lifecycle": lifecycle, "item": serialize_asset(record)}


def approve_asset(
    session: Session,
    *,
    record: AssetRecord,
    actor_id: str | None,
    audit_reason: str | None,
) -> dict[str, Any]:
    validation = dict(_metadata(record).get("validation") or {})
    if validation.get("status") != "passed":
        raise AssetLifecycleError(
            "asset_validation_required",
            "Asset validation must pass before approval.",
        )
    lifecycle = _set_lifecycle(
        record,
        status="approved",
        actor_id=actor_id,
        audit_reason=audit_reason,
        action="approve",
    )
    session.flush()
    return {"item": serialize_asset(record), "lifecycle": lifecycle}


def publish_asset(
    session: Session,
    *,
    kind: AssetKind,
    record: AssetRecord,
    actor_id: str | None,
    audit_reason: str | None,
) -> dict[str, Any]:
    status = _status(record)
    if status not in {"approved", "published"}:
        raise AssetLifecycleError(
            "asset_approval_required",
            "Asset must be approved before publish.",
        )
    for sibling in _version_history(session, kind, record):
        if sibling.id == record.id or _status(sibling) != "published":
            continue
        _set_lifecycle(
            sibling,
            status="deprecated",
            actor_id=actor_id,
            audit_reason=f"superseded_by:{record.id}",
            action="deprecate",
        )
    lifecycle = _set_lifecycle(
        record,
        status="published",
        actor_id=actor_id,
        audit_reason=audit_reason,
        action="publish",
    )
    session.flush()
    return {"item": serialize_asset(record), "lifecycle": lifecycle}


def deprecate_asset(
    session: Session,
    *,
    kind: AssetKind,
    record: AssetRecord,
    actor_id: str | None,
    audit_reason: str | None,
) -> dict[str, Any]:
    used_by = _usage_entries(session, kind=kind, record=record)
    if any(entry["resource_kind"] == "deployment" and entry["active"] for entry in used_by):
        raise AssetLifecycleError(
            "asset_in_use_by_active_deployment",
            "Asset is still referenced by an active deployment.",
            status_code=409,
        )
    lifecycle = _set_lifecycle(
        record,
        status="deprecated",
        actor_id=actor_id,
        audit_reason=audit_reason,
        action="deprecate",
    )
    session.flush()
    return {"item": serialize_asset(record), "lifecycle": lifecycle, "used_by": used_by}


def archive_asset(
    session: Session,
    *,
    kind: AssetKind,
    record: AssetRecord,
    actor_id: str | None,
    audit_reason: str | None,
) -> dict[str, Any]:
    used_by = _usage_entries(session, kind=kind, record=record)
    if any(entry["active"] for entry in used_by):
        raise AssetLifecycleError(
            "asset_still_referenced",
            "Asset still has active references and cannot be archived.",
            status_code=409,
        )
    lifecycle = _set_lifecycle(
        record,
        status="archived",
        actor_id=actor_id,
        audit_reason=audit_reason,
        action="archive",
    )
    session.flush()
    return {"item": serialize_asset(record), "lifecycle": lifecycle, "used_by": used_by}


def rollback_asset(
    session: Session,
    *,
    kind: AssetKind,
    record: AssetRecord,
    actor_id: str | None,
    audit_reason: str | None,
    target_version: str | None,
) -> dict[str, Any]:
    history = _version_history(session, kind, record)
    target: AssetRecord | None = None
    if target_version:
        for candidate in history:
            if _record_version(candidate) == target_version:
                target = candidate
                break
    else:
        previous_candidates = [candidate for candidate in history if candidate.id != record.id]
        if previous_candidates:
            target = previous_candidates[-1]
    if target is None:
        raise AssetLifecycleError(
            "rollback_target_not_found",
            "Rollback target version was not found.",
            status_code=404,
        )
    if target.id == record.id:
        raise AssetLifecycleError(
            "rollback_target_invalid",
            "Rollback target must be a different version.",
        )
    _set_lifecycle(
        record,
        status="deprecated",
        actor_id=actor_id,
        audit_reason=audit_reason,
        action="rollback",
    )
    lifecycle = _set_lifecycle(
        target,
        status="published",
        actor_id=actor_id,
        audit_reason=audit_reason,
        action="publish",
    )
    session.flush()
    return {
        "item": serialize_asset(target),
        "rolled_back_from": serialize_asset(record),
        "lifecycle": lifecycle,
    }
