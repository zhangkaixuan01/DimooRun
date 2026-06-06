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


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _is_secret_ref(value: object) -> bool:
    return isinstance(value, str) and (value.startswith("secret:") or value.startswith("vault://"))


@router.post("/v1/model-gateways/test")
def test_model_gateway(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    credential_ref = data.get("credential_ref")
    credential_valid = _is_secret_ref(credential_ref)
    credential_validation = {
        "valid": credential_valid,
        "credential_ref": credential_ref,
        "scope": "project",
    }
    if not credential_valid:
        credential_validation["disabled_action_reason"] = "credential_ref_must_use_secret_ref"
    return {
        "credential_validation": credential_validation,
        "safe_health_probe": {
            "status": "ok" if credential_valid else "blocked",
            "provider": data.get("provider_type") or "unknown",
            "base_url": data.get("base_url"),
            "secret_exposed": False,
            "checked_at": _now(),
        },
        "budget_preview": {
            "model_group": data.get("model_group") or data.get("default_model_group") or "default",
            "monthly_budget_usd": float(data.get("monthly_budget_usd") or 0),
            "estimated_request_cost_usd": 0.002,
            "disabled_action_reason": None,
        },
        "fallback_preview": {
            "target": data.get("fallback_gateway_ref"),
            "enabled": bool(data.get("fallback_gateway_ref")),
            "order": [data.get("name") or "candidate", data.get("fallback_gateway_ref")],
        },
        "provider_error_normalization": {
            "raw_status": 503,
            "raw_code": "upstream_unavailable",
            "normalized_code": "provider_unavailable",
            "retryable": True,
        },
        "audit_preview": {
            "action": "model_gateway.test",
            "resource_type": "model_gateway",
            "resource_id": data.get("name"),
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
    }
