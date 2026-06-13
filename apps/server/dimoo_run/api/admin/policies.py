from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Response
from sqlalchemy import Table, select
from sqlalchemy.orm import Session, sessionmaker

from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
)
from dimoo_run.core.config import Settings
from dimoo_run.domain.models import Policy, Project, Tenant
from dimoo_run.persistence.database import create_session_factory
from dimoo_run.security.api_keys import AuthenticatedActor

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]
_SCHEMA_DATABASE_URL: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _session_factory() -> sessionmaker[Session]:
    global _SCHEMA_DATABASE_URL
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database.url)
    if settings.runtime.mode == "dev" and _SCHEMA_DATABASE_URL != settings.database.url:
        with session_factory() as session:
            bind = session.get_bind()
            for model in (Tenant, Project, Policy):
                _table(model).create(bind, checkfirst=True)
        _SCHEMA_DATABASE_URL = settings.database.url
    return session_factory


def _table(model: type[Any]) -> Table:
    table = model.__table__
    if not isinstance(table, Table):
        raise TypeError(f"{model.__name__} does not expose a SQLAlchemy Table")
    return table


def _policy_name(policy: Policy) -> str | None:
    return policy.metadata_json.get("name") if isinstance(policy.metadata_json, dict) else None


def _serialize_policy(policy: Policy) -> dict[str, Any]:
    metadata = dict(policy.metadata_json or {})
    item = {
        "id": policy.id,
        "tenant_id": policy.tenant_id,
        "project_id": policy.project_id,
        "type": policy.type,
        "resource_type": policy.resource_type,
        "action": policy.action,
        "decision": policy.decision,
        "priority": policy.priority,
        "risk_level": policy.risk_level,
        "condition": policy.condition_json,
        "reason": policy.reason,
        "status": policy.status,
        "metadata": {key: value for key, value in metadata.items() if not key.startswith("_")},
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }
    if metadata.get("name"):
        item["name"] = metadata["name"]
    if metadata.get("_environment"):
        item["environment"] = metadata["_environment"]
    return item


def _draft(payload: dict[str, Any]) -> dict[str, Any]:
    draft = dict(payload.get("draft_policy") or payload)
    if not draft.get("resource_type"):
        draft["resource_type"] = "generic"
    if not draft.get("action"):
        draft["action"] = "manage"
    if not draft.get("decision"):
        draft["decision"] = "allow"
    if not draft.get("priority"):
        draft["priority"] = 100
    if not draft.get("type"):
        draft["type"] = "admin"
    return draft


def _condition_matches(condition: dict[str, Any], sample: dict[str, Any]) -> bool:
    for key, expected in condition.items():
        if key == "attributes" and isinstance(expected, dict):
            raw_attributes = sample.get("attributes")
            attributes = raw_attributes if isinstance(raw_attributes, dict) else {}
            if any(
                attributes.get(attr_key) != attr_value
                for attr_key, attr_value in expected.items()
            ):
                return False
            continue
        if sample.get(key) != expected:
            return False
    return True


def _policy_matches(policy: Policy, sample: dict[str, Any]) -> bool:
    if policy.status != "active":
        return False
    if policy.resource_type != sample.get("resource_type"):
        return False
    if policy.action != sample.get("action"):
        return False
    return _condition_matches(policy.condition_json or {}, sample)


def _draft_matches(draft: dict[str, Any], sample: dict[str, Any]) -> bool:
    if draft.get("resource_type") != sample.get("resource_type"):
        return False
    if draft.get("action") != sample.get("action"):
        return False
    return _condition_matches(dict(draft.get("condition") or {}), sample)


def _matching_policies(
    policies: Iterable[Policy],
    *,
    sample: dict[str, Any],
) -> list[Policy]:
    return sorted(
        [policy for policy in policies if _policy_matches(policy, sample)],
        key=lambda policy: (policy.priority, policy.id),
    )


