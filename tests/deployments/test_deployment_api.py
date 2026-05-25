from dimoo_run.api.native.deployments import default_deployment_control, reset_deployment_control
from dimoo_run.deployments.service import DeploymentRecord
from dimoo_run.domain.enums import DeploymentDesiredStatus
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    reset_deployment_control()


def test_deployment_control_api_updates_status_and_lists_instances() -> None:
    service = default_deployment_control()
    service.deployments.add(
        DeploymentRecord(
            id="deployment_1",
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="version_1",
            environment="dev",
            desired_status=DeploymentDesiredStatus.draft,
        )
    )
    instance = service.instances.register_loading(
        tenant_id="tenant_1",
        project_id="project_1",
        deployment_id="deployment_1",
        agent_id="agent_1",
        agent_version_id="version_1",
        worker_id="worker_1",
        execution_profile_id=None,
    )
    service.instances.mark_ready(instance.id)
    client = TestClient(create_app())

    response = client.post(
        "/v1/deployments/deployment_1/activate",
        headers={
            "X-Actor-Id": "user_1",
            "X-Request-Id": "req_1",
            "X-Tenant-Id": "tenant_1",
            "X-Project-Id": "project_1",
        },
    )
    instances_response = client.get(
        "/v1/deployments/deployment_1/instances",
        headers={"X-Tenant-Id": "tenant_1", "X-Project-Id": "project_1"},
    )

    assert response.status_code == 200
    assert response.json()["desired_status"] == "active"
    assert instances_response.status_code == 200
    assert instances_response.json()[0]["worker_id"] == "worker_1"


def test_deployment_control_api_returns_stable_error_response() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/deployments/missing/activate",
        headers={
            "X-Request-Id": "req_missing",
            "X-Tenant-Id": "tenant_1",
            "X-Project-Id": "project_1",
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
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
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
    client = TestClient(create_app())

    missing_scope = client.get("/v1/deployments", headers={"X-Request-Id": "req_scope"})
    scoped = client.get(
        "/v1/deployments",
        headers={"X-Tenant-Id": "tenant_1", "X-Project-Id": "project_1"},
    )
    cross_scope = client.get(
        "/v1/deployments/deployment_2",
        headers={"X-Tenant-Id": "tenant_1", "X-Project-Id": "project_1"},
    )

    assert missing_scope.status_code == 400
    assert missing_scope.json()["error_code"] == "request_scope_required"
    assert [deployment["id"] for deployment in scoped.json()] == ["deployment_1"]
    assert cross_scope.status_code == 404
    assert cross_scope.json()["error_code"] == "deployment_not_found"
