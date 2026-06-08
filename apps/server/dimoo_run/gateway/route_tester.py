from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import Table, select

from dimoo_run.domain.models import (
    AuditLog,
    Environment,
    Policy,
    Project,
    PublishedSurfaceBinding,
    PublishedSurfaceEvidenceBundle,
    PublishedSurfaceRequestLog,
    PublishedSurfaceRollout,
    Tenant,
)
from dimoo_run.persistence.database import create_session_factory
from dimoo_run.persistence.repositories import AuditLogRepository
from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import PolicyEngine, PolicyRequest, StaticPolicyRule

_STATE_DATABASE_URL: str | None = None
_REQUEST_LOG_SEQUENCE = 900
_SURFACES: dict[int, dict[str, Any]] = {}
_REQUEST_LOGS: dict[int, list[dict[str, Any]]] = {}
_ROLLOUT_HISTORY: dict[int, list[dict[str, Any]]] = {}
_LIVE_INGRESS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


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
        session_factory = create_session_factory(database_url)
        with session_factory() as session:
            bind = session.get_bind()
            for model in (
                Tenant,
                Project,
                Environment,
                Policy,
                AuditLog,
                PublishedSurfaceBinding,
                PublishedSurfaceEvidenceBundle,
                PublishedSurfaceRequestLog,
                PublishedSurfaceRollout,
            ):
                _table(model).create(bind, checkfirst=True)


