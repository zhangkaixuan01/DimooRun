from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

import dimoo_run.domain.models as domain_models
from dimoo_run.api.admin.notifications import record_delivery_attempt
from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
)
from dimoo_run.core.config import Settings
from dimoo_run.persistence.database import Base, create_session_factory

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]

_STATE_DATABASE_URL: str | None = None
_INCIDENTS: dict[int, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def reset_incident_workflows() -> None:
    global _STATE_DATABASE_URL
    _STATE_DATABASE_URL = None
    _INCIDENTS.clear()


def _sync_state() -> None:
    global _STATE_DATABASE_URL
    from dimoo_run.core.config import Settings

    database_url = Settings.from_env().database.url
    if _STATE_DATABASE_URL != database_url:
        reset_incident_workflows()
        _STATE_DATABASE_URL = database_url


def _list_ints(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    return [int(item) for item in value if str(item).strip()]


def _invalid_int_list(value: Any) -> bool:
    if value is None:
        return False
    if not isinstance(value, list):
        return True
    if _invalid_int_items(value):
        return True
    return False


def _invalid_int_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    invalid_items: list[str] = []
    for item in value:
        if not str(item).strip():
            invalid_items.append(str(item))
            continue
        try:
            int(item)
        except (TypeError, ValueError):
            invalid_items.append(str(item))
    return invalid_items


def _invalid_linked_evidence_fields(data: dict[str, Any]) -> list[str]:
    invalid_fields = [
        field
        for field in ("linked_runs", "linked_tasks")
        if _invalid_int_list(data.get(field))
    ]
    if _invalid_string_list(data.get("linked_events")) or _invalid_string_items(
        data.get("linked_events")
    ):
        invalid_fields.append("linked_events")
    return invalid_fields


def _invalid_linked_evidence_values(data: dict[str, Any]) -> dict[str, list[str]]:
    invalid_values: dict[str, list[str]] = {}
    for field in ("linked_runs", "linked_tasks"):
        invalid_items = _invalid_int_items(data.get(field))
        if invalid_items:
            invalid_values[field] = invalid_items
    invalid_events = _invalid_string_items(data.get("linked_events"))
    if invalid_events:
        invalid_values["linked_events"] = invalid_events
    return invalid_values


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _provided_invalid_string_list(value: Any) -> bool:
    return bool(_invalid_string_items(value)) or (
        isinstance(value, list) and bool(value) and not _list_strings(value)
    )


def _invalid_string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if not str(item).strip()]


def _invalid_string_list(value: Any) -> bool:
    if value is None:
        return False
    if not isinstance(value, list):
        return True
    return bool(value) and not _list_strings(value)


def _audit_note(value: Any) -> str:
    return str(value or "").strip()


def _resolution_summary(value: Any) -> str:
    return str(value or "").strip()


def _incident(
    incident_id: int,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any]:
    incident = _INCIDENTS.get(incident_id)
    if incident is None:
        incident = {
            "id": incident_id,
            "name": f"Incident {incident_id}",
            "status": "open",
            "severity": "critical",
            "tenant_id": tenant_id,
            "project_id": project_id,
            "environment": environment,
            "created_at": _now(),
            "updated_at": _now(),
            "linked_evidence": {"runs": [], "tasks": [], "events": []},
            "timeline": [],
            "delivery_attempts": [],
            "resolution": None,
        }
        _INCIDENTS[incident_id] = incident
    return incident


def _record_incident_action(
    incident_id: int,
    *,
    status: str,
    action: str,
    payload: dict[str, Any] | None,
    request_id: str | None,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
) -> dict[str, Any] | JSONResponse:
    _sync_state()
    data = payload or {}
    audit_note = _audit_note(data.get("audit_note"))
    if not audit_note:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "incident_audit_note_required",
                "message": "Incident actions require an audit_note.",
                "status": "blocked",
                "validation": {"valid": False, "checks": ["audit_note_present"]},
                "disabled_action_reason": "audit_note_required",
                "timeline": [],
                "delivery_attempts": [],
                "request_id": request_id,
            },
        )
    resolution_summary = _resolution_summary(data.get("resolution_summary"))
    if action == "incident.resolve" and not resolution_summary:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "incident_resolution_summary_required",
                "message": "Incident resolve requires a resolution_summary.",
                "status": "blocked",
                "validation": {
                    "valid": False,
                    "checks": ["audit_note_present", "resolution_summary_present"],
                },
                "disabled_action_reason": "resolution_summary_required",
                "timeline": [],
                "delivery_attempts": [],
                "resolution": None,
                "request_id": request_id,
            },
        )
    if _provided_invalid_string_list(data.get("notify_channels")):
        invalid_notify_channels = _invalid_string_items(data.get("notify_channels"))
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "incident_notify_channels_invalid",
                "message": "Incident notify_channels must include at least one channel name.",
                "status": "blocked",
                "validation": {
                    "valid": False,
                    "checks": ["audit_note_present", "notify_channels_valid"],
                    "notify_channels_valid": False,
                    "invalid_notify_channels": invalid_notify_channels,
                },
                "disabled_action_reason": "notify_channels_invalid",
                "timeline": [],
                "delivery_attempts": [],
                "request_id": request_id,
            },
        )
    invalid_linked_evidence_fields = (
        _invalid_linked_evidence_fields(data)
        if action == "incident.acknowledge"
        else []
    )
    if invalid_linked_evidence_fields:
        invalid_linked_evidence_values = _invalid_linked_evidence_values(data)
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "incident_linked_evidence_invalid",
                "message": "Incident linked evidence IDs must be integer identifiers.",
                "status": "blocked",
                "validation": {
                    "valid": False,
                    "checks": ["audit_note_present", "linked_evidence_valid"],
                    "linked_evidence_valid": False,
                    "invalid_linked_evidence_fields": invalid_linked_evidence_fields,
                    "invalid_linked_evidence_values": invalid_linked_evidence_values,
                },
                "disabled_action_reason": "linked_evidence_invalid",
                "timeline": [],
                "delivery_attempts": [],
                "request_id": request_id,
            },
        )
    incident = _incident(incident_id, tenant_id, project_id, environment)
    incident["status"] = status
    incident["updated_at"] = _now()
    decision_payload = dict(data.get("decision_payload") or {})
    if action == "incident.acknowledge":
        incident["linked_evidence"] = {
            "runs": _list_ints(data.get("linked_runs")),
            "tasks": _list_ints(data.get("linked_tasks")),
            "events": _list_strings(data.get("linked_events")),
        }
    if action == "incident.resolve":
        incident["resolution"] = {
            "summary": resolution_summary,
            "resolved_at": incident["updated_at"],
        }
    timeline_entry = {
        "action": action,
        "status": status,
        "audit_note": audit_note,
        "decision_payload": decision_payload,
        "created_at": incident["updated_at"],
        "request_id": request_id,
    }
    incident["timeline"].append(timeline_entry)
    attempts = [
        record_delivery_attempt(
            channel_id=None,
            channel_name=channel,
            target_ref=f"channel://{channel}",
            message=timeline_entry["audit_note"] or f"{action} for incident {incident_id}",
            source=action,
            request_id=request_id,
        )
        for channel in _list_strings(data.get("notify_channels"))
    ]
    incident["delivery_attempts"].extend(attempts)
    persisted_item = _persist_incident_status(
        incident_id,
        status=status,
        decision_payload=decision_payload,
    )
    incident_item = persisted_item or {
        key: value
        for key, value in incident.items()
        if key not in {"timeline", "delivery_attempts", "linked_evidence", "resolution"}
    }
    return {
        "item": incident_item,
        "incident": {
            key: value
            for key, value in incident.items()
            if key not in {"timeline", "delivery_attempts", "linked_evidence", "resolution"}
        },
        "timeline": list(incident["timeline"]),
        "linked_evidence": incident["linked_evidence"],
        "delivery_attempts": list(incident["delivery_attempts"]),
        "resolution": incident["resolution"],
        "audit": {
            "action": action,
            "resource_type": "incident",
            "resource_id": incident_id,
            "request_id": request_id,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "environment": environment,
        },
        "request_id": request_id,
    }


