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

_STATE_DATABASE_URL: str | None = None
_DELIVERY_SEQUENCE = 600
_DELIVERY_ATTEMPTS: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(UTC).isoformat()


def reset_notification_workflows() -> None:
    global _STATE_DATABASE_URL, _DELIVERY_SEQUENCE
    _STATE_DATABASE_URL = None
    _DELIVERY_SEQUENCE = 600
    _DELIVERY_ATTEMPTS.clear()


def _sync_state() -> None:
    global _STATE_DATABASE_URL
    from dimoo_run.core.config import Settings

    database_url = Settings.from_env().database.url
    if _STATE_DATABASE_URL != database_url:
        reset_notification_workflows()
        _STATE_DATABASE_URL = database_url


def _next_delivery_id() -> int:
    global _DELIVERY_SEQUENCE
    _DELIVERY_SEQUENCE += 1
    return _DELIVERY_SEQUENCE


def _notification_validation(data: dict[str, Any]) -> dict[str, Any]:
    target_ref = _normalized_target_ref(data.get("target_ref"))
    message = str(data.get("message") or "").strip()
    target_ref_valid = _target_ref_valid(data.get("target_ref"))
    channel_id_valid = _channel_id(data.get("channel_id")) is not False
    channel_name = data.get("channel_name")
    channel_name_valid = _channel_name_valid(channel_name)
    return {
        "valid": (
            bool(target_ref)
            and target_ref_valid
            and bool(message)
            and channel_id_valid
            and channel_name_valid
        ),
        "checks": [
            "target_ref_present",
            "target_ref_valid",
            "message_present",
            "channel_id_valid",
            "channel_name_valid",
        ],
        "target_ref_present": bool(target_ref),
        "target_ref_valid": target_ref_valid,
        "target_ref_normalized": target_ref,
        "message_present": bool(message),
        "channel_id_valid": channel_id_valid,
        "channel_id_normalized": _normalized_channel_id(data.get("channel_id")),
        "channel_name_valid": channel_name_valid,
        "channel_name_normalized": _normalized_channel_name(channel_name),
    }


def _target_ref_valid(value: Any) -> bool:
    normalized = _normalized_target_ref(value)
    return not normalized or ("://" in normalized and normalized == str(value))


def _normalized_target_ref(value: Any) -> str:
    return str(value or "").strip()


def _channel_id(value: Any) -> int | None | bool:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() != value:
        return False
    try:
        return int(value)
    except (TypeError, ValueError):
        return False


def _normalized_channel_id(value: Any) -> int | None:
    parsed = _channel_id(str(value).strip() if isinstance(value, str) else value)
    if parsed is False:
        return None
    return parsed


def _channel_name_valid(value: Any) -> bool:
    if value is None:
        return True
    normalized = str(value).strip()
    return bool(normalized) and normalized == str(value)


def _normalized_channel_name(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip()


def record_delivery_attempt(
    *,
    channel_id: int | None,
    channel_name: str,
    target_ref: str,
    message: str,
    source: str,
    request_id: str | None,
) -> dict[str, Any]:
    _sync_state()
    attempt = {
        "id": _next_delivery_id(),
        "channel_id": channel_id,
        "channel_name": channel_name,
        "target_ref": target_ref,
        "status": "sent",
        "source": source,
        "attempted_at": _now(),
        "visible_to_operator": True,
        "redacted_payload": {"message": message},
        "request_id": request_id,
    }
    _DELIVERY_ATTEMPTS.append(attempt)
    return attempt


@router.post("/v1/notifications/test-send")
def test_send_notification(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    data = payload or {}
    validation = _notification_validation(data)
    if not validation["target_ref_present"]:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "notification_target_ref_required",
                "message": "Notification test-send requires a target_ref.",
                "status": "blocked",
                "validation": validation,
                "disabled_action_reason": "target_ref_required",
                "delivery_attempt": None,
                "request_id": x_request_id,
            },
        )
    if not validation["target_ref_valid"]:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "notification_target_ref_invalid",
                "message": "Notification test-send target_ref must be a URI-style reference.",
                "status": "blocked",
                "validation": validation,
                "disabled_action_reason": "target_ref_invalid",
                "delivery_attempt": None,
                "request_id": x_request_id,
            },
        )
    if not validation["message_present"]:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "notification_message_required",
                "message": "Notification test-send requires a message.",
                "status": "blocked",
                "validation": validation,
                "disabled_action_reason": "message_required",
                "delivery_attempt": None,
                "request_id": x_request_id,
            },
        )
    channel_id = _channel_id(data.get("channel_id"))
    if channel_id is False:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "notification_channel_id_invalid",
                "message": "Notification test-send channel_id must be an integer.",
                "status": "blocked",
                "validation": validation,
                "disabled_action_reason": "channel_id_invalid",
                "delivery_attempt": None,
                "request_id": x_request_id,
            },
        )
    if not validation["channel_name_valid"]:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "notification_channel_name_invalid",
                "message": "Notification test-send channel_name cannot be blank.",
                "status": "blocked",
                "validation": validation,
                "disabled_action_reason": "channel_name_invalid",
                "delivery_attempt": None,
                "request_id": x_request_id,
            },
        )
    attempt = record_delivery_attempt(
        channel_id=channel_id,
        channel_name=str(data.get("channel_name") or "notification-channel").strip(),
        target_ref=str(data.get("target_ref")).strip(),
        message=str(data.get("message")).strip(),
        source="notification.test_send",
        request_id=x_request_id,
    )
    return {
        "status": attempt["status"],
        "delivery_attempt": attempt,
        "audit": {
            "action": "notification.test_send",
            "resource_type": "notification_channel",
            "resource_id": attempt["channel_id"],
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
        "request_id": x_request_id,
    }


@router.get("/v1/notifications/delivery-attempts")
def list_delivery_attempts(x_request_id: RequestIdHeader = None) -> dict[str, Any]:
    _sync_state()
    return {
        "items": list(_DELIVERY_ATTEMPTS),
        "count": len(_DELIVERY_ATTEMPTS),
        "request_id": x_request_id,
    }