def _table(model: type[Any]) -> Table:
    table = model.__table__
    if not isinstance(table, Table):
        raise TypeError(f"{model.__name__} does not expose a SQLAlchemy Table")
    return table


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
    audit_scope_record = _record(audit_scope)
    candidate_surface = {
        "id": surface_id,
        "deployment_id": int(surface.get("deployment_id") or 10),
        "environment": str(surface.get("environment") or "local"),
        "tenant_id": audit_scope_record.get("tenant_id") or 1,
        "project_id": audit_scope_record.get("project_id") or 1,
        "route_path": str(surface.get("route_path") or "/support/triage"),
        "auth_mode": str(surface.get("auth_mode") or "api_key"),
    }
    policy_decision = _evaluate_surface_policy(
        candidate_surface,
        action="publish",
        resource_id=surface_id,
        route_id=701,
        request_metadata={
            "route_path": candidate_surface["route_path"],
            "auth_mode": candidate_surface["auth_mode"],
            "environment": candidate_surface["environment"],
        },
    )
    if policy_decision["result"] not in {"allow", "allow_with_redaction", "allow_with_limit"}:
        blocked_reasons = [str(policy_decision.get("reason") or "policy_denied")]
        return {
            **validation,
            "status": "blocked",
            "can_publish": False,
            "surface": None,
            "rollout": None,
            "blocked_reasons": blocked_reasons,
            **_publish_blocked_decision_snapshot(
                blocked_reasons,
                policy_decision=policy_decision,
            ),
        }
    current = _surface(surface_id)
    deployment_id = surface.get("deployment_id") or current.get("deployment_id") or 10
    rate_limit_policy = _record(surface.get("rate_limit_policy"))
    cors_policy = _record(surface.get("cors_policy"))
    current.update(
        {
            "id": surface_id,
            "name": str(surface.get("name") or current.get("name") or "support-public-api"),
            "deployment_id": int(deployment_id),
            "status": "active" if validation["can_publish"] else "blocked",
            "environment": str(surface.get("environment") or current.get("environment") or "local"),
            "tenant_id": _record(audit_scope).get("tenant_id") or current.get("tenant_id") or 1,
            "project_id": _record(audit_scope).get("project_id") or current.get("project_id") or 1,
            "route_path": str(
                surface.get("route_path") or current.get("route_path") or "/support/triage"
            ),
            "auth_mode": str(surface.get("auth_mode") or current.get("auth_mode") or "api_key"),
            "cors_allowed_origins": list(
                cors_policy.get(
                    "allowed_origins",
                    current.get("cors_allowed_origins", []),
                )
            ),
            "requests_per_minute": int(
                rate_limit_policy.get(
                    "requests_per_minute",
                    current.get("requests_per_minute", 120),
                )
            ),
            "published_at": _now() if validation["can_publish"] else None,
        }
    )
    _persist_surface_binding(current)
    version = len(_surface_rollout_history(surface_id)) + 1
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
    cors_decision = _cors_decision(surface, payload)
    if cors_decision["allowed"] is False:
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
            "blocked_reasons": ["cors_origin_not_allowed"],
            "run_id": None,
            "task_id": None,
            "trace_id": f"trace_{surface_id}_{_REQUEST_LOG_SEQUENCE}",
            "cors": cors_decision,
            "traffic_control": _traffic_control(surface, route_id),
            "redacted_request_metadata": {
                "headers": _redact_headers(_record(payload.get("headers"))),
                "body_keys": sorted(_record(payload.get("body")).keys()),
            },
            "created_at": _now(),
        }
        _attach_request_log_evidence(
            log,
            auth_decision={"result": "not_evaluated"},
            policy_decision={
                "result": "deny",
                "policy_id": "published-surface-cors",
            },
        )
        _record_request_log(surface_id, log)
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
                "policy_id": "published-surface-cors",
            },
            "expected_runtime_task": None,
            "blocked_reasons": ["cors_origin_not_allowed"],
            "cors": cors_decision,
            "request_log": log,
            "traffic_control": _traffic_control(surface, route_id),
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
            "cors": cors_decision,
            "traffic_control": _traffic_control(surface, route_id),
            "redacted_request_metadata": {
                "headers": _redact_headers(_record(payload.get("headers"))),
                "body_keys": sorted(_record(payload.get("body")).keys()),
            },
            "created_at": _now(),
        }
        _attach_request_log_evidence(
            log,
            auth_decision={"result": "not_evaluated"},
            policy_decision={
                "result": "deny",
                "policy_id": "published-surface-active-state",
            },
        )
        _record_request_log(surface_id, log)
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
        1 for entry in _surface_request_logs(surface_id) if entry.get("status") == 200
    )
    if recent_allowed >= requests_per_minute:
        _REQUEST_LOG_SEQUENCE += 1
        rate_limit = {
            "limit": requests_per_minute,
            "remaining": 0,
            "retry_after_seconds": 60,
        }
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
            "rate_limit": rate_limit,
            "cors": cors_decision,
            "traffic_control": _traffic_control(surface, route_id),
            "redacted_request_metadata": {
                "headers": _redact_headers(_record(payload.get("headers"))),
                "body_keys": sorted(_record(payload.get("body")).keys()),
            },
            "created_at": _now(),
        }
        _attach_request_log_evidence(
            log,
            auth_decision={"result": "allow", "mode": surface["auth_mode"]},
            policy_decision={
                "result": "deny",
                "policy_id": "published-surface-rate-limit",
            },
        )
        _record_request_log(surface_id, log)
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
            "rate_limit": rate_limit,
            "request_log": log,
            "traffic_control": _traffic_control(surface, route_id),
        }
    policy_decision = _evaluate_surface_policy(
        surface,
        action="ingress.invoke",
        resource_id=surface_id,
        route_id=route_id,
        request_metadata={
            "path": path,
            "method": method,
            "headers": _redact_headers(_record(payload.get("headers"))),
            "body_keys": sorted(_record(payload.get("body")).keys()),
        },
    )
    if policy_decision["result"] not in {"allow", "allow_with_redaction", "allow_with_limit"}:
        blocked_reason = str(policy_decision.get("reason") or "policy_denied")
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
            "auth_result": "allow",
            "policy_result": "deny",
            "blocked_reasons": [blocked_reason],
            "run_id": None,
            "task_id": None,
            "trace_id": f"trace_{surface_id}_{_REQUEST_LOG_SEQUENCE}",
            "cors": cors_decision,
            "traffic_control": _traffic_control(surface, route_id),
            "redacted_request_metadata": {
                "headers": _redact_headers(_record(payload.get("headers"))),
                "body_keys": sorted(_record(payload.get("body")).keys()),
            },
            "created_at": _now(),
        }
        _attach_request_log_evidence(
            log,
            auth_decision={"result": "allow", "mode": surface["auth_mode"]},
            policy_decision=policy_decision,
        )
        _record_request_log(surface_id, log)
        return {
            "status": "blocked",
            "matched_deployment": {
                "deployment_id": surface["deployment_id"],
                "environment": surface["environment"],
                "surface_id": surface_id,
                "route_id": route_id,
            },
            "auth_decision": {"result": "allow", "mode": surface["auth_mode"]},
            "policy_decision": policy_decision,
            "expected_runtime_task": None,
            "blocked_reasons": [blocked_reason],
            "request_log": log,
            "traffic_control": _traffic_control(surface, route_id),
        }

    policy_effects = _policy_effects(policy_decision)
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
        "policy_result": policy_decision["result"],
        "run_id": 9001,
        "task_id": 8001,
        "trace_id": f"trace_{surface_id}_{_REQUEST_LOG_SEQUENCE}",
        "cors": cors_decision,
        "traffic_control": _traffic_control(surface, route_id),
        "redacted_request_metadata": {
            "headers": _redact_headers(_record(payload.get("headers"))),
            "body_keys": sorted(_record(payload.get("body")).keys()),
        },
        "created_at": _now(),
    }
    if policy_effects:
        log["policy_effects"] = policy_effects
    _attach_request_log_evidence(
        log,
        auth_decision={"result": "allow", "mode": surface["auth_mode"]},
        policy_decision=policy_decision,
    )
    _record_request_log(surface_id, log)
    return {
        "status": "matched",
        "matched_deployment": {
            "deployment_id": surface["deployment_id"],
            "environment": surface["environment"],
            "surface_id": surface_id,
            "route_id": route_id,
        },
        "auth_decision": {"result": "allow", "mode": surface["auth_mode"]},
        "policy_decision": policy_decision,
        "cors": cors_decision,
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


def handle_live_ingress(
    *,
    path: str,
    method: str,
    headers: dict[str, Any],
    body: dict[str, Any],
    request_id: str | None,
) -> tuple[int, dict[str, Any]]:
    effective_request_id = request_id or f"req_live_{uuid4().hex}"
    route_path = "/" + path.strip("/")
    surface = _surface_for_published_route(route_path)
    if surface is None:
        return 404, {
            "status": "blocked",
            "error_code": "ingress_route_not_found",
            "message": "No published surface is bound to this ingress route.",
            "blocked_reasons": ["route_not_found"],
            "request_id": effective_request_id,
        }
    if method.upper() == "OPTIONS":
        return _handle_live_ingress_preflight(
            surface=surface,
            headers=headers,
            request_id=effective_request_id,
        )
    result = test_route(
        {
            "surface_id": surface["id"],
            "route_id": surface.get("route_id", 701),
            "path": route_path,
            "method": method,
            "headers": headers,
            "body": body,
        },
        request_id=effective_request_id,
    )
    request_log = result.get("request_log")
    traffic_control = _record(result.get("traffic_control"))
    traffic_control_decision = _traffic_control_decision(traffic_control)
    if isinstance(request_log, dict):
        request_log["ingress_source"] = "live_http"
        request_log["request_id"] = effective_request_id
        request_log["traffic_control_decision"] = traffic_control_decision
        evidence_bundle = request_log.get("evidence_bundle")
        if isinstance(evidence_bundle, dict):
            evidence_bundle["request_id"] = effective_request_id
        _persist_request_log(request_log)
    if result.get("status") == "matched":
        return 200, {
            "status": "accepted",
            "trace_id": request_log.get("trace_id") if isinstance(request_log, dict) else None,
            "request_log_id": request_log.get("id") if isinstance(request_log, dict) else None,
            "matched_deployment": result.get("matched_deployment"),
            "auth_decision": result.get("auth_decision"),
            "policy_decision": result.get("policy_decision"),
            "cors": result.get("cors"),
            "traffic_control_decision": traffic_control_decision,
            "runtime_task": result.get("expected_runtime_task"),
            "request_id": effective_request_id,
        }
    status_code = request_log.get("status") if isinstance(request_log, dict) else None
    http_status = status_code if isinstance(status_code, int) else 403
    return http_status, {
        "status": "blocked",
        "trace_id": request_log.get("trace_id") if isinstance(request_log, dict) else None,
        "request_log_id": request_log.get("id") if isinstance(request_log, dict) else None,
        "matched_deployment": result.get("matched_deployment"),
        "auth_decision": result.get("auth_decision"),
        "policy_decision": result.get("policy_decision"),
        "cors": result.get("cors"),
        "traffic_control_decision": traffic_control_decision,
        "blocked_reasons": result.get("blocked_reasons", []),
        "rate_limit": result.get("rate_limit"),
        "request_id": effective_request_id,
    }


def _handle_live_ingress_preflight(
    *,
    surface: dict[str, Any],
    headers: dict[str, Any],
    request_id: str,
) -> tuple[int, dict[str, Any]]:
    cors_decision = _cors_decision(surface, {"headers": headers})
    if cors_decision["allowed"] is False:
        return 403, {
            "status": "blocked",
            "blocked_reasons": ["cors_origin_not_allowed"],
            "cors": cors_decision,
            "request_id": request_id,
        }

    requested_method = (_header_value(headers, "access-control-request-method") or "").upper()
    if requested_method not in _LIVE_INGRESS_METHODS:
        return 405, {
            "status": "blocked",
            "blocked_reasons": ["method_not_allowed"],
            "cors": cors_decision,
            "request_id": request_id,
        }

    requested_headers = _header_value(headers, "access-control-request-headers")
    return 204, {
        "status": "preflight_allowed",
        "cors": {
            **cors_decision,
            "preflight": True,
            "allow_methods": _LIVE_INGRESS_METHODS,
            "allow_headers": requested_headers,
        },
        "request_id": request_id,
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
    live_gateway_verification: dict[str, Any] | None = None
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
            live_gateway_verification = {
                "status": "ready_for_live_ingress",
                "verification_mode": "in_process_route_binding",
                "restored_route_path": surface["route_path"],
                "restored_deployment_id": surface["deployment_id"],
                "restored_environment": surface["environment"],
                "restored_auth_mode": surface["auth_mode"],
            }
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
            "live_gateway_verification": _record(live_gateway_verification),
            "audit_reason": audit_reason,
            "created_at": _now(),
            "request_id": request_id,
            "audit_scope": _record(audit_scope),
            **action_snapshot,
        },
    )
    _persist_surface_binding(surface)
    return 200, {
        "surface": surface,
        "rollout": rollout,
        "rollout_history": _surface_rollout_history(surface_id),
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
        "exposure_health": _exposure_health(surface),
        "request_logs": _surface_request_logs(surface_id),
        "rollout_history": _surface_rollout_history(surface_id),
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


def _publish_blocked_decision_snapshot(
    blocked_reasons: list[str],
    *,
    policy_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "permission_summary": {
            "required_permission": "published_surface.publish",
            "actor_permission": "allowed",
        },
        "policy_decision": policy_decision
        or {
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


def _exposure_health(surface: dict[str, Any]) -> dict[str, Any]:
    surface_id = int(surface["id"])
    live_log = next(
        (
            request_log
            for request_log in _surface_request_logs(surface_id)
            if request_log.get("ingress_source") == "live_http"
        ),
        None,
    )
    blocked_reasons = _exposure_blocked_reasons(surface, live_log)
    return {
        "status": "ready" if not blocked_reasons else "blocked",
        "route_path": surface.get("route_path"),
        "published": bool(surface.get("published_at")) and str(surface.get("status")) == "active",
        "last_live_request_status": live_log.get("status") if live_log else None,
        "last_live_request_id": live_log.get("id") if live_log else None,
        "last_live_trace_id": live_log.get("trace_id") if live_log else None,
        "blocked_reasons": blocked_reasons,
    }


def _exposure_blocked_reasons(
    surface: dict[str, Any],
    live_log: dict[str, Any] | None,
) -> list[str]:
    status = str(surface.get("status") or "")
    if status == "revoked":
        return ["surface_revoked"]
    if status == "disabled":
        return ["surface_disabled"]
    if status != "active":
        return ["surface_not_active"]
    if not surface.get("published_at"):
        return ["surface_not_published"]
    if live_log is None:
        return ["live_ingress_not_proven"]
    if int(live_log.get("status") or 0) >= 400:
        reasons = live_log.get("blocked_reasons")
        return (
            [str(reason) for reason in reasons]
            if isinstance(reasons, list)
            else ["last_probe_failed"]
        )
    return []


def request_log_detail(
    surface_id: int,
    request_log_id: int,
    *,
    request_id: str | None,
) -> dict[str, Any] | None:
    for request_log in _surface_request_logs(surface_id):
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


def evidence_bundle_export(
    surface_id: int,
    bundle_id: str,
    *,
    request_id: str | None,
) -> dict[str, Any] | None:
    for request_log in _surface_request_logs(surface_id):
        evidence_bundle = _record(request_log.get("evidence_bundle"))
        if evidence_bundle.get("bundle_id") != bundle_id:
            continue
        redacted_payload = {
            "request_log_id": request_log.get("id"),
            "status": request_log.get("status"),
            "method": request_log.get("method"),
            "path": request_log.get("path"),
            "trace_id": request_log.get("trace_id"),
            "request_metadata": _record(request_log.get("redacted_request_metadata")),
            "policy_decision": evidence_bundle.get("policy_decision"),
            "traffic_control": evidence_bundle.get("traffic_control"),
        }
        _record_evidence_bundle_export_audit(
            surface_id=surface_id,
            evidence_bundle=evidence_bundle,
            redacted_payload_summary={
                "kind": "request_log",
                "request_log_id": request_log.get("id"),
                "status": request_log.get("status"),
                "trace_id": request_log.get("trace_id"),
            },
            request_id=request_id,
        )
        return {
            "export_format": "redacted_json",
            "evidence_bundle": evidence_bundle,
            "redacted_payload": redacted_payload,
            "audit": {
                "action": "published_surface.evidence_bundle.export",
                "resource_type": "published_surface_evidence_bundle",
                "resource_id": bundle_id,
                "surface_id": surface_id,
                "request_id": request_id,
            },
            "request_id": request_id,
        }
    for rollout in _surface_rollout_history(surface_id):
        evidence_bundle = _record(rollout.get("evidence_bundle"))
        if evidence_bundle.get("bundle_id") != bundle_id:
            continue
        redacted_payload = {
            "rollout_id": rollout.get("id"),
            "operation": rollout.get("operation"),
            "traffic_split": _record(rollout.get("traffic_split")),
            "shadow_mode": rollout.get("shadow_mode"),
            "rollback_to_version": rollout.get("rollback_to_version"),
            "audit_scope": _record(rollout.get("audit_scope")),
            "policy_decision": evidence_bundle.get("policy_decision"),
            "impact_preview": evidence_bundle.get("impact_preview"),
        }
        _record_evidence_bundle_export_audit(
            surface_id=surface_id,
            evidence_bundle=evidence_bundle,
            redacted_payload_summary={
                "kind": "rollout",
                "rollout_id": rollout.get("id"),
                "operation": rollout.get("operation"),
            },
            request_id=request_id,
        )
        return {
            "export_format": "redacted_json",
            "evidence_bundle": evidence_bundle,
            "redacted_payload": redacted_payload,
            "audit": {
                "action": "published_surface.evidence_bundle.export",
                "resource_type": "published_surface_evidence_bundle",
                "resource_id": bundle_id,
                "surface_id": surface_id,
                "request_id": request_id,
            },
            "request_id": request_id,
        }
    return None


def evidence_bundle_archive(
    surface_id: int,
    bundle_id: str,
    payload: dict[str, Any],
    *,
    request_id: str | None,
) -> dict[str, Any] | None:
    evidence_bundle = _find_evidence_bundle(surface_id, bundle_id)
    if evidence_bundle is None:
        return None

    retention_days = int(payload.get("retention_days") or 30)
    now = datetime.now(UTC)
    retain_until = now + timedelta(days=retention_days)
    retention = {
        "policy_id": str(payload.get("retention_policy_id") or "gateway-evidence-default"),
        "retention_days": retention_days,
        "retain_until": retain_until.isoformat(),
        "archived_at": now.isoformat(),
    }
    archive_reason = str(payload.get("archive_reason") or "Evidence bundle archived.")
    _record_evidence_bundle_archive_audit(
        surface_id=surface_id,
        evidence_bundle=evidence_bundle,
        retention=retention,
        archive_reason=archive_reason,
        archived_at=now,
        retain_until=retain_until,
        request_id=request_id,
    )
    return {
        "status": "archived",
        "evidence_bundle": evidence_bundle,
        "retention": retention,
        "audit": {
            "action": "published_surface.evidence_bundle.archive",
            "resource_type": "published_surface_evidence_bundle",
            "resource_id": bundle_id,
            "surface_id": surface_id,
            "request_id": request_id,
        },
        "request_id": request_id,
    }


def evidence_bundle_catalog(surface_id: int, *, request_id: str | None) -> dict[str, Any]:
    recorded_bundle_ids = _recorded_evidence_bundle_ids(surface_id)
    lifecycle_by_bundle_id = _evidence_bundle_lifecycle_index(surface_id)
    items: list[dict[str, Any]] = []
    for request_log in _surface_request_logs(surface_id):
        evidence_bundle = _record(request_log.get("evidence_bundle"))
        bundle_id = str(evidence_bundle.get("bundle_id") or "")
        if not bundle_id:
            continue
        items.append(
            {
                "bundle_id": bundle_id,
                "resource_type": evidence_bundle.get("resource_type"),
                "surface_id": surface_id,
                "request_log_id": evidence_bundle.get("request_log_id"),
                "route_id": evidence_bundle.get("route_id"),
                "deployment_id": evidence_bundle.get("deployment_id"),
                "environment": evidence_bundle.get("environment"),
                "trace_id": evidence_bundle.get("trace_id"),
                "created_at": evidence_bundle.get("created_at"),
                "export_url": _evidence_bundle_export_url(surface_id, bundle_id),
                "audit_index": _evidence_bundle_audit_index(bundle_id, recorded_bundle_ids),
                "lifecycle": lifecycle_by_bundle_id.get(
                    bundle_id, _default_evidence_bundle_lifecycle()
                ),
            }
        )
    for rollout in _surface_rollout_history(surface_id):
        evidence_bundle = _record(rollout.get("evidence_bundle"))
        bundle_id = str(evidence_bundle.get("bundle_id") or "")
        if not bundle_id:
            continue
        items.append(
            {
                "bundle_id": bundle_id,
                "resource_type": evidence_bundle.get("resource_type"),
                "surface_id": surface_id,
                "rollout_id": evidence_bundle.get("rollout_id"),
                "operation": evidence_bundle.get("operation"),
                "created_at": evidence_bundle.get("created_at"),
                "export_url": _evidence_bundle_export_url(surface_id, bundle_id),
                "audit_index": _evidence_bundle_audit_index(bundle_id, recorded_bundle_ids),
                "lifecycle": lifecycle_by_bundle_id.get(
                    bundle_id, _default_evidence_bundle_lifecycle()
                ),
            }
        )
    return {
        "surface_id": surface_id,
        "items": items,
        "count": len(items),
        "audit": {
            "action": "published_surface.evidence_bundle.list",
            "resource_type": "published_surface_evidence_bundle",
            "resource_id": surface_id,
            "request_id": request_id,
        },
        "request_id": request_id,
    }


def _find_evidence_bundle(surface_id: int, bundle_id: str) -> dict[str, Any] | None:
    for request_log in _surface_request_logs(surface_id):
        evidence_bundle = _record(request_log.get("evidence_bundle"))
        if evidence_bundle.get("bundle_id") == bundle_id:
            return evidence_bundle
    for rollout in _surface_rollout_history(surface_id):
        evidence_bundle = _record(rollout.get("evidence_bundle"))
        if evidence_bundle.get("bundle_id") == bundle_id:
            return evidence_bundle
    return None


def _record_request_log(surface_id: int, log: dict[str, Any]) -> None:
    _REQUEST_LOGS.setdefault(surface_id, []).insert(0, log)
    _persist_request_log(log)


def _record_rollout(surface_id: int, rollout: dict[str, Any]) -> None:
    _ROLLOUT_HISTORY.setdefault(surface_id, []).append(rollout)
    _persist_rollout(surface_id, rollout)


def _surface_request_logs(surface_id: int) -> list[dict[str, Any]]:
    logs_by_id: dict[int, dict[str, Any]] = {}
    ordered_logs: list[dict[str, Any]] = []
    for log in _REQUEST_LOGS.get(surface_id, []):
        log_id = _positive_int(log.get("id"))
        if log_id is None:
            continue
        logs_by_id[log_id] = log
        ordered_logs.append(log)
    for log in _persisted_request_logs(surface_id):
        log_id = _positive_int(log.get("id"))
        if log_id is None or log_id in logs_by_id:
            continue
        logs_by_id[log_id] = log
        ordered_logs.append(log)
    ordered_logs.sort(key=lambda item: _positive_int(item.get("id")) or 0, reverse=True)
    return ordered_logs


def _surface_rollout_history(surface_id: int) -> list[dict[str, Any]]:
    rollouts_by_id: dict[int, dict[str, Any]] = {}
    ordered_rollouts: list[dict[str, Any]] = []
    for rollout in _ROLLOUT_HISTORY.get(surface_id, []):
        rollout_id = _positive_int(rollout.get("id"))
        if rollout_id is None:
            continue
        rollouts_by_id[rollout_id] = rollout
        ordered_rollouts.append(rollout)
    for rollout in _persisted_rollouts(surface_id):
        rollout_id = _positive_int(rollout.get("id"))
        if rollout_id is None or rollout_id in rollouts_by_id:
            continue
        rollouts_by_id[rollout_id] = rollout
        ordered_rollouts.append(rollout)
    ordered_rollouts.sort(key=lambda item: _positive_int(item.get("id")) or 0)
    return ordered_rollouts


def _persist_request_log(log: dict[str, Any]) -> None:
    if _STATE_DATABASE_URL is None:
        return
    surface_id = _positive_int(log.get("surface_id"))
    request_log_id = _positive_int(log.get("id"))
    status_code = _positive_int(log.get("status"))
    if surface_id is None or request_log_id is None or status_code is None:
        return
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        record = session.scalar(
            select(PublishedSurfaceRequestLog).where(
                PublishedSurfaceRequestLog.surface_id == surface_id,
                PublishedSurfaceRequestLog.request_log_id == request_log_id,
                PublishedSurfaceRequestLog.is_deleted.is_(False),
            )
        )
        if record is None:
            record = PublishedSurfaceRequestLog(
                tenant_id=_positive_int(log.get("tenant_id")) or 1,
                project_id=_positive_int(log.get("project_id")) or 1,
                surface_id=surface_id,
                request_log_id=request_log_id,
                status_code=status_code,
                method=str(log.get("method") or ""),
                path=str(log.get("path") or ""),
                trace_id=_optional_string(log.get("trace_id")),
                request_id=_optional_string(log.get("request_id")),
                ingress_source=(
                    _optional_string(log.get("ingress_source"))
                ),
                request_log_json=log,
                evidence_bundle_json=_record(log.get("evidence_bundle")),
            )
            session.add(record)
        else:
            record.status_code = status_code
            record.method = str(log.get("method") or "")
            record.path = str(log.get("path") or "")
            record.trace_id = _optional_string(log.get("trace_id"))
            record.request_id = _optional_string(log.get("request_id"))
            record.ingress_source = _optional_string(log.get("ingress_source"))
            record.request_log_json = log
            record.evidence_bundle_json = _record(log.get("evidence_bundle"))
        session.commit()


def _persist_rollout(surface_id: int, rollout: dict[str, Any]) -> None:
    if _STATE_DATABASE_URL is None:
        return
    rollout_id = _positive_int(rollout.get("id"))
    if rollout_id is None:
        return
    audit_scope = _record(rollout.get("audit_scope"))
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        record = session.scalar(
            select(PublishedSurfaceRollout).where(
                PublishedSurfaceRollout.surface_id == surface_id,
                PublishedSurfaceRollout.rollout_id == rollout_id,
                PublishedSurfaceRollout.is_deleted.is_(False),
            )
        )
        if record is None:
            record = PublishedSurfaceRollout(
                tenant_id=_positive_int(audit_scope.get("tenant_id")) or 1,
                project_id=_positive_int(audit_scope.get("project_id")) or 1,
                surface_id=surface_id,
                rollout_id=rollout_id,
                operation=str(rollout.get("operation") or ""),
                request_id=_optional_string(rollout.get("request_id")),
                rollout_json=rollout,
                evidence_bundle_json=_record(rollout.get("evidence_bundle")),
            )
            session.add(record)
        else:
            record.operation = str(rollout.get("operation") or "")
            record.request_id = _optional_string(rollout.get("request_id"))
            record.rollout_json = rollout
            record.evidence_bundle_json = _record(rollout.get("evidence_bundle"))
        session.commit()


def _persisted_request_logs(surface_id: int) -> list[dict[str, Any]]:
    if _STATE_DATABASE_URL is None:
        return []
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        records = session.scalars(
            select(PublishedSurfaceRequestLog)
            .where(
                PublishedSurfaceRequestLog.surface_id == surface_id,
                PublishedSurfaceRequestLog.is_deleted.is_(False),
            )
            .order_by(PublishedSurfaceRequestLog.request_log_id.desc())
        )
        return [dict(record.request_log_json) for record in records]


def _persisted_rollouts(surface_id: int) -> list[dict[str, Any]]:
    if _STATE_DATABASE_URL is None:
        return []
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        records = session.scalars(
            select(PublishedSurfaceRollout)
            .where(
                PublishedSurfaceRollout.surface_id == surface_id,
                PublishedSurfaceRollout.is_deleted.is_(False),
            )
            .order_by(PublishedSurfaceRollout.rollout_id.asc())
        )
        return [dict(record.rollout_json) for record in records]


def _persist_surface_binding(surface: dict[str, Any]) -> None:
    if _STATE_DATABASE_URL is None:
        return
    surface_id = _positive_int(surface.get("id"))
    deployment_id = _positive_int(surface.get("deployment_id"))
    if surface_id is None or deployment_id is None:
        return
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        record = session.scalar(
            select(PublishedSurfaceBinding).where(
                PublishedSurfaceBinding.surface_id == surface_id,
                PublishedSurfaceBinding.is_deleted.is_(False),
            )
        )
        if record is None:
            record = PublishedSurfaceBinding(
                tenant_id=_positive_int(surface.get("tenant_id")) or 1,
                project_id=_positive_int(surface.get("project_id")) or 1,
                surface_id=surface_id,
                name=str(surface.get("name") or "support-public-api"),
                deployment_id=deployment_id,
                status=str(surface.get("status") or "active"),
                environment=str(surface.get("environment") or "local"),
                route_path=str(surface.get("route_path") or "/support/triage"),
                auth_mode=str(surface.get("auth_mode") or "api_key"),
                published_at=_optional_string(surface.get("published_at")),
                surface_json=surface,
            )
            session.add(record)
        else:
            record.tenant_id = _positive_int(surface.get("tenant_id")) or 1
            record.project_id = _positive_int(surface.get("project_id")) or 1
            record.name = str(surface.get("name") or "support-public-api")
            record.deployment_id = deployment_id
            record.status = str(surface.get("status") or "active")
            record.environment = str(surface.get("environment") or "local")
            record.route_path = str(surface.get("route_path") or "/support/triage")
            record.auth_mode = str(surface.get("auth_mode") or "api_key")
            record.published_at = _optional_string(surface.get("published_at"))
            record.surface_json = surface
        session.commit()


def _persisted_surface(surface_id: int) -> dict[str, Any] | None:
    if _STATE_DATABASE_URL is None:
        return None
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        record = session.scalar(
            select(PublishedSurfaceBinding).where(
                PublishedSurfaceBinding.surface_id == surface_id,
                PublishedSurfaceBinding.is_deleted.is_(False),
            )
        )
        return dict(record.surface_json) if record is not None else None


def _persisted_surface_for_route(route_path: str) -> dict[str, Any] | None:
    if _STATE_DATABASE_URL is None:
        return None
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        record = session.scalar(
            select(PublishedSurfaceBinding).where(
                PublishedSurfaceBinding.route_path == route_path,
                PublishedSurfaceBinding.published_at.is_not(None),
                PublishedSurfaceBinding.is_deleted.is_(False),
            )
        )
        return dict(record.surface_json) if record is not None else None


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _surface(surface_id: int) -> dict[str, Any]:
    surface = _SURFACES.get(surface_id)
    if surface is None:
        persisted_surface = _persisted_surface(surface_id)
        if persisted_surface is not None:
            _SURFACES[surface_id] = persisted_surface
            return persisted_surface
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


def _surface_for_published_route(route_path: str) -> dict[str, Any] | None:
    for surface in _SURFACES.values():
        if surface.get("route_path") == route_path and surface.get("published_at"):
            return surface
    persisted_surface = _persisted_surface_for_route(route_path)
    if persisted_surface is not None:
        surface_id = _positive_int(persisted_surface.get("id"))
        if surface_id is not None:
            _SURFACES[surface_id] = persisted_surface
        return persisted_surface
    return None


def _cors_decision(surface: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    headers = _record(payload.get("headers"))
    origin = _header_value(headers, "origin")
    if not origin:
        return {"origin": None, "allowed": None}
    allowed_origins = [
        str(origin_value)
        for origin_value in surface.get("cors_allowed_origins", [])
        if isinstance(origin_value, str)
    ]
    return {"origin": origin, "allowed": origin in allowed_origins}


def _header_value(headers: dict[str, Any], name: str) -> str | None:
    expected = name.lower()
    for key, value in headers.items():
        if str(key).lower() == expected and isinstance(value, str) and value:
            return value
    return None


def _append_rollout(surface_id: int, rollout: dict[str, Any]) -> dict[str, Any]:
    rollout = {"id": len(_surface_rollout_history(surface_id)) + 1, **rollout}
    rollout["evidence_bundle"] = _rollout_evidence_bundle(surface_id, rollout)
    _record_rollout(surface_id, rollout)
    return rollout


def _attach_request_log_evidence(
    log: dict[str, Any],
    *,
    auth_decision: dict[str, Any],
    policy_decision: dict[str, Any],
) -> None:
    surface_id = int(log["surface_id"])
    request_log_id = int(log["id"])
    log["evidence_bundle"] = {
        "bundle_id": f"published-surface-request-log-{surface_id}-{request_log_id}",
        "resource_type": "published_surface_request_log",
        "surface_id": surface_id,
        "request_log_id": request_log_id,
        "route_id": log.get("route_id"),
        "deployment_id": log.get("deployment_id"),
        "environment": log.get("environment"),
        "trace_id": log.get("trace_id"),
        "status": log.get("status"),
        "auth_decision": auth_decision,
        "policy_decision": policy_decision,
        "traffic_control": _record(log.get("traffic_control")),
        "rate_limit": _record(log.get("rate_limit")),
        "cors": _record(log.get("cors")),
        "redaction": {
            "headers": ["authorization"],
            "body": "keys_only",
        },
        "created_at": log.get("created_at"),
    }
    _record_evidence_bundle_audit(
        surface_id=surface_id,
        evidence_bundle=log["evidence_bundle"],
        request_id=log.get("request_id") if isinstance(log.get("request_id"), str) else None,
    )


def _rollout_evidence_bundle(surface_id: int, rollout: dict[str, Any]) -> dict[str, Any]:
    rollout_id = int(rollout["id"])
    evidence_bundle = {
        "bundle_id": f"published-surface-rollout-{surface_id}-{rollout_id}",
        "resource_type": "published_surface_rollout",
        "surface_id": surface_id,
        "rollout_id": rollout_id,
        "operation": rollout.get("operation"),
        "policy_decision": _record(rollout.get("policy_decision")),
        "impact_preview": _record(rollout.get("impact_preview")),
        "audit_preview": _record(rollout.get("audit_preview")),
        "audit_scope": _record(rollout.get("audit_scope")),
        "live_gateway_verification": _record(rollout.get("live_gateway_verification")),
        "created_at": rollout.get("created_at"),
    }
    _record_evidence_bundle_audit(
        surface_id=surface_id,
        evidence_bundle=evidence_bundle,
        request_id=(
            rollout.get("request_id") if isinstance(rollout.get("request_id"), str) else None
        ),
    )
    return evidence_bundle


def _record_evidence_bundle_audit(
    *,
    surface_id: int,
    evidence_bundle: dict[str, Any],
    request_id: str | None,
) -> None:
    if _STATE_DATABASE_URL is None:
        return
    tenant_id = int(evidence_bundle.get("audit_scope", {}).get("tenant_id") or 1)
    project_id = evidence_bundle.get("audit_scope", {}).get("project_id")
    if project_id is None:
        project_id = 1
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        _upsert_evidence_bundle_record(
            session=session,
            surface_id=surface_id,
            tenant_id=tenant_id,
            project_id=int(project_id),
            evidence_bundle=evidence_bundle,
        )
        AuditLogRepository(session).append(
            tenant_id=tenant_id,
            project_id=int(project_id),
            action="published_surface.evidence_bundle.record",
            resource_type="published_surface_evidence_bundle",
            resource_id=surface_id,
            result="recorded",
            actor_type="system",
            request_id=request_id,
            metadata={"evidence_bundle": evidence_bundle},
        )
        session.commit()


def _record_evidence_bundle_export_audit(
    *,
    surface_id: int,
    evidence_bundle: dict[str, Any],
    redacted_payload_summary: dict[str, Any],
    request_id: str | None,
) -> None:
    if _STATE_DATABASE_URL is None:
        return
    tenant_id = int(evidence_bundle.get("audit_scope", {}).get("tenant_id") or 1)
    project_id = evidence_bundle.get("audit_scope", {}).get("project_id")
    if project_id is None:
        project_id = 1
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        _mark_evidence_bundle_exported(
            session=session,
            surface_id=surface_id,
            evidence_bundle=evidence_bundle,
            redacted_payload_summary=redacted_payload_summary,
            request_id=request_id,
        )
        AuditLogRepository(session).append(
            tenant_id=tenant_id,
            project_id=int(project_id),
            action="published_surface.evidence_bundle.export",
            resource_type="published_surface_evidence_bundle",
            resource_id=surface_id,
            result="exported",
            actor_type="system",
            request_id=request_id,
            metadata={
                "export_format": "redacted_json",
                "evidence_bundle": evidence_bundle,
                "redacted_payload_summary": redacted_payload_summary,
            },
        )
        session.commit()


def _record_evidence_bundle_archive_audit(
    *,
    surface_id: int,
    evidence_bundle: dict[str, Any],
    retention: dict[str, Any],
    archive_reason: str,
    archived_at: datetime,
    retain_until: datetime,
    request_id: str | None,
) -> None:
    if _STATE_DATABASE_URL is None:
        return
    tenant_id = int(evidence_bundle.get("audit_scope", {}).get("tenant_id") or 1)
    project_id = evidence_bundle.get("audit_scope", {}).get("project_id")
    if project_id is None:
        project_id = 1
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        _mark_evidence_bundle_archived(
            session=session,
            surface_id=surface_id,
            evidence_bundle=evidence_bundle,
            retention=retention,
            archive_reason=archive_reason,
            archived_at=archived_at,
            retain_until=retain_until,
            request_id=request_id,
        )
        AuditLogRepository(session).append(
            tenant_id=tenant_id,
            project_id=int(project_id),
            action="published_surface.evidence_bundle.archive",
            resource_type="published_surface_evidence_bundle",
            resource_id=surface_id,
            result="archived",
            actor_type="system",
            request_id=request_id,
            metadata={
                "evidence_bundle": _evidence_bundle_identity(evidence_bundle),
                "retention": retention,
                "archive_reason": archive_reason,
            },
        )
        session.commit()


def _upsert_evidence_bundle_record(
    *,
    session: Any,
    surface_id: int,
    tenant_id: int,
    project_id: int,
    evidence_bundle: dict[str, Any],
) -> None:
    bundle_id = str(evidence_bundle.get("bundle_id") or "")
    if not bundle_id:
        return
    record = session.scalar(
        select(PublishedSurfaceEvidenceBundle).where(
            PublishedSurfaceEvidenceBundle.surface_id == surface_id,
            PublishedSurfaceEvidenceBundle.bundle_id == bundle_id,
            PublishedSurfaceEvidenceBundle.is_deleted.is_(False),
        )
    )
    if record is None:
        record = PublishedSurfaceEvidenceBundle(
            tenant_id=tenant_id,
            project_id=project_id,
            surface_id=surface_id,
            bundle_id=bundle_id,
            resource_type=str(evidence_bundle.get("resource_type") or "unknown"),
            status="recorded",
            export_status="not_exported",
            evidence_bundle_json=evidence_bundle,
            redacted_payload_summary_json={},
        )
        session.add(record)
        session.flush()
        return
    record.evidence_bundle_json = evidence_bundle
    record.status = "recorded"


def _mark_evidence_bundle_exported(
    *,
    session: Any,
    surface_id: int,
    evidence_bundle: dict[str, Any],
    redacted_payload_summary: dict[str, Any],
    request_id: str | None,
) -> None:
    bundle_id = str(evidence_bundle.get("bundle_id") or "")
    if not bundle_id:
        return
    record = session.scalar(
        select(PublishedSurfaceEvidenceBundle).where(
            PublishedSurfaceEvidenceBundle.surface_id == surface_id,
            PublishedSurfaceEvidenceBundle.bundle_id == bundle_id,
            PublishedSurfaceEvidenceBundle.is_deleted.is_(False),
        )
    )
    if record is None:
        tenant_id = int(evidence_bundle.get("audit_scope", {}).get("tenant_id") or 1)
        project_id = int(evidence_bundle.get("audit_scope", {}).get("project_id") or 1)
        record = PublishedSurfaceEvidenceBundle(
            tenant_id=tenant_id,
            project_id=project_id,
            surface_id=surface_id,
            bundle_id=bundle_id,
            resource_type=str(evidence_bundle.get("resource_type") or "unknown"),
            status="recorded",
            export_status="not_exported",
            evidence_bundle_json=evidence_bundle,
            redacted_payload_summary_json={},
        )
        session.add(record)
        session.flush()
    record.export_status = "exported"
    record.last_exported_at = datetime.now(UTC)
    record.last_export_request_id = request_id
    record.redacted_payload_summary_json = redacted_payload_summary


def _mark_evidence_bundle_archived(
    *,
    session: Any,
    surface_id: int,
    evidence_bundle: dict[str, Any],
    retention: dict[str, Any],
    archive_reason: str,
    archived_at: datetime,
    retain_until: datetime,
    request_id: str | None,
) -> None:
    bundle_id = str(evidence_bundle.get("bundle_id") or "")
    if not bundle_id:
        return
    record = session.scalar(
        select(PublishedSurfaceEvidenceBundle).where(
            PublishedSurfaceEvidenceBundle.surface_id == surface_id,
            PublishedSurfaceEvidenceBundle.bundle_id == bundle_id,
            PublishedSurfaceEvidenceBundle.is_deleted.is_(False),
        )
    )
    if record is None:
        tenant_id = int(evidence_bundle.get("audit_scope", {}).get("tenant_id") or 1)
        project_id = int(evidence_bundle.get("audit_scope", {}).get("project_id") or 1)
        record = PublishedSurfaceEvidenceBundle(
            tenant_id=tenant_id,
            project_id=project_id,
            surface_id=surface_id,
            bundle_id=bundle_id,
            resource_type=str(evidence_bundle.get("resource_type") or "unknown"),
            status="recorded",
            export_status="not_exported",
            evidence_bundle_json=evidence_bundle,
            redacted_payload_summary_json={},
        )
        session.add(record)
        session.flush()
    record.status = "archived"
    record.retention_policy_id = str(retention.get("policy_id") or "")
    record.retain_until = retain_until
    record.archived_at = archived_at
    record.archive_reason = archive_reason
    record.archive_request_id = request_id


def _recorded_evidence_bundle_ids(surface_id: int) -> set[str]:
    if _STATE_DATABASE_URL is None:
        return set()
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        records = session.scalars(
            select(AuditLog).where(
                AuditLog.action == "published_surface.evidence_bundle.record",
                AuditLog.resource_type == "published_surface_evidence_bundle",
                AuditLog.resource_id == surface_id,
            )
        )
        bundle_ids: set[str] = set()
        for record in records:
            evidence_bundle = _record(record.metadata_json.get("evidence_bundle"))
            bundle_id = evidence_bundle.get("bundle_id")
            if isinstance(bundle_id, str):
                bundle_ids.add(bundle_id)
        return bundle_ids


def _evidence_bundle_lifecycle_index(surface_id: int) -> dict[str, dict[str, Any]]:
    if _STATE_DATABASE_URL is None:
        return {}
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        records = session.scalars(
            select(PublishedSurfaceEvidenceBundle).where(
                PublishedSurfaceEvidenceBundle.surface_id == surface_id,
                PublishedSurfaceEvidenceBundle.is_deleted.is_(False),
            )
        )
        return {
            record.bundle_id: {
                "status": record.status,
                "export_status": record.export_status,
                "retention_policy_id": record.retention_policy_id,
                "retain_until": _datetime_iso(record.retain_until),
                "archived_at": _datetime_iso(record.archived_at),
            }
            for record in records
        }


def _default_evidence_bundle_lifecycle() -> dict[str, Any]:
    return {
        "status": "recorded",
        "export_status": "not_exported",
        "retention_policy_id": None,
        "retain_until": None,
        "archived_at": None,
    }


def _datetime_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _evidence_bundle_identity(evidence_bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": evidence_bundle.get("bundle_id"),
        "resource_type": evidence_bundle.get("resource_type"),
        "surface_id": evidence_bundle.get("surface_id"),
        "request_log_id": evidence_bundle.get("request_log_id"),
        "rollout_id": evidence_bundle.get("rollout_id"),
        "trace_id": evidence_bundle.get("trace_id"),
    }


def _evidence_bundle_export_url(surface_id: int, bundle_id: str) -> str:
    return f"/v1/console/published-surfaces/{surface_id}/evidence-bundles/{bundle_id}"


def _evidence_bundle_audit_index(
    bundle_id: str, recorded_bundle_ids: set[str]
) -> dict[str, Any]:
    return {
        "action": "published_surface.evidence_bundle.record",
        "resource_type": "published_surface_evidence_bundle",
        "recorded": bundle_id in recorded_bundle_ids,
    }


def _rollout_version_exists(surface_id: int, version: int) -> bool:
    return any(item.get("id") == version for item in _surface_rollout_history(surface_id))


def _rollout_surface_snapshot(surface_id: int, version: int) -> dict[str, Any] | None:
    for item in _surface_rollout_history(surface_id):
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
        "tenant_id": surface.get("tenant_id"),
        "project_id": surface.get("project_id"),
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


def _traffic_control_decision(traffic_control: dict[str, Any]) -> dict[str, Any]:
    traffic_split = _record(traffic_control.get("traffic_split")) or {
        "stable": 100,
        "candidate": 0,
    }
    candidate = _non_negative_int(traffic_split.get("candidate")) or 0
    return {
        "selected_branch": "candidate" if candidate == 100 else "stable",
        "traffic_split": traffic_split,
        "shadow_mirror": traffic_control.get("shadow_mode") is True,
        "shadow_route_id": traffic_control.get("shadow_route_id"),
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


def _policy_effects(policy_decision: dict[str, Any]) -> dict[str, Any]:
    effects: dict[str, Any] = {}
    limits = _record(policy_decision.get("limits"))
    redactions = _string_list(policy_decision.get("redactions"))
    if limits:
        effects["limits"] = limits
    if redactions:
        effects["redactions"] = redactions
    return effects


def _policy_rule_metadata(policy: Policy) -> dict[str, Any]:
    metadata = _record(policy.metadata_json)
    rule_metadata: dict[str, Any] = {}
    limits = _record(metadata.get("limits"))
    redactions = _string_list(metadata.get("redactions"))
    if limits:
        rule_metadata["limits"] = limits
    if redactions:
        rule_metadata["redactions"] = redactions
    return rule_metadata


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [item for item in (str(item).strip() for item in value) if item]


def _evaluate_surface_policy(
    surface: dict[str, Any],
    *,
    action: str,
    resource_id: int,
    route_id: int,
    request_metadata: dict[str, Any],
) -> dict[str, Any]:
    if _STATE_DATABASE_URL is None:
        return {"result": "allow", "policy_id": "published-surface-default"}
    tenant_id = int(surface.get("tenant_id") or 1)
    project_id = int(surface.get("project_id") or 1)
    environment = str(surface.get("environment") or "local")
    rules = _active_policy_rules(
        tenant_id=tenant_id,
        project_id=project_id,
        resource_type="published_surface",
        action=action,
    )
    decision = PolicyEngine(rules=rules).evaluate(
        PolicyRequest(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=None,
            actor_type="external_ingress",
            resource_type="published_surface",
            resource_id=resource_id,
            action=action,
            deployment_id=int(surface["deployment_id"]),
            environment=environment,
            runtime_context={
                "route_id": route_id,
                "route_path": surface.get("route_path"),
            },
            request_metadata=request_metadata,
        )
    )
    policy_id = decision.matched_policy_ids[0] if decision.matched_policy_ids else None
    limits = decision.limits or _record(decision.metadata.get("limits"))
    redactions = decision.redactions or tuple(_string_list(decision.metadata.get("redactions")))
    return {
        "result": decision.decision.value,
        "policy_id": policy_id or "published-surface-default",
        **(
            {"policy_ids": list(decision.matched_policy_ids)}
            if len(decision.matched_policy_ids) > 1
            else {}
        ),
        **({"limits": limits} if limits else {}),
        **({"redactions": list(redactions)} if redactions else {}),
        **({"approval_required": True} if decision.approval_required else {}),
        **({"reason": decision.reason} if decision.reason else {}),
    }


def _active_policy_rules(
    *,
    tenant_id: int,
    project_id: int,
    resource_type: str,
    action: str,
) -> list[StaticPolicyRule]:
    assert _STATE_DATABASE_URL is not None
    session_factory = create_session_factory(_STATE_DATABASE_URL)
    with session_factory() as session:
        policies = session.scalars(
            select(Policy)
            .where(
                Policy.is_deleted.is_(False),
                Policy.status == "active",
                Policy.tenant_id == tenant_id,
                Policy.resource_type == resource_type,
                Policy.action == action,
            )
            .order_by(Policy.priority.asc(), Policy.id.asc())
        ).all()
        rules: list[StaticPolicyRule] = []
        for policy in policies:
            if policy.project_id not in {None, project_id}:
                continue
            condition = _record(policy.condition_json)
            decision = _policy_decision_value(str(policy.decision))
            if decision is None:
                continue
            rules.append(
                StaticPolicyRule(
                    policy_id=str(policy.id),
                    resource_type=policy.resource_type,
                    action=policy.action,
                    decision=decision,
                    reason=policy.reason or "policy_matched",
                    tenant_id=policy.tenant_id,
                    project_id=policy.project_id,
                    environment=(
                        str(condition["environment"])
                        if condition.get("environment") is not None
                        else None
                    ),
                    risk_level=policy.risk_level,
                    resource_id=(
                        int(condition["resource_id"])
                        if isinstance(condition.get("resource_id"), int)
                        else None
                    ),
                    metadata=_policy_rule_metadata(policy),
                )
            )
        return rules


def _policy_decision_value(value: str) -> Decision | None:
    try:
        return Decision(value)
    except ValueError:
        return None