def _conflicts(draft: dict[str, Any], matches: Iterable[Policy]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for policy in matches:
        same_priority = policy.priority == int(draft.get("priority") or 100)
        different_decision = policy.decision != draft.get("decision")
        if same_priority and different_decision:
            warnings.append(
                {
                    "code": "priority_conflict",
                    "message": (
                        "An active policy with the same priority returns a different decision."
                    ),
                    "conflicting_policy_id": policy.id,
                    "conflicting_policy_name": _policy_name(policy),
                }
            )
    return warnings


def _version_from_metadata(metadata: dict[str, Any]) -> int:
    return int(metadata.get("version") or 0)


def _history_from_metadata(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    history = metadata.get("versions")
    return list(history) if isinstance(history, list) else []


def _require_audit_reason(
    *,
    audit_reason: str,
    response: Response,
    request_id: str | None,
) -> dict[str, Any] | None:
    if audit_reason.strip():
        return None
    response.status_code = 400
    return {
        "error_code": "audit_reason_required",
        "message": "Audit reason is required for policy governance changes.",
        "request_id": request_id,
        "details": {"field": "audit_reason"},
    }


def _snapshot(policy: Policy) -> dict[str, Any]:
    return {
        "type": policy.type,
        "resource_type": policy.resource_type,
        "action": policy.action,
        "decision": policy.decision,
        "priority": policy.priority,
        "risk_level": policy.risk_level,
        "condition": policy.condition_json,
        "reason": policy.reason,
        "status": policy.status,
        "name": _policy_name(policy),
    }


def _compare_snapshots(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    from_version: int | None,
    to_version: int,
) -> dict[str, Any]:
    previous_snapshot = previous or {}
    changed_fields: list[dict[str, Any]] = []
    for key in sorted(set(previous_snapshot) | set(current)):
        before = previous_snapshot.get(key)
        after = current.get(key)
        if before == after:
            continue
        changed_fields.append(
            {
                "field": key,
                "before": before,
                "after": after,
            }
        )
    return {
        "from_version": from_version,
        "to_version": to_version,
        "changed_fields": changed_fields,
    }


def _apply_draft(
    policy: Policy,
    draft: dict[str, Any],
    *,
    tenant_id: int,
    project_id: int | None,
    environment: str | None,
) -> None:
    policy.tenant_id = tenant_id
    policy.project_id = project_id
    policy.type = str(draft.get("type") or "admin")
    policy.resource_type = str(draft.get("resource_type") or "generic")
    policy.action = str(draft.get("action") or "manage")
    policy.decision = str(draft.get("decision") or "allow")
    policy.priority = int(draft.get("priority") or 100)
    policy.risk_level = (
        str(draft.get("risk_level")) if draft.get("risk_level") is not None else None
    )
    policy.condition_json = dict(draft.get("condition") or {})
    policy.reason = str(draft.get("reason")) if draft.get("reason") is not None else None
    policy.status = "active"
    metadata = dict(policy.metadata_json or {})
    if draft.get("name"):
        metadata["name"] = draft["name"]
    draft_metadata = draft.get("metadata")
    if isinstance(draft_metadata, dict):
        for key, value in draft_metadata.items():
            if key not in {"version", "versions", "last_audit_reason"}:
                metadata[str(key)] = value
    if environment:
        metadata["_environment"] = environment
    policy.metadata_json = metadata


@router.post("/v1/policies/simulate")
def simulate_policy(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    draft = _draft(data)
    sample = dict(data.get("sample") or {})
    session = _session_factory()()
    try:
        policies = session.scalars(
            select(Policy).where(
                Policy.is_deleted.is_(False),
                Policy.tenant_id == x_tenant_id,
                Policy.project_id == x_project_id,
            )
        ).all()
        matches = _matching_policies(policies, sample=sample)
        draft_applies = _draft_matches(draft, sample)
        matched_policy = matches[0] if matches else None
        decision = {
            "result": str(
                draft["decision"]
                if draft_applies
                else (matched_policy.decision if matched_policy else "allow")
            ),
            "policy_id": None if draft_applies else (matched_policy.id if matched_policy else None),
            "policy_name": (
                draft.get("name")
                if draft_applies
                else (_policy_name(matched_policy) if matched_policy else None)
            ),
            "reason": (
                draft.get("reason")
                if draft_applies
                else (matched_policy.reason if matched_policy else None)
            ),
        }
        matched_resources = []
        if sample.get("resource_type") and sample.get("action"):
            matched_resources.append(
                {
                    "resource_type": sample.get("resource_type"),
                    "resource_id": sample.get("resource_id"),
                    "action": sample.get("action"),
                    "environment": sample.get("environment") or x_environment,
                }
            )
        return {
            "decision": decision,
            "matched_resources": matched_resources,
            "matched_policies": [_serialize_policy(policy) for policy in matches],
            "audit_preview": {
                "action": "policy.simulate",
                "resource_type": draft["resource_type"],
                "resource_id": sample.get("resource_id"),
                "request_id": x_request_id,
                "tenant_id": x_tenant_id,
                "project_id": x_project_id,
                "environment": x_environment,
                "created_at": _now(),
            },
            "conflict_warnings": _conflicts(draft, matches),
        }
    finally:
        session.close()


@router.post("/v1/policies/activate", status_code=201)
def activate_policy(
    response: Response,
    payload: AdminPayload = None,
    actor: Annotated[AuthenticatedActor | None, Depends(enforce_console_actor)] = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    draft = _draft(data)
    audit_reason = str(data.get("audit_reason") or "")
    expected_version = data.get("expected_version")
    reason_error = _require_audit_reason(
        audit_reason=audit_reason,
        response=response,
        request_id=x_request_id,
    )
    if reason_error is not None:
        return reason_error
    assert x_tenant_id is not None
    session = _session_factory()()
    try:
        policies = session.scalars(
            select(Policy).where(
                Policy.is_deleted.is_(False),
                Policy.tenant_id == x_tenant_id,
                Policy.project_id == x_project_id,
            )
        ).all()
        active = next(
            (policy for policy in policies if _policy_name(policy) == draft.get("name")),
            None,
        )
        current_snapshot: dict[str, Any] | None = None
        current_version = 0
        if active is None:
            active = Policy(
                tenant_id=x_tenant_id,
                project_id=x_project_id,
                type="admin",
                resource_type="generic",
                action="manage",
                decision="allow",
                priority=100,
                condition_json={},
                metadata_json={},
            )
            session.add(active)
            session.flush()
        else:
            current_snapshot = _snapshot(active)
            current_version = _version_from_metadata(dict(active.metadata_json or {}))
            if expected_version is not None and int(expected_version) != current_version:
                response.status_code = 409
                return {
                    "error_code": "policy_version_conflict",
                    "message": "Policy changed since the current review context was loaded.",
                    "request_id": x_request_id,
                    "details": {
                        "policy_id": active.id,
                        "expected_version": int(expected_version),
                        "current_version": current_version,
                    },
                }
        history = _history_from_metadata(dict(active.metadata_json or {}))
        if active.id is not None and active.created_at is not None:
            if current_version > 0:
                history.append({"version": current_version, "snapshot": _snapshot(active)})
        _apply_draft(
            active,
            draft,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            environment=x_environment,
        )
        version = max([entry.get("version", 0) for entry in history] + [0]) + 1
        metadata = dict(active.metadata_json or {})
        metadata["version"] = version
        metadata["versions"] = history + [{"version": version, "snapshot": _snapshot(active)}]
        metadata["last_audit_reason"] = audit_reason
        active.metadata_json = metadata
        session.commit()
        return {
            "item": _serialize_policy(active),
            "version": version,
            "comparison": _compare_snapshots(
                current_snapshot,
                _snapshot(active),
                from_version=current_version or None,
                to_version=version,
            ),
            "audit": {
                "action": "policy.activate",
                "reason": audit_reason,
                "actor_id": actor.actor_id if actor else None,
                "request_id": x_request_id,
            },
            "rollback_target": {"policy_id": active.id, "version": version},
            "conflict_warnings": _conflicts(
                draft,
                [policy for policy in policies if policy.id != active.id],
            ),
        }
    finally:
        session.close()


@router.post("/v1/policies/{policy_id}/rollback")
def rollback_policy(
    policy_id: int,
    response: Response,
    payload: AdminPayload = None,
    actor: Annotated[AuthenticatedActor | None, Depends(enforce_console_actor)] = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    target_version = int(data.get("target_version") or 0)
    audit_reason = str(data.get("audit_reason") or "")
    expected_version = data.get("expected_version")
    reason_error = _require_audit_reason(
        audit_reason=audit_reason,
        response=response,
        request_id=x_request_id,
    )
    if reason_error is not None:
        return reason_error
    assert x_tenant_id is not None
    session = _session_factory()()
    try:
        policy = session.get(Policy, policy_id)
        if (
            policy is None
            or policy.is_deleted
            or policy.tenant_id != x_tenant_id
            or policy.project_id != x_project_id
        ):
            response.status_code = 404
            return {
                "error_code": "resource_not_found",
                "message": f"Policy {policy_id} was not found.",
                "request_id": x_request_id,
                "details": {},
            }
        metadata = dict(policy.metadata_json or {})
        history = _history_from_metadata(metadata)
        current_snapshot = _snapshot(policy)
        current_version = _version_from_metadata(metadata)
        if expected_version is not None and int(expected_version) != current_version:
            response.status_code = 409
            return {
                "error_code": "policy_version_conflict",
                "message": "Policy changed since the current review context was loaded.",
                "request_id": x_request_id,
                "details": {
                    "policy_id": policy.id,
                    "expected_version": int(expected_version),
                    "current_version": current_version,
                },
            }
        target = next(
            (entry for entry in history if int(entry.get("version") or 0) == target_version),
            None,
        )
        if target is None:
            response.status_code = 404
            return {
                "error_code": "policy_version_not_found",
                "message": f"Policy version {target_version} was not found.",
                "request_id": x_request_id,
                "details": {"target_version": target_version},
            }
        if current_version > 0:
            history.append({"version": current_version, "snapshot": _snapshot(policy)})
        snapshot = dict(target.get("snapshot") or {})
        _apply_draft(
            policy,
            snapshot,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            environment=x_environment,
        )
        next_version = (
            max([int(entry.get("version") or 0) for entry in history] + [current_version])
            + 1
        )
        metadata = dict(policy.metadata_json or {})
        metadata["version"] = next_version
        metadata["versions"] = history + [{"version": next_version, "snapshot": _snapshot(policy)}]
        metadata["last_audit_reason"] = audit_reason
        policy.metadata_json = metadata
        session.commit()
        return {
            "item": _serialize_policy(policy),
            "version": next_version,
            "comparison": _compare_snapshots(
                current_snapshot,
                _snapshot(policy),
                from_version=current_version or None,
                to_version=next_version,
            ),
            "audit": {
                "action": "policy.rollback",
                "reason": audit_reason,
                "actor_id": actor.actor_id if actor else None,
                "request_id": x_request_id,
            },
            "rollback_target": {"policy_id": policy.id, "version": target_version},
            "conflict_warnings": [],
        }
    finally:
        session.close()
