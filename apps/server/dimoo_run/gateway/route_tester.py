from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_STATE_DATABASE_URL: str | None = None
_REQUEST_LOG_SEQUENCE = 900
_SURFACES: dict[int, dict[str, Any]] = {}
_REQUEST_LOGS: dict[int, list[dict[str, Any]]] = {}
_ROLLOUT_HISTORY: dict[int, list[dict[str, Any]]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def reset_gateway_workflows() -> None:
    global _STATE_DATABASE_URL, _REQUEST_LOG_SEQUENCE
    _STATE_DATABASE_URL = None
    _REQUEST_LOG_SEQUENCE = 900
    _SURFACES.clear()
    _REQUEST_LOGS.clear()
    _ROLLOUT_HISTORY.clear()


def sync_state(database_url: str) -> None:
    global _STATE_DATABASE_URL
    if _STATE_DATABASE_URL != database_url:
        reset_gateway_workflows()
        _STATE_DATABASE_URL = database_url


def validate_publish(surface: dict[str, Any]) -> dict[str, Any]:
    route_path = str(surface.get("route_path") or "")
    auth_mode = str(surface.get("auth_mode") or "")
    environment = surface.get("environment")
    cors_policy = _record(surface.get("cors_policy"))
    rate_limit_policy = _record(surface.get("rate_limit_policy"))
    deployment_id = _positive_int(surface.get("deployment_id"))
    requests_per_minute = _positive_int(rate_limit_policy.get("requests_per_minute"))
    checks = {
        "route_path": {
            "valid": _valid_route_path(route_path),
            "value": route_path,
            "reason": None,
        },
        "auth_mode": {
            "valid": auth_mode in {"api_key", "oauth", "jwt", "mTLS", "mtls"},
            "value": auth_mode,
            "reason": None,
        },
        "deployment_binding": {
            "valid": deployment_id is not None,
            "deployment_id": surface.get("deployment_id"),
            "environment": surface.get("environment"),
            "reason": None,
        },
        "environment_scope": {
            "valid": environment in {"local", "dev", "staging", "production"},
            "environment": environment,
            "reason": None,
        },
        "cors_policy": {
            "valid": _valid_cors_origins(cors_policy.get("allowed_origins")),
            "allowed_origins": cors_policy.get("allowed_origins", []),
            "reason": None,
        },
        "rate_limit_policy": {
            "valid": requests_per_minute is not None,
            "requests_per_minute": rate_limit_policy.get("requests_per_minute"),
            "reason": None,
        },
        "policy_engine": {
            "valid": surface.get("policy_enforced") is True,
            "enforced": surface.get("policy_enforced") is True,
            "reason": None,
        },
    }
    blocked_reasons: list[str] = []
    reason_map = {
        "route_path": "route_path_invalid",
        "auth_mode": "auth_mode_unsafe",
        "deployment_binding": "deployment_binding_missing",
        "environment_scope": "environment_scope_invalid",
        "cors_policy": "cors_wildcard_origin",
        "rate_limit_policy": "rate_limit_missing",
        "policy_engine": "policy_engine_not_enforced",
    }
    for key, check in checks.items():
        if check["valid"]:
            continue
        reason = reason_map[key]
        check["reason"] = reason
        blocked_reasons.append(reason)
    can_publish = not blocked_reasons
    return {
        "status": "valid" if can_publish else "invalid",
        "can_publish": can_publish,
        "checks": checks,
        "blocked_reasons": blocked_reasons,
    }


def publish_surface(
    surface: dict[str, Any],
    *,
    request_id: str | None,
    audit_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validate_publish(surface)
    if not validation["can_publish"]:
        return {
            **validation,
            "status": "blocked",
            "surface": None,
            "rollout": None,
            **_publish_blocked_decision_snapshot(validation["blocked_reasons"]),
        }
    surface_id = _positive_int(surface.get("surface_id")) if "surface_id" in surface else 501
    if surface_id is None:
        blocked_reasons = [*validation["blocked_reasons"], "surface_id_invalid"]
        return {
            **validation,
            "status": "blocked",
            "can_publish": False,
            "surface": None,
            "rollout": None,
            "blocked_reasons": blocked_reasons,
            **_publish_blocked_decision_snapshot(blocked_reasons),
        }
    current = _surface(surface_id)
    deployment_id = surface.get("deployment_id") or current.get("deployment_id") or 10
    rate_limit_policy = _record(surface.get("rate_limit_policy"))
    current.update(
        {
            "id": surface_id,
            "name": str(surface.get("name") or current.get("name") or "support-public-api"),
            "deployment_id": int(deployment_id),
            "status": "active" if validation["can_publish"] else "blocked",
            "environment": str(surface.get("environment") or current.get("environment") or "local"),
            "route_path": str(
                surface.get("route_path") or current.get("route_path") or "/support/triage"
            ),
            "auth_mode": str(surface.get("auth_mode") or current.get("auth_mode") or "api_key"),
            "requests_per_minute": int(
                rate_limit_policy.get(
                    "requests_per_minute",
                    current.get("requests_per_minute", 120),
                )
            ),
            "published_at": _now() if validation["can_publish"] else None,
        }
    )
    version = len(_ROLLOUT_HISTORY.get(surface_id, [])) + 1
    rollout = _append_rollout(
        surface_id,
        {
            "operation": "publish",
            "status": current["status"],
            "version": version,
            "surface_snapshot": _surface_snapshot(current),
            "audit_reason": "validated publish",
            "created_at": _now(),
            "request_id": request_id,
            "audit_scope": _record(audit_scope),
            **_publish_action_decision_snapshot(current),
        },
    )
    return {
        **validation,
        "surface": current,
        "rollout": rollout,
    }


def test_route(payload: dict[str, Any], *, request_id: str | None) -> dict[str, Any]:
    global _REQUEST_LOG_SEQUENCE
    surface_id = _positive_int(payload.get("surface_id")) if "surface_id" in payload else 501
    route_id = _positive_int(payload.get("route_id")) if "route_id" in payload else 701
    blocked_reasons = []
    if surface_id is None:
        blocked_reasons.append("surface_id_invalid")
    if route_id is None:
        blocked_reasons.append("route_id_invalid")
    if blocked_reasons:
        return {
            "status": "blocked",
            "matched_deployment": None,
            "auth_decision": {"result": "not_evaluated"},
            "policy_decision": {"result": "not_evaluated"},
            "expected_runtime_task": None,
            "blocked_reasons": blocked_reasons,
            "request_log": None,
        }
    assert surface_id is not None
    assert route_id is not None
    path = str(payload.get("path") or "/support/triage")
    method = str(payload.get("method") or "POST").upper()
    surface = _surface(surface_id)
    route_blocked_reasons = []
    if path != surface["route_path"]:
        route_blocked_reasons.append("route_not_found")
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        route_blocked_reasons.append("method_not_allowed")
    if route_blocked_reasons:
        return {
            "status": "blocked",
            "matched_deployment": None,
            "auth_decision": {"result": "not_evaluated"},
            "policy_decision": {"result": "not_evaluated"},
            "expected_runtime_task": None,
            "blocked_reasons": route_blocked_reasons,
            "request_log": None,
        }
    surface_status = str(surface.get("status") or "")
    if surface_status != "active":
        reason = (
            "surface_revoked"
            if surface_status == "revoked"
            else "surface_disabled"
            if surface_status == "disabled"
            else "surface_not_active"
        )
        _REQUEST_LOG_SEQUENCE += 1
        log = {
            "id": _REQUEST_LOG_SEQUENCE,
            "surface_id": surface_id,
            "route_id": route_id,
            "deployment_id": surface["deployment_id"],
            "environment": surface["environment"],
            "auth_mode": surface["auth_mode"],
            "path": path,
            "method": method,
            "status": 403,
            "latency_ms": 1,
            "auth_result": "not_evaluated",
            "policy_result": "deny",
            "blocked_reasons": [reason],
            "run_id": None,
            "task_id": None,
            "trace_id": f"trace_{surface_id}_{_REQUEST_LOG_SEQUENCE}",
            "traffic_control": _traffic_control(surface, route_id),
            "redacted_request_metadata": {
                "headers": _redact_headers(_record(payload.get("headers"))),
                "body_keys": sorted(_record(payload.get("body")).keys()),
            },
            "created_at": _now(),
        }
        _REQUEST_LOGS.setdefault(surface_id, []).insert(0, log)
        return {
            "status": "blocked",
            "matched_deployment": {
                "deployment_id": surface["deployment_id"],
                "environment": surface["environment"],
                "surface_id": surface_id,
                "route_id": route_id,
            },
            "auth_decision": {"result": "not_evaluated"},
            "policy_decision": {
                "result": "deny",
                "policy_id": "published-surface-active-state",
            },
            "expected_runtime_task": None,
            "blocked_reasons": [reason],
            "request_log": log,
            "traffic_control": _traffic_control(surface, route_id),
        }
    requests_per_minute = _positive_int(surface.get("requests_per_minute")) or 120
    recent_allowed = sum(
        1 for entry in _REQUEST_LOGS.get(surface_id, []) if entry.get("status") == 200
    )
    if recent_allowed >= requests_per_minute:
        _REQUEST_LOG_SEQUENCE += 1
        log = {
            "id": _REQUEST_LOG_SEQUENCE,
            "surface_id": surface_id,
            "route_id": route_id,
            "deployment_id": surface["deployment_id"],
            "environment": surface["environment"],
            "auth_mode": surface["auth_mode"],
            "path": path,
            "method": method,
            "status": 429,
            "latency_ms": 1,
            "auth_result": "allow",
            "policy_result": "deny",
            "blocked_reasons": ["rate_limited"],
            "run_id": None,
            "task_id": None,
            "trace_id": f"trace_{surface_id}_{_REQUEST_LOG_SEQUENCE}",
            "traffic_control": _traffic_control(surface, route_id),
            "redacted_request_metadata": {
                "headers": _redact_headers(_record(payload.get("headers"))),
                "body_keys": sorted(_record(payload.get("body")).keys()),
            },
            "created_at": _now(),
        }
        _REQUEST_LOGS.setdefault(surface_id, []).insert(0, log)
        return {
            "status": "blocked",
            "matched_deployment": {
                "deployment_id": surface["deployment_id"],
                "environment": surface["environment"],
                "surface_id": surface_id,
                "route_id": route_id,
            },
            "auth_decision": {"result": "allow", "mode": surface["auth_mode"]},
            "policy_decision": {
                "result": "deny",
                "policy_id": "published-surface-rate-limit",
            },
            "expected_runtime_task": None,
            "blocked_reasons": ["rate_limited"],
            "request_log": log,
            "traffic_control": _traffic_control(surface, route_id),
        }
    _REQUEST_LOG_SEQUENCE += 1
    log = {
        "id": _REQUEST_LOG_SEQUENCE,
        "surface_id": surface_id,
        "route_id": route_id,
        "deployment_id": surface["deployment_id"],
        "environment": surface["environment"],
        "auth_mode": surface["auth_mode"],
        "path": path,
        "method": method,
        "status": 200,
        "latency_ms": 42,
        "auth_result": "allow",
        "policy_result": "allow",
        "run_id": 9001,
        "task_id": 8001,
        "trace_id": f"trace_{surface_id}_{_REQUEST_LOG_SEQUENCE}",
        "traffic_control": _traffic_control(surface, route_id),
        "redacted_request_metadata": {
            "headers": _redact_headers(_record(payload.get("headers"))),
            "body_keys": sorted(_record(payload.get("body")).keys()),
        },
        "created_at": _now(),
    }
    _REQUEST_LOGS.setdefault(surface_id, []).insert(0, log)
    return {
        "status": "matched",
        "matched_deployment": {
            "deployment_id": surface["deployment_id"],
            "environment": surface["environment"],
            "surface_id": surface_id,
            "route_id": route_id,
        },
        "auth_decision": {"result": "allow", "mode": surface["auth_mode"]},
        "policy_decision": {"result": "allow", "policy_id": "published-surface-default"},
        "expected_runtime_task": {
            "deployment_id": surface["deployment_id"],
            "task_shape": "deployment.invoke",
            "method": method,
            "path": path,
        },
        "blocked_reasons": [],
        "request_log": log,
        "traffic_control": _traffic_control(surface, route_id),
    }


def rollout_surface(
    surface_id: int,
    payload: dict[str, Any],
    *,
    request_id: str | None,
    audit_scope: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    operation = str(payload.get("operation") or "")
    surface = _surface(surface_id)
    restored_version = None
    if operation not in {"revoke", "disable", "enable", "traffic_split", "shadow_mode", "rollback"}:
        return 409, {
            "error_code": "unsupported_rollout_operation",
            "message": "Rollout operation is not supported for published surfaces.",
            "blocked_reasons": ["rollout_operation_unsupported"],
            "request_id": request_id,
            **_surface_blocked_action_decision_snapshot(
                surface,
                operation or "unknown",
                ["rollout_operation_unsupported"],
            ),
        }
    audit_reason = str(payload.get("audit_reason") or "").strip()
    if operation in {
        "enable",
        "disable",
        "traffic_split",
        "shadow_mode",
        "rollback",
    } and not audit_reason:
        return 409, {
            "error_code": "rollout_audit_reason_required",
            "message": "Rollout control actions require an audit reason.",
            "blocked_reasons": ["audit_reason_required"],
            "request_id": request_id,
            **_surface_blocked_action_decision_snapshot(
                surface,
                operation,
                ["audit_reason_required"],
            ),
        }
    if operation in {"traffic_split", "shadow_mode"} and surface.get("status") != "active":
        blocked_reason = (
            "surface_revoked"
            if surface.get("status") == "revoked"
            else "surface_disabled"
        )
        return 409, {
            "error_code": "surface_inactive",
            "message": "Traffic controls require an active published surface.",
            "blocked_reasons": [blocked_reason],
            "request_id": request_id,
            **_surface_blocked_action_decision_snapshot(
                surface,
                operation,
                [blocked_reason],
            ),
        }
    if operation == "revoke":
        required_confirmation = f"REVOKE SURFACE {surface_id}"
        if payload.get("confirmation") != required_confirmation:
            return 409, {
                "error_code": "dangerous_surface_action_confirmation_required",
                "message": "Surface revoke requires the exact confirmation phrase.",
                "required_confirmation": required_confirmation,
                "blocked_reasons": ["confirmation_required"],
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    ["confirmation_required"],
                ),
            }
        if not audit_reason:
            return 409, {
                "error_code": "rollout_audit_reason_required",
                "message": "Rollout control actions require an audit reason.",
                "blocked_reasons": ["audit_reason_required"],
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    ["audit_reason_required"],
                ),
            }
        if surface.get("status") == "revoked":
            return 409, {
                "error_code": "surface_already_revoked",
                "message": "Surface has already been revoked.",
                "blocked_reasons": ["already_revoked"],
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    ["already_revoked"],
                ),
            }
        surface["status"] = "revoked"
        audit_action = "published_surface.revoke"
    elif operation == "disable":
        if surface.get("status") == "disabled":
            return 409, {
                "error_code": "surface_already_disabled",
                "message": "Surface has already been disabled.",
                "blocked_reasons": ["already_disabled"],
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    ["already_disabled"],
                ),
            }
        surface["status"] = "disabled"
        audit_action = "published_surface.disable"
    elif operation == "enable":
        if surface.get("status") == "active":
            return 409, {
                "error_code": "surface_already_active",
                "message": "Surface is already active.",
                "blocked_reasons": ["already_active"],
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    ["already_active"],
                ),
            }
        if surface.get("status") == "revoked":
            return 409, {
                "error_code": "surface_revoked",
                "message": "Revoked surfaces cannot be enabled.",
                "blocked_reasons": ["surface_revoked"],
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    ["surface_revoked"],
                ),
            }
        surface["status"] = "active"
        audit_action = "published_surface.enable"
    elif operation == "traffic_split":
        valid, blocked_reasons = _validate_traffic_split(payload.get("traffic_split"))
        if not valid:
            return 409, {
                "error_code": "invalid_traffic_split",
                "message": (
                    "Traffic split must contain non-negative integer percentages "
                    "totaling 100."
                ),
                "blocked_reasons": blocked_reasons,
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    blocked_reasons,
                ),
            }
        surface["traffic_split"] = _record(payload.get("traffic_split"))
        audit_action = "published_surface.traffic_split"
    elif operation == "shadow_mode":
        route_id = _positive_int(payload.get("route_id"))
        if route_id is None or not isinstance(payload.get("shadow_mode"), bool):
            blocked_reasons = [
                reason
                for reason, blocked in (
                    ("route_id_invalid", route_id is None),
                    ("shadow_mode_invalid", not isinstance(payload.get("shadow_mode"), bool)),
                )
                if blocked
            ]
            return 409, {
                "error_code": "invalid_shadow_mode",
                "message": "Route shadow mode requires a valid route id and boolean shadow mode.",
                "blocked_reasons": blocked_reasons,
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    blocked_reasons,
                ),
            }
        surface["shadow_route_id"] = route_id
        surface["shadow_mode"] = payload.get("shadow_mode")
        audit_action = "published_surface.shadow_mode"
    elif operation == "rollback":
        rollback_to_version = _positive_int(payload.get("rollback_to_version"))
        if rollback_to_version is None:
            return 409, {
                "error_code": "invalid_rollback_target",
                "message": "Rollback requires a positive rollback target version.",
                "blocked_reasons": ["rollback_target_invalid"],
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    ["rollback_target_invalid"],
                ),
            }
        if not _rollout_version_exists(surface_id, rollback_to_version):
            return 409, {
                "error_code": "rollback_target_not_found",
                "message": "Rollback target version was not found for this surface.",
                "blocked_reasons": ["rollback_target_not_found"],
                "request_id": request_id,
                **_surface_blocked_action_decision_snapshot(
                    surface,
                    operation,
                    ["rollback_target_not_found"],
                ),
            }
        snapshot = _rollout_surface_snapshot(surface_id, rollback_to_version)
        if snapshot is not None:
            surface.update(snapshot)
            restored_version = rollback_to_version
        audit_action = "published_surface.rollback"
    else:
        audit_action = f"published_surface.{operation or 'rollout'}"
    action_snapshot = _surface_action_decision_snapshot(surface, operation)
    rollout = _append_rollout(
        surface_id,
        {
            "operation": operation,
            "route_id": payload.get("route_id"),
            "traffic_split": _record(payload.get("traffic_split")),
            "shadow_mode": payload.get("shadow_mode") is True,
            "rollback_to_version": payload.get("rollback_to_version"),
            "restored_version": restored_version,
            "audit_reason": audit_reason,
            "created_at": _now(),
            "request_id": request_id,
            "audit_scope": _record(audit_scope),
            **action_snapshot,
        },
    )
    return 200, {
        "surface": surface,
        "rollout": rollout,
        "rollout_history": list(_ROLLOUT_HISTORY.get(surface_id, [])),
        "audit": {
            "action": audit_action,
            "resource_type": "published_surface",
            "resource_id": surface_id,
            "request_id": request_id,
        },
    }


