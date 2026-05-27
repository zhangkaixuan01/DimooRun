import os
from uuid import uuid4

from dimoo_run.server import create_app
from fastapi.testclient import TestClient

ADMIN_PATHS = [
    "/v1/policies",
    "/v1/artifacts/{artifact_id}",
    "/v1/human-tasks",
    "/v1/human-tasks/{task_id}/approve",
    "/v1/human-tasks/{task_id}/reject",
    "/v1/model-gateways",
    "/v1/published-surfaces",
    "/v1/ingress-routes",
    "/v1/catalog/items",
    "/v1/datasets",
    "/v1/experiments",
    "/v1/service-accounts",
    "/v1/api-keys",
    "/v1/schedules",
    "/v1/batch-runs",
    "/v1/notifications/channels",
    "/v1/alerts/rules",
    "/v1/backups/plans",
    "/v1/backups/restore-jobs",
    "/v1/webhooks/subscriptions",
    "/v1/incidents",
    "/v1/incidents/{incident_id}/acknowledge",
    "/v1/incidents/{incident_id}/resolve",
    "/v1/identity/tenants",
    "/v1/identity/projects",
    "/v1/identity/environments",
    "/v1/identity/users",
    "/v1/identity/operators",
    "/v1/identity/roles",
    "/v1/identity/permissions",
    "/v1/secrets",
    "/v1/tools",
    "/v1/assets/prompts",
    "/v1/assets/configs",
    "/v1/assets/templates",
    "/v1/audit-logs",
    "/v1/evaluations/results",
    "/v1/feedback",
    "/v1/semantic-store/providers",
    "/v1/observability/exporters",
    "/v1/sandbox/policies",
    "/v1/container-pool/policies",
]


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DIMOORUN_DEV_API_KEY"] = "dev-local-key"


def admin_headers(request_id: str = "req_admin") -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Tenant-Id": "tenant_1",
        "X-Project-Id": "project_1",
        "X-Environment": "local",
        "X-Request-Id": request_id,
    }


def test_admin_api_paths_are_registered_in_openapi() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in ADMIN_PATHS:
        assert path in paths


def test_high_risk_admin_action_marks_audit_required() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/human-tasks/task_1/approve",
        headers=admin_headers("req_approve"),
        json={"decision_payload": {"approved": True}},
    )

    assert response.status_code == 200
    assert response.json()["audit_required"] is True
    assert response.json()["item"]["status"] == "approved"


def test_admin_collection_api_supports_minimal_create_and_list() -> None:
    client = TestClient(create_app())

    created = client.post(
        "/v1/policies",
        headers=admin_headers("req_admin_write"),
        json={"name": "allow-read", "metadata": {"scope": "project"}},
    )
    listed = client.get("/v1/policies", headers=admin_headers("req_admin_read"))

    assert created.status_code == 201
    assert created.json()["item"]["name"] == "allow-read"
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1
    assert any(item["name"] == "allow-read" for item in listed.json()["items"])

    resource_id = created.json()["item"]["id"]
    updated = client.patch(
        f"/v1/policies/{resource_id}",
        headers=admin_headers("req_admin_update"),
        json={"name": "allow-read-updated", "status": "disabled"},
    )
    deleted = client.delete(
        f"/v1/policies/{resource_id}",
        headers=admin_headers("req_admin_delete"),
    )

    assert updated.status_code == 200
    assert updated.json()["item"]["name"] == "allow-read-updated"
    assert updated.json()["item"]["status"] == "disabled"
    assert deleted.status_code == 200
    assert deleted.json()["item"]["status"] == "deleted"


def test_scope_management_collections_are_seeded() -> None:
    client = TestClient(create_app())

    tenants = client.get("/v1/identity/tenants", headers=admin_headers("req_tenants"))
    projects = client.get("/v1/identity/projects", headers=admin_headers("req_projects"))
    environments = client.get(
        "/v1/identity/environments",
        headers=admin_headers("req_environments"),
    )

    assert tenants.status_code == 200
    assert projects.status_code == 200
    assert environments.status_code == 200
    assert any(item["id"] == "tenant_1" for item in tenants.json()["items"])
    assert any(item["id"] == "project_1" for item in projects.json()["items"])
    assert any(item["id"] == "local" for item in environments.json()["items"])


def test_console_admin_surface_collections_support_create_and_list() -> None:
    client = TestClient(create_app())
    name = f"console-created-{uuid4().hex[:8]}"
    paths = [
        "/v1/identity/users",
        "/v1/identity/tenants",
        "/v1/identity/projects",
        "/v1/identity/environments",
        "/v1/identity/roles",
        "/v1/service-accounts",
        "/v1/api-keys",
        "/v1/secrets",
        "/v1/model-gateways",
        "/v1/webhooks/subscriptions",
        "/v1/backups/restore-jobs",
        "/v1/incidents",
    ]

    for path in paths:
        created = client.post(path, headers=admin_headers(), json={"name": name})
        listed = client.get(path, headers=admin_headers())

        assert created.status_code == 201, path
        assert listed.status_code == 200, path
        assert any(item["name"] == name for item in listed.json()["items"]), path


def test_machine_identity_service_account_api_key_lifecycle() -> None:
    client = TestClient(create_app())

    service_account = client.post(
        "/v1/identity/service-accounts",
        headers=admin_headers("req_sa_create"),
        json={
            "name": "ci-deployer",
            "description": "CI deployment identity",
            "tenant_id": "tenant_1",
            "project_id": "project_1",
            "permissions": ["agent:read", "agent:deploy"],
        },
    )
    assert service_account.status_code == 201
    service_account_id = service_account.json()["item"]["id"]

    denied_key = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_key_denied"),
        json={"name": "too-powerful", "scopes": ["agent:read", "secret:read"]},
    )
    assert denied_key.status_code == 403
    assert denied_key.json()["error_code"] == "api_key_scope_exceeds_owner"

    created_key = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_key_create"),
        json={"name": "deploy-key", "scopes": ["agent:read"]},
    )
    assert created_key.status_code == 201
    payload = created_key.json()
    assert payload["plain_key"].startswith("dr_")
    key_id = payload["item"]["id"]

    listed_keys = client.get(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_key_list"),
    )
    assert listed_keys.status_code == 200
    assert "plain_key" not in listed_keys.json()["items"][0]
    assert listed_keys.json()["items"][0]["scopes"] == ["agent:read"]

    allowed = client.get(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {payload['plain_key']}",
            "X-Tenant-Id": "tenant_1",
            "X-Project-Id": "project_1",
            "X-Request-Id": "req_key_allowed",
        },
    )
    assert allowed.status_code == 200

    disabled = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys/{key_id}/disable",
        headers=admin_headers("req_key_disable"),
    )
    assert disabled.status_code == 200

    rejected = client.get(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {payload['plain_key']}",
            "X-Tenant-Id": "tenant_1",
            "X-Project-Id": "project_1",
            "X-Request-Id": "req_key_rejected",
        },
    )
    assert rejected.status_code == 401


def test_admin_artifact_read_returns_stable_not_found_response() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/v1/artifacts/artifact_missing",
        headers=admin_headers("req_artifact_read"),
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "resource_not_found"
    assert response.json()["request_id"] == "req_artifact_read"
