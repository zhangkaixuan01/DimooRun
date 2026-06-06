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


def _validate_schema(schema: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    missing = [
        field
        for field in schema.get("required", [])
        if isinstance(field, str) and field not in arguments
    ]
    return {
        "valid": not missing and schema.get("type") == "object",
        "missing_fields": missing,
        "schema_type": schema.get("type"),
    }


@router.post("/v1/tools/dry-run")
def dry_run_tool(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> dict[str, Any]:
    data = payload or {}
    raw_schema = data.get("schema")
    raw_arguments = data.get("arguments")
    schema = raw_schema if isinstance(raw_schema, dict) else {}
    arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
    risk_level = str(data.get("risk_level") or "read")
    requires_approval = risk_level in {"write", "admin", "critical"}
    validation = _validate_schema(schema, arguments)
    decision = "require_approval" if requires_approval else "allow"
    return {
        "schema_validation": validation,
        "risk_classification": {
            "level": risk_level,
            "requires_approval": requires_approval,
        },
        "policy_preview": {
            "decision": decision,
            "matched_policy": "tool-risk-default",
            "reason": (
                "High-risk tool calls require approval."
                if requires_approval
                else "Read-only dry run."
            ),
        },
        "approval_requirement": {
            "required": requires_approval,
            "role": "platform-approver" if requires_approval else None,
        },
        "usage_history_link": f"/v1/tools/{data.get('name') or 'tool'}/usage",
        "dry_run_output": {
            "status": "blocked" if requires_approval else "succeeded",
            "side_effects": False,
        },
        "audit_preview": {
            "action": "tool.dry_run",
            "resource_type": "tool",
            "resource_id": data.get("name"),
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
            "created_at": _now(),
        },
    }