def surface_detail(surface_id: int, *, request_id: str | None) -> dict[str, Any]:
    surface = _surface(surface_id)
    status = surface["status"]
    revoked_disabled_reason = "surface_revoked" if status == "revoked" else None
    inactive_disabled_reason = (
        "surface_revoked"
        if status == "revoked"
        else "surface_disabled"
        if status == "disabled"
        else None
    )
    return {
        "surface": surface,
        "deployment_binding_health": {
            "status": "ready",
            "deployment_id": surface["deployment_id"],
            "environment": surface["environment"],
            "runtime_status": "ready",
        },
        "request_logs": list(_REQUEST_LOGS.get(surface_id, [])),
        "rollout_history": list(_ROLLOUT_HISTORY.get(surface_id, [])),
        "actions": {
            "enable": _surface_action(
                surface,
                "enable",
                disabled_reason=(
                    "already_active"
                    if status == "active"
                    else "surface_revoked"
                    if status == "revoked"
                    else None
                ),
            ),
            "disable": _surface_action(
                surface,
                "disable",
                disabled_reason=revoked_disabled_reason
                or ("already_disabled" if status == "disabled" else None),
            ),
            "revoke": _surface_action(
                surface,
                "revoke",
                disabled_reason="already_revoked"
                if status == "revoked"
                else None,
                requires_confirmation=True,
                confirmation=f"REVOKE SURFACE {surface_id}",
            ),
            "traffic_split": _surface_action(
                surface,
                "traffic_split",
                disabled_reason=inactive_disabled_reason,
            ),
            "shadow_mode": _surface_action(
                surface,
                "shadow_mode",
                disabled_reason=inactive_disabled_reason,
            ),
            "rollback": _surface_action(
                surface,
                "rollback",
                disabled_reason=None,
                target_version=1,
                recovery_path="restore_previous_surface_snapshot",
            ),
        },
        "request_id": request_id,
    }


