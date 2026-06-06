import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.deployments import reset_deployment_control
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = (
        f"sqlite:///{tempfile.gettempdir()}/dimoorun-package-workflow-{uuid4().hex}.db"
    )
    reset_api_key_authenticator()
    reset_deployment_control()
    reset_native_runtime()


def create_api_key(*, scopes: set[str] | None = None) -> tuple[str, ServiceAccountRecord]:
    requested_scopes = scopes or {"agent:read", "agent:write", "agent:deploy", "agent:invoke"}
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="package-workflow",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="package-workflow-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=requested_scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": "req_package_workflow",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "production",
    }


def create_agent(client: TestClient, key: str) -> int:
    response = client.post(
        "/v1/agents",
        headers=auth_headers(key),
        json={"name": "package-agent"},
    )
    assert response.status_code == 201
    agent_id = response.json()["id"]
    assert isinstance(agent_id, int)
    return agent_id


def valid_manifest() -> dict[str, object]:
    return {
        "name": "support-agent",
        "runtime": {
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
        },
        "secrets": [{"name": "OPENAI_API_KEY", "ref": "vault://openai"}],
        "capabilities": {"invoke": True, "stream": True},
    }


def test_package_validation_endpoint_reports_readiness_and_next_action() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/packages/validate" in paths

    response = client.post(
        "/v1/packages/validate",
        headers=auth_headers(key),
        json={
            "package_uri": "oci://registry.local/support-agent:1.0.0",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": valid_manifest(),
            "required_secret_refs": ["vault://openai"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["ready"] is True
    assert body["validation_token"].startswith("pkgval_")
    assert body["capabilities"] == {"invoke": True, "stream": True}
    assert body["missing_secret_refs"] == []
    assert body["warnings"] == []
    assert body["next_action"] == "create_ready_agent_version"


def test_package_validation_reports_dependency_warnings_without_blocking_readiness() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    manifest = {
        **valid_manifest(),
        "dependencies": [
            {"name": "langgraph", "version": "1.2.1"},
            {"name": "custom-toolkit"},
            "unstructured-extra",
        ],
    }

    response = client.post(
        "/v1/packages/validate",
        headers=auth_headers(key),
        json={
            "package_uri": "oci://registry.local/support-agent:1.0.0",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": manifest,
            "required_secret_refs": ["vault://openai"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["ready"] is True
    assert body["warnings"] == [
        "Dependency custom-toolkit does not declare a version.",
        "Dependency entry must be an object with name and version: unstructured-extra",
    ]
    assert body["next_action"] == "create_ready_agent_version"


def test_package_validation_explains_invalid_manifest_secret_and_runtime_errors() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()

    response = client.post(
        "/v1/packages/validate",
        headers=auth_headers(key),
        json={
            "package_uri": "file://../unsafe-agent",
            "framework": "langgraph",
            "adapter": "deepagents",
            "entrypoint": "agent:create_agent",
            "manifest": {
                "runtime": {"entrypoint": "agent:create_other"},
                "capabilities": {"unsupported_magic": True},
            },
            "required_secret_refs": ["vault://openai"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert body["ready"] is False
    assert body["validation_token"] is None
    assert body["missing_secret_refs"] == ["vault://openai"]
    assert {item["code"] for item in body["errors"]} == {
        "package_uri_not_allowed",
        "unsupported_runtime_pair",
        "manifest_runtime_mismatch",
        "required_secret_missing",
        "unsupported_capability",
    }
    assert body["next_action"] == "fix_validation_errors"


def test_agent_version_ready_status_requires_validation_token() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id = create_agent(client, key)

    blocked_create = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "1.0.0",
            "package_uri": "oci://registry.local/support-agent:1.0.0",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "status": "ready",
            "manifest": valid_manifest(),
        },
    )
    assert blocked_create.status_code == 409
    assert blocked_create.json()["error_code"] == "package_validation_required"

    validation = client.post(
        "/v1/packages/validate",
        headers=auth_headers(key),
        json={
            "package_uri": "oci://registry.local/support-agent:1.0.0",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": valid_manifest(),
            "required_secret_refs": ["vault://openai"],
        },
    )
    token = validation.json()["validation_token"]

    ready = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "1.0.0",
            "package_uri": "oci://registry.local/support-agent:1.0.0",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "status": "ready",
            "manifest": {**valid_manifest(), "validation_token": token},
        },
    )
    assert ready.status_code == 201
    assert ready.json()["status"] == "ready"

    draft = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "1.1.0",
            "package_uri": "oci://registry.local/support-agent:1.1.0",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "status": "draft",
            "manifest": valid_manifest(),
        },
    )
    assert draft.status_code == 201

    blocked_update = client.patch(
        f"/v1/agents/{agent_id}/versions/1.1.0",
        headers=auth_headers(key),
        json={"status": "ready"},
    )
    assert blocked_update.status_code == 409
    assert blocked_update.json()["error_code"] == "package_validation_required"
