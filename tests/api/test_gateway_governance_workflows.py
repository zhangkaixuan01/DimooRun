import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import reset_api_key_authenticator
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DIMOORUN_DEV_API_KEY"] = "dev-local-key"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-gateway-governance-{uuid4().hex}.db"
    reset_api_key_authenticator()


def admin_headers(request_id: str = "req_gateway_governance") -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
        "X-Request-Id": request_id,
    }


def test_model_gateway_test_returns_validation_health_budget_fallback_and_normalized_error(
) -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/model-gateways/test",
        headers=admin_headers("req_gateway_test"),
        json={
            "name": "primary-openai",
            "provider_type": "openai",
            "base_url": "https://api.openai.example/v1",
            "credential_ref": "secret:model-openai",
            "model_group": "support-tier",
            "monthly_budget_usd": 500,
            "fallback_gateway_ref": "gateway:backup-openai",
            "probe_prompt": "health",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["credential_validation"] == {
        "valid": True,
        "credential_ref": "secret:model-openai",
        "scope": "project",
    }
    assert body["safe_health_probe"]["status"] == "ok"
    assert body["safe_health_probe"]["secret_exposed"] is False
    assert body["budget_preview"]["monthly_budget_usd"] == 500
    assert body["fallback_preview"]["target"] == "gateway:backup-openai"
    assert body["provider_error_normalization"]["normalized_code"] == "provider_unavailable"
    assert body["audit_preview"]["action"] == "model_gateway.test"


def test_model_gateway_test_blocks_plaintext_credentials() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/model-gateways/test",
        headers=admin_headers("req_gateway_plaintext"),
        json={
            "name": "unsafe-openai",
            "provider_type": "openai",
            "base_url": "https://api.openai.example/v1",
            "credential_ref": "sk-plaintext",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["credential_validation"]["valid"] is False
    assert (
        body["credential_validation"]["disabled_action_reason"]
        == "credential_ref_must_use_secret_ref"
    )
    assert body["safe_health_probe"]["status"] == "blocked"


def test_tool_dry_run_returns_schema_risk_policy_approval_and_usage_history() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/tools/dry-run",
        headers=admin_headers("req_tool_dry_run"),
        json={
            "name": "crm.update_ticket",
            "schema": {
                "type": "object",
                "required": ["ticket_id", "status"],
                "properties": {
                    "ticket_id": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
            "arguments": {"ticket_id": "T-100", "status": "closed"},
            "risk_level": "write",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_validation"]["valid"] is True
    assert body["risk_classification"] == {"level": "write", "requires_approval": True}
    assert body["policy_preview"]["decision"] == "require_approval"
    assert body["approval_requirement"]["required"] is True
    assert body["usage_history_link"] == "/v1/tools/crm.update_ticket/usage"
    assert body["audit_preview"]["action"] == "tool.dry_run"


def test_secret_validation_and_rotation_return_metadata_without_secret_value() -> None:
    client = TestClient(create_app())

    validated = client.post(
        "/v1/secrets/validate",
        headers=admin_headers("req_secret_validate"),
        json={
            "name": "model-openai",
            "provider": "external",
            "ref": "vault://project/model-openai",
            "access_context": {"used_by": "gateway:primary-openai"},
        },
    )
    rotated = client.post(
        "/v1/secrets/rotate",
        headers=admin_headers("req_secret_rotate"),
        json={
            "name": "model-openai",
            "provider": "external",
            "ref": "vault://project/model-openai-next",
            "rotation_reason": "scheduled rotation",
        },
    )

    assert validated.status_code == 200
    assert rotated.status_code == 200
    validation_body = validated.json()
    rotation_body = rotated.json()
    assert validation_body["validation"]["valid"] is True
    assert validation_body["secret_value"] is None
    assert validation_body["last_used"]["used_by"] == "gateway:primary-openai"
    assert validation_body["access_audit"]["action"] == "secret.validate"
    assert rotation_body["rotation"]["status"] == "rotated"
    assert rotation_body["rotation"]["previous_ref"] == "vault://project/model-openai"
    assert rotation_body["rotation"]["current_ref"] == "vault://project/model-openai-next"
    assert "secret_value" not in rotation_body


def test_secret_rotation_blocks_invalid_ref_without_replacing_current_ref() -> None:
    client = TestClient(create_app())

    validated = client.post(
        "/v1/secrets/validate",
        headers=admin_headers("req_secret_validate_before_blocked_rotate"),
        json={
            "name": "model-openai",
            "provider": "external",
            "ref": "vault://project/model-openai",
        },
    )
    blocked = client.post(
        "/v1/secrets/rotate",
        headers=admin_headers("req_secret_rotate_invalid_ref"),
        json={
            "name": "model-openai",
            "provider": "external",
            "ref": "plaintext:model-openai-next",
            "rotation_reason": "operator pasted a raw value",
        },
    )

    assert validated.status_code == 200
    assert blocked.status_code == 200
    body = blocked.json()
    assert body["rotation"]["status"] == "blocked"
    assert body["rotation"]["previous_ref"] == "vault://project/model-openai"
    assert body["rotation"]["current_ref"] == "vault://project/model-openai"
    assert body["rotation"]["rejected_ref"] == "plaintext:model-openai-next"
    assert body["rotation"]["disabled_action_reason"] == "secret_ref_must_use_external_uri"
    assert "secret_value" not in body