def _surface_action(surface: dict[str, Any], action: str, **fields: Any) -> dict[str, Any]:
    return {
        **fields,
        "audit_required": True,
        **_surface_action_decision_snapshot(surface, action),
    }


def _publish_blocked_decision_snapshot(blocked_reasons: list[str]) -> dict[str, Any]:
    return {
        "permission_summary": {
            "required_permission": "published_surface.publish",
            "actor_permission": "allowed",
        },
        "policy_decision": {
            "result": "deny",
            "policy_id": "published-surface-publish-controls",
        },
        "impact_preview": {
            "affected_resources": ["published_surface:new", "ingress_route:new"],
            "requires_audit_reason": True,
            "expected_runtime_effect": "external_traffic_not_exposed",
            "blocked_reasons": blocked_reasons,
        },
        "audit_preview": {
            "action": "published_surface.publish.blocked",
            "resource_type": "published_surface",
            "resource_id": None,
        },
    }


def _publish_action_decision_snapshot(surface: dict[str, Any]) -> dict[str, Any]:
    surface_id = surface["id"]
    return {
        "permission_summary": {
            "required_permission": "published_surface.publish",
            "actor_permission": "allowed",
        },
        "policy_decision": {
            "result": "allow",
            "policy_id": "published-surface-publish-controls",
        },
        "impact_preview": {
            "surface_id": surface_id,
            "affected_resources": [
                f"published_surface:{surface_id}",
                f"deployment:{surface['deployment_id']}",
                f"ingress_route:{surface.get('route_id', 701)}",
            ],
            "last_known_health": "ready",
            "requires_audit_reason": True,
            "expected_runtime_effect": "external_traffic_exposed",
        },
        "audit_preview": {
            "action": "published_surface.publish",
            "resource_type": "published_surface",
            "resource_id": surface_id,
        },
    }


