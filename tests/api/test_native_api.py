from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.server import create_app
from fastapi.testclient import TestClient

NATIVE_PATHS = [
    "/v1/agents",
    "/v1/agents/{agent_id}",
    "/v1/agents/{agent_id}/versions",
    "/v1/agents/{agent_id}/versions/{version}",
    "/v1/agents/{agent_id}/invoke",
    "/v1/agents/{agent_id}/tasks",
    "/v1/agents/{agent_id}/stream",
    "/v1/runs/{run_id}",
    "/v1/runs/{run_id}/events",
    "/v1/runs/{run_id}/attempts",
    "/v1/runs/{run_id}/cancel",
    "/v1/runs/{run_id}/resume",
    "/v1/runs/{run_id}/retry",
    "/v1/runs/{run_id}/replay",
    "/v1/deployments",
    "/v1/deployments/{deployment_id}",
    "/v1/deployments/{deployment_id}/activate",
    "/v1/deployments/{deployment_id}/pause",
    "/v1/deployments/{deployment_id}/resume",
    "/v1/deployments/{deployment_id}/drain",
    "/v1/deployments/{deployment_id}/stop",
    "/v1/deployments/{deployment_id}/restart",
    "/v1/deployments/{deployment_id}/instances",
    "/v1/tasks/{task_id}",
    "/v1/tasks/{task_id}/cancel",
]


def setup_function() -> None:
    reset_api_key_authenticator()
    reset_native_runtime()


def create_api_key(*, scopes: set[str] | None = None) -> tuple[str, ServiceAccountRecord]:
    requested_scopes = scopes or {"agent:read", "agent:write", "agent:invoke"}
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id="tenant_1",
        project_id="project_1",
        name="native",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id="tenant_1",
        project_id="project_1",
        name="native-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=requested_scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers(
    api_key: str | None = None,
    *,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key or create_api_key()[0]}",
        "X-Request-Id": "req_native",
        "X-Tenant-Id": "tenant_1",
        "X-Project-Id": "project_1",
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def create_agent_with_version(client: TestClient, key: str) -> tuple[str, str]:
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
        json={"version": "0.1.0", "package_uri": "file://support-agent"},
    )
    assert version.status_code == 201
    return agent_id, version.json()["id"]


def test_native_api_paths_are_registered_in_openapi() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in NATIVE_PATHS:
        assert path in paths


def test_native_agent_task_run_event_flow_is_real() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, version_id = create_agent_with_version(client, key)

    task_response = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key, idempotency_key="idem_1"),
        json={"input": {"message": "hello"}},
    )

    assert task_response.status_code == 202
    task_body = task_response.json()
    assert task_body["run_id"].startswith("run_")
    assert task_body["task_id"].startswith("task_")
    assert task_body["status"] == "queued"

    run = client.get(
        f"/v1/runs/{task_body['run_id']}",
        headers=auth_headers(key),
    )
    assert run.status_code == 200
    assert run.json()["agent_id"] == agent_id
    assert run.json()["agent_version_id"] == version_id

    task = client.get(
        f"/v1/tasks/{task_body['task_id']}",
        headers=auth_headers(key),
    )
    assert task.status_code == 200
    assert task.json()["run_id"] == task_body["run_id"]

    events = client.get(
        f"/v1/runs/{task_body['run_id']}/events",
        headers=auth_headers(key),
    )
    assert events.status_code == 200
    assert [event["type"] for event in events.json()] == ["run.created", "task.queued"]


def test_native_agent_task_creation_is_idempotent() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)

    first = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key, idempotency_key="idem_1"),
        json={"input": {"message": "hello"}},
    )
    second = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key, idempotency_key="idem_1"),
        json={"input": {"message": "hello"}},
    )
    conflict = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key, idempotency_key="idem_1"),
        json={"input": {"message": "different"}},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["run_id"] == first.json()["run_id"]
    assert second.json()["replayed"] is True
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "idempotency_key_conflict"


def test_native_cancel_updates_run_and_task() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)
    task_body = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "hello"}},
    ).json()

    cancelled = client.post(
        f"/v1/runs/{task_body['run_id']}/cancel",
        headers=auth_headers(key),
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    task = client.get(f"/v1/tasks/{task_body['task_id']}", headers=auth_headers(key))
    assert task.json()["status"] == "cancelled"