def _persist_incident_status(
    incident_id: int,
    *,
    status: str,
    decision_payload: dict[str, Any],
) -> dict[str, Any] | None:
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database.url)
    session = session_factory()
    try:
        if settings.runtime.mode == "dev":
            Base.metadata.create_all(session.get_bind())
        incident = session.get(domain_models.IncidentEvent, incident_id)
        if incident is None:
            return None
        incident.status = status
        metadata = dict(incident.metadata_json or {})
        metadata["decision_payload"] = decision_payload
        incident.metadata_json = metadata
        session.commit()
        return {
            "id": incident.id,
            "status": incident.status,
            "severity": incident.severity,
            "signal": incident.signal,
            "source_ref": incident.source_ref,
            "value": incident.value,
            "metadata": dict(incident.metadata_json or {}),
            "tenant_id": incident.tenant_id,
            "project_id": incident.project_id,
        }
    finally:
        session.close()


@router.post("/v1/incidents/{incident_id}/acknowledge")
def acknowledge_incident(
    incident_id: int,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    return _record_incident_action(
        incident_id,
        status="acknowledged",
        action="incident.acknowledge",
        payload=payload,
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
    )


@router.post("/v1/incidents/{incident_id}/resolve")
def resolve_incident(
    incident_id: int,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    return _record_incident_action(
        incident_id,
        status="resolved",
        action="incident.resolve",
        payload=payload,
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
    )