def _surface_action_decision_snapshot(surface: dict[str, Any], action: str) -> dict[str, Any]:
    surface_id = surface["id"]
    return {
        "permission_summary": {
            "required_permission": f"published_surface.{action}",
            "actor_permission": "allowed",
        },
        "policy_decision": {
            "result": "allow",
            "policy_id": "published-surface-rollout-controls",
        },
        "impact_preview": {
            "surface_id": surface_id,
            "affected_resources": [
                f"published_surface:{surface_id}",
                f"deployment:{surface['deployment_id']}",
                f"ingress_route:{surface.get('route_id', 701)}",
            ],
            "last_known_health": "ready",
            "requires_audit_reason": True,
            "expected_runtime_effect": _surface_action_runtime_effect(action),
        },
        "audit_preview": {
            "action": f"published_surface.{action}",
            "resource_type": "published_surface",
            "resource_id": surface_id,
        },
    }


def _surface_blocked_action_decision_snapshot(
    surface: dict[str, Any],
    action: str,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    snapshot = _surface_action_decision_snapshot(surface, action)
    snapshot["policy_decision"] = {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    snapshot["audit_preview"] = {
        **snapshot["audit_preview"],
        "action": f"published_surface.{action}.blocked",
    }
    snapshot["impact_preview"] = {
        **snapshot["impact_preview"],
        "blocked_reasons": blocked_reasons,
    }
    return snapshot


def _surface_action_runtime_effect(action: str) -> str:
    return {
        "enable": "external_traffic_allowed",
        "disable": "external_traffic_paused",
        "revoke": "external_traffic_denied",
        "traffic_split": "traffic_distribution_changes",
        "shadow_mode": "shadow_route_mirroring_changes",
        "rollback": "surface_snapshot_restored",
    }.get(action, "unsupported_operation_blocked")


def request_log_detail(
    surface_id: int,
    request_log_id: int,
    *,
    request_id: str | None,
) -> dict[str, Any] | None:
    for request_log in _REQUEST_LOGS.get(surface_id, []):
        if request_log.get("id") == request_log_id:
            return {
                "request_log": request_log,
                "audit": {
                    "action": "published_surface.request_log.view",
                    "resource_type": "published_surface_request_log",
                    "resource_id": request_log_id,
                    "surface_id": surface_id,
                    "request_id": request_id,
                },
                "request_id": request_id,
            }
    return None


def _surface(surface_id: int) -> dict[str, Any]:
    surface = _SURFACES.get(surface_id)
    if surface is None:
        surface = {
            "id": surface_id,
            "name": "support-public-api",
            "deployment_id": 10,
            "status": "active",
            "environment": "local",
            "route_path": "/support/triage",
            "auth_mode": "api_key",
        }
        _SURFACES[surface_id] = surface
    return surface


def _append_rollout(surface_id: int, rollout: dict[str, Any]) -> dict[str, Any]:
    rollout = {"id": len(_ROLLOUT_HISTORY.get(surface_id, [])) + 1, **rollout}
    _ROLLOUT_HISTORY.setdefault(surface_id, []).append(rollout)
    return rollout


def _rollout_version_exists(surface_id: int, version: int) -> bool:
    return any(item.get("id") == version for item in _ROLLOUT_HISTORY.get(surface_id, []))


def _rollout_surface_snapshot(surface_id: int, version: int) -> dict[str, Any] | None:
    for item in _ROLLOUT_HISTORY.get(surface_id, []):
        if item.get("id") == version and isinstance(item.get("surface_snapshot"), dict):
            return dict(item["surface_snapshot"])
    return None


def _surface_snapshot(surface: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": surface["id"],
        "name": surface["name"],
        "deployment_id": surface["deployment_id"],
        "status": surface["status"],
        "environment": surface["environment"],
        "route_path": surface["route_path"],
        "auth_mode": surface["auth_mode"],
        "requests_per_minute": surface.get("requests_per_minute", 120),
        "traffic_split": _record(surface.get("traffic_split")),
        "shadow_mode": surface.get("shadow_mode") is True,
        "shadow_route_id": surface.get("shadow_route_id"),
        "published_at": surface.get("published_at"),
    }


def _traffic_control(surface: dict[str, Any], route_id: int) -> dict[str, Any]:
    return {
        "traffic_split": _record(surface.get("traffic_split")) or {
            "stable": 100,
            "candidate": 0,
        },
        "shadow_mode": surface.get("shadow_mode") is True
        and surface.get("shadow_route_id") == route_id,
        "shadow_route_id": surface.get("shadow_route_id"),
    }


def _valid_route_path(value: str) -> bool:
    if not value.startswith("/") or " " in value or "?" in value or "#" in value:
        return False
    parts = value.split("/")[1:]
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def _valid_cors_origins(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    return all(isinstance(item, str) and item.strip() and item != "*" for item in value)


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.isdigit() and not value.startswith("0"):
        parsed = int(value)
    else:
        return None
    return parsed if parsed > 0 else None


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.isdigit() and (value == "0" or not value.startswith("0")):
        parsed = int(value)
    else:
        return None
    return parsed if parsed >= 0 else None


def _validate_traffic_split(value: Any) -> tuple[bool, list[str]]:
    split = _record(value)
    stable = _non_negative_int(split.get("stable"))
    candidate = _non_negative_int(split.get("candidate"))
    blocked_reasons = []
    if stable is None or candidate is None:
        blocked_reasons.append("traffic_split_negative")
    if stable is None or candidate is None or stable + candidate != 100:
        blocked_reasons.append("traffic_split_total_invalid")
    return not blocked_reasons, blocked_reasons


def _redact_headers(headers: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in headers.items():
        redacted[str(key).lower()] = "[REDACTED]" if str(key).lower() == "authorization" else value
    if "authorization" not in redacted:
        redacted["authorization"] = "[REDACTED]"
    return redacted
