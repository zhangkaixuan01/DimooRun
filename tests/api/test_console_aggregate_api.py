import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.deployments import reset_deployment_control
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.packages.validation import validation_token
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


CONSOLE_PATHS = [
    "/v1/console/dashboard-summary",
    "/v1/console/runtime-overview",
    "/v1/console/deployment-health",
    "/v1/console/worker-health",
    "/v1/console/recent-failures",
    "/v1/console/pending-actions",
    "/v1/console/action-summary",
]


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = (
        f"sqlite:///{tempfile.gettempdir()}/dimoorun-console-aggregate-{uuid4().hex}.db"
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
        name="console-aggregate",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="console-aggregate-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=requested_scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers(
    api_key: str,
    *,
    tenant_id: int = 1,
    project_id: int = 1,
    environment: str = "production",
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": "req_console_aggregate",
        "X-Tenant-Id": str(tenant_id),
        "X-Project-Id": str(project_id),
        "X-Environment": environment,
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def create_agent_with_version(client: TestClient, key: str) -> tuple[int, int]:
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(key),
        json={"name": "support-agent"},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]
    version = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "0.1.0",
            "package_uri": "file://support-agent",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": {
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "agent:create_agent",
                },
                "capabilities": {"invoke": True},
                "validation_token": validation_token(
                    package_uri="file://support-agent",
                    framework="langgraph",
                    adapter="langgraph",
                    entrypoint="agent:create_agent",
                    manifest={
                        "runtime": {
                            "framework": "langgraph",
                            "adapter": "langgraph",
                            "entrypoint": "agent:create_agent",
                        },
                        "capabilities": {"invoke": True},
                    },
                ),
            },
            "status": "ready",
        },
    )
    assert version.status_code == 201
    return agent_id, version.json()["id"]


def create_deployment(
    client: TestClient,
    key: str,
    *,
    environment: str,
    desired_status: str = "active",
) -> int:
    agent_id, version_id = create_agent_with_version(client, key)
    response = client.post(
        "/v1/deployments",
        headers=auth_headers(key, environment=environment),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": environment,
            "desired_status": desired_status,
            "replicas": 2,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_console_aggregate_paths_are_registered_in_openapi() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in CONSOLE_PATHS:
        assert path in paths


def test_runtime_overview_is_scoped_and_redacts_failure_payloads() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    production_deployment_id = create_deployment(client, key, environment="production")
    create_deployment(client, key, environment="staging")

    task = client.post(
        f"/v1/deployments/{production_deployment_id}/tasks",
        headers=auth_headers(key, idempotency_key="console_overview_1"),
        json={"input": {"message": "hello", "secret": "do-not-leak"}},
    )
    assert task.status_code == 202

    from dimoo_run.api.native.runtime import default_native_runtime
    from dimoo_run.domain.enums import RunStatus, TaskStatus

    runtime = default_native_runtime()
    run = runtime.runs[task.json()["run_id"]]
    run.status = RunStatus.failed
    run.error = {"message": "provider timeout", "secret": "hidden"}
    worker_task = runtime.tasks[task.json()["task_id"]]
    worker_task.status = TaskStatus.dead_letter
    worker_task.dead_letter_reason = "provider timeout"

    overview = client.get(
        "/v1/console/runtime-overview",
        headers=auth_headers(key, environment="production"),
    )

    assert overview.status_code == 200
    body = overview.json()
    assert body["summary"]["run_count_today"] == 1
    assert body["summary"]["queue_backlog"] == 1
    assert body["deployment_health"] == [
        {
            "deployment_id": production_deployment_id,
            "environment": "production",
            "desired_status": "active",
            "runtime_status": "not_loaded",
            "replicas": 2,
            "queue_backlog": 1,
            "running_runs": 0,
            "last_runtime_error": None,
        }
    ]
    assert body["recent_failures"][0]["run_id"] == run.id
    assert body["recent_failures"][0]["error_summary"] == "provider timeout"
    assert "input" not in body["recent_failures"][0]
    assert "output" not in body["recent_failures"][0]
    assert "secret" not in str(body)


def test_action_summary_explains_disabled_actions_without_granting_authorization() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read"})
    deployment_id = create_deployment(
        client,
        create_api_key()[0],
        environment="production",
        desired_status="draft",
    )

    summary = client.get(
        "/v1/console/action-summary",
        headers=auth_headers(key, environment="production"),
        params={"resource_type": "deployment", "resource_id": deployment_id},
    )

    assert summary.status_code == 200
    actions = {item["action"]: item for item in summary.json()["actions"]}
    assert actions["deployment.activate"]["available"] is False
    assert actions["deployment.activate"]["disabled_reasons"][0:1] == [
        "Deployment must be stopped, paused, or active before activation."
    ]
    assert "Current actor lacks agent:deploy permission." in actions["deployment.activate"][
        "disabled_reasons"
    ]
    assert actions["deployment.activate"]["required_permissions"] == ["agent:deploy"]
    assert actions["deployment.activate"]["audit_required"] is True
    assert "Policy Engine enforces this action on submit." in actions["deployment.activate"][
        "policy_warnings"
    ]

    denied_write = client.post(
        f"/v1/deployments/{deployment_id}/activate",
        headers=auth_headers(key, environment="production"),
    )
    assert denied_write.status_code == 403
