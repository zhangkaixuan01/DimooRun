from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.deployments import default_deployment_control, reset_deployment_control
from dimoo_run.deployments.service import DeploymentRecord
from dimoo_run.domain.enums import DeploymentDesiredStatus
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    reset_api_key_authenticator()
    reset_deployment_control()


def create_api_key(*, scopes: set[str]) -> tuple[str, ServiceAccountRecord]:
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="runtime",
        permissions=scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="runtime-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def test_deployment_control_api_updates_status_and_lists_instances() -> None:
    service = default_deployment_control()
    service.deployments.add(
        DeploymentRecord(
            id="deployment_1",
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id="version_1",
            environment="dev",
            desired_status=DeploymentDesiredStatus.draft,
        )
    )
    instance = service.instances.register_loading(
        tenant_id=1,
        project_id=1,
        deployment_id=1,
        agent_id=1,
        agent_version_id="version_1",
        worker_id="worker_1",
        execution_profile_id=None,
    )
    service.instances.mark_ready(instance.id)
    plain_key, service_account = create_api_key(scopes={"agent:read", "agent:deploy"})
    client = TestClient(create_app())

    response = client.post(
        "/v1/deployments/deployment_1/activate",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Request-Id": "req_1",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
    )
    instances_response = client.get(
        "/v1/deployments/deployment_1/instances",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
    )

    assert response.status_code == 200
    assert response.json()["desired_status"] == "active"
    assert instances_response.status_code == 200
    assert instances_response.json()[0]["worker_id"] == "worker_1"
    assert service.audit_sink.entries[0].actor_id == service_account.id


def test_deployment_api_creates_deployment_with_deploy_scope() -> None:
    plain_key, service_account = create_api_key(
        scopes={"agent:read", "agent:write", "agent:deploy"}
    )
    client = TestClient(create_app())
    agent = client.post(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
        json={"name": "support-agent"},
    ).json()
    version = client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
        json={"version": "0.1.0"},
    ).json()

    response = client.post(
        "/v1/deployments",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Request-Id": "req_create",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
        json={
            "agent_id": agent["id"],
            "agent_version_id": version["id"],
            "environment": "dev",
            "replicas": 2,
        },
    )
    duplicate = client.post(
        "/v1/deployments",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Request-Id": "req_duplicate",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
        json={
            "agent_id": agent["id"],
            "agent_version_id": version["id"],
            "environment": "dev",
        },
    )

    assert response.status_code == 201
    assert response.json()["agent_id"] == agent["id"]
    assert response.json()["runtime_status"] == "not_loaded"
    assert default_deployment_control().audit_sink.entries[0].actor_id == service_account.id
    assert duplicate.status_code == 409
    assert duplicate.json()["error_code"] == "deployment_already_exists"


def test_deployment_api_rejects_missing_agent_version_binding() -> None:
    plain_key, _ = create_api_key(scopes={"agent:read", "agent:write", "agent:deploy"})
    client = TestClient(create_app())
    agent = client.post(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
        json={"name": "support-agent"},
    ).json()

    response = client.post(
        "/v1/deployments",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
        json={
            "agent_id": agent["id"],
            "agent_version_id": "missing_version",
            "environment": "dev",
        },
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "agent_version_not_found"


def test_deployment_control_api_returns_stable_error_response() -> None:
    plain_key, _ = create_api_key(scopes={"agent:deploy"})
    client = TestClient(create_app())

    response = client.post(
        "/v1/deployments/missing/activate",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Request-Id": "req_missing",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "deployment_not_found",
        "message": "Deployment was not found.",
        "request_id": "req_missing",
        "details": {"deployment_id": "missing"},
    }


def test_deployment_api_requires_request_scope_and_filters_by_scope() -> None:
    service = default_deployment_control()
    service.deployments.add(
        DeploymentRecord(
            id="deployment_1",
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id="version_1",
            environment="dev",
        )
    )
    service.deployments.add(
        DeploymentRecord(
            id="deployment_2",
            tenant_id="tenant_2",
            project_id="project_2",
            agent_id="agent_2",
            agent_version_id="version_2",
            environment="dev",
        )
    )
    plain_key, _ = create_api_key(scopes={"agent:read"})
    client = TestClient(create_app())

    missing_scope = client.get("/v1/deployments", headers={"X-Request-Id": "req_scope"})
    scoped = client.get(
        "/v1/deployments",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
    )
    cross_scope = client.get(
        "/v1/deployments/deployment_2",
        headers={
            "Authorization": f"Bearer {plain_key}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
    )

    assert missing_scope.status_code == 400
    assert missing_scope.json()["error_code"] == "request_scope_required"
    assert [deployment["id"] for deployment in scoped.json()] == ["deployment_1"]
    assert cross_scope.status_code == 404
    assert cross_scope.json()["error_code"] == "deployment_not_found"


def test_deployment_control_api_requires_api_key_with_deploy_scope() -> None:
    service = default_deployment_control()
    service.deployments.add(
        DeploymentRecord(
            id="deployment_1",
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id="version_1",
            environment="dev",
        )
    )
    read_only_key, _ = create_api_key(scopes={"agent:read"})
    client = TestClient(create_app())

    missing_auth = client.post(
        "/v1/deployments/deployment_1/activate",
        headers={"X-Tenant-Id": "1", "X-Project-Id": "1"},
    )
    insufficient_scope = client.post(
        "/v1/deployments/deployment_1/activate",
        headers={
            "Authorization": f"Bearer {read_only_key}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
    )

    assert missing_auth.status_code == 401
    assert missing_auth.json()["error_code"] == "api_key_invalid"
    assert insufficient_scope.status_code == 403
    assert insufficient_scope.json()["error_code"] == "api_key_scope_denied"
