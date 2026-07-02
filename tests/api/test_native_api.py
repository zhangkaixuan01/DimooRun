import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.deployments import reset_deployment_control
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.core.startup_checks import StartupConfigurationError
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.packages.validation import validation_token
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
    "/v1/runs",
    "/v1/runs/{run_id}",
    "/v1/runs/{run_id}/integration-evidence",
    "/v1/runs/{run_id}/events",
    "/v1/events",
    "/v1/runs/{run_id}/attempts",
    "/v1/runs/{run_id}/cancel",
    "/v1/runs/{run_id}/resume",
    "/v1/runs/{run_id}/retry",
    "/v1/runs/{run_id}/replay",
    "/v1/replay-jobs/compare",
    "/v1/replay-jobs/{comparison_id}/dataset-captures",
    "/v1/deployments",
    "/v1/deployments/{deployment_id}",
    "/v1/deployments/{deployment_id}/activate",
    "/v1/deployments/{deployment_id}/pause",
    "/v1/deployments/{deployment_id}/resume",
    "/v1/deployments/{deployment_id}/drain",
    "/v1/deployments/{deployment_id}/stop",
    "/v1/deployments/{deployment_id}/restart",
    "/v1/deployments/{deployment_id}/tasks",
    "/v1/deployments/{deployment_id}/instances",
    "/v1/tasks",
    "/v1/tasks/{task_id}",
    "/v1/tasks/{task_id}/cancel",
]


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-native-{uuid4().hex}.db"
    os.environ["DIMOORUN_NATIVE_RUNTIME_STORE"] = "memory"
    reset_api_key_authenticator()
    reset_deployment_control()
    reset_native_runtime()


def create_api_key(*, scopes: set[str] | None = None) -> tuple[str, ServiceAccountRecord]:
    requested_scopes = scopes or {"agent:read", "agent:write", "agent:invoke"}
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="native",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
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
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def validated_manifest(
    *,
    package_uri: str = "file://support-agent",
    framework: str = "langgraph",
    adapter: str = "langgraph",
    entrypoint: str = "agent:create_agent",
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "runtime": {
            "framework": framework,
            "adapter": adapter,
            "entrypoint": entrypoint,
        }
    }
    manifest["validation_token"] = validation_token(
        package_uri=package_uri,
        framework=framework,
        adapter=adapter,
        entrypoint=entrypoint,
        manifest=manifest,
    )
    return manifest


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
            "manifest": validated_manifest(),
            "status": "ready",
        },
    )
    assert version.status_code == 201
    return agent_id, version.json()["id"]


def test_native_api_paths_are_registered_in_openapi() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in NATIVE_PATHS:
        assert path in paths


def test_dev_api_key_can_authenticate_in_dev_mode(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "dev")
    monkeypatch.setenv("DIMOORUN_DEV_API_KEY", "dev-local-key")
    client = TestClient(create_app())

    response = client.get(
        "/v1/agents",
        headers={
            "Authorization": "Bearer dev-local-key",
            "X-Request-Id": "req_dev_key",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
        },
    )

    assert response.status_code == 200


def test_dev_api_key_is_rejected_outside_dev_mode(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "production")
    monkeypatch.setenv("DIMOORUN_DEV_API_KEY", "dev-local-key")
    with pytest.raises(StartupConfigurationError) as exc_info:
        create_app()

    assert "Production mode cannot expose DIMOORUN_DEV_API_KEY." in str(exc_info.value)


def test_native_agent_read_is_logical_and_version_read_owns_runtime_fields() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(key),
        json={"name": "logical-agent", "description": "shared identity"},
    )
    assert agent.status_code == 201
    agent_body = agent.json()

    assert agent_body["name"] == "logical-agent"
    assert agent_body["description"] == "shared identity"
    assert agent_body["status"] == "active"
    assert "framework" not in agent_body
    assert "adapter" not in agent_body
    assert "version" not in agent_body
    assert "capabilities" not in agent_body

    missing_runtime_fields = client.post(
        f"/v1/agents/{agent_body['id']}/versions",
        headers=auth_headers(key),
        json={"version": "0.1.0", "package_uri": "file://agent"},
    )
    assert missing_runtime_fields.status_code == 422

    version = client.post(
        f"/v1/agents/{agent_body['id']}/versions",
        headers=auth_headers(key),
        json={
            "version": "0.1.0",
            "package_uri": "file://agent",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "capabilities": {"invoke": True},
        },
    )
    assert version.status_code == 201
    version_body = version.json()
    assert version_body["agent_id"] == agent_body["id"]
    assert version_body["framework"] == "langgraph"
    assert version_body["adapter"] == "langgraph"
    assert version_body["version"] == "0.1.0"
    assert version_body["capabilities"] == {"invoke": True}


def test_native_agent_version_can_be_updated_and_archived() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)

    updated = client.patch(
        f"/v1/agents/{agent_id}/versions/0.1.0",
        headers=auth_headers(key),
        json={
            "version": "0.1.1",
            "package_uri": "file://support-agent-v011",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_v011",
            "capabilities": {"invoke": True, "stream": True},
            "manifest": validated_manifest(
                package_uri="file://support-agent-v011",
                entrypoint="agent:create_v011",
            ),
            "status": "ready",
        },
    )

    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["version"] == "0.1.1"
    assert updated_body["package_uri"] == "file://support-agent-v011"
    assert updated_body["adapter"] == "langgraph"
    assert updated_body["entrypoint"] == "agent:create_v011"
    assert updated_body["capabilities"] == {"invoke": True, "stream": True}
    assert updated_body["manifest"]["runtime"] == {
        "framework": "langgraph",
        "adapter": "langgraph",
        "entrypoint": "agent:create_v011",
    }
    assert updated_body["manifest"]["validation_token"].startswith("pkgval_")

    archived = client.delete(
        f"/v1/agents/{agent_id}/versions/0.1.1",
        headers=auth_headers(key),
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    versions = client.get(f"/v1/agents/{agent_id}/versions", headers=auth_headers(key))
    assert versions.status_code == 200
    assert all(item["version"] != "0.1.1" for item in versions.json())


def test_native_agent_version_rejects_unsupported_framework_adapter() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(key),
        json={"name": "validated-agent"},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]

    unsupported = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "0.1.0",
            "package_uri": "file://agent",
            "framework": "custom",
            "adapter": "custom",
            "entrypoint": "agent:create_agent",
        },
    )
    assert unsupported.status_code == 400
    assert unsupported.json()["error_code"] == "unsupported_agent_runtime"

    mismatched = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "0.1.0",
            "package_uri": "file://agent",
            "framework": "langgraph",
            "adapter": "deepagents",
            "entrypoint": "agent:create_agent",
        },
    )
    assert mismatched.status_code == 400
    assert mismatched.json()["error_code"] == "unsupported_agent_runtime"


def test_native_agent_status_blocks_new_tasks_and_deployments() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read", "agent:write", "agent:deploy", "agent:invoke"})
    agent_id, version_id = create_agent_with_version(client, key)

    disabled = client.patch(
        f"/v1/agents/{agent_id}",
        headers=auth_headers(key),
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    direct_task = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "blocked"}},
    )
    assert direct_task.status_code == 409
    assert direct_task.json()["error_code"] == "agent_not_active"

    deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "production",
            "desired_status": "active",
        },
    )
    assert deployment.status_code == 409
    assert deployment.json()["error_code"] == "agent_not_active"

    enabled = client.patch(
        f"/v1/agents/{agent_id}",
        headers=auth_headers(key),
        json={"status": "active"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"

    direct_task_after_enable = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "allowed"}},
    )
    assert direct_task_after_enable.status_code == 202


def test_native_agent_version_status_blocks_new_tasks_and_deployments() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read", "agent:write", "agent:deploy", "agent:invoke"})
    agent_id, version_id = create_agent_with_version(client, key)

    disabled = client.patch(
        f"/v1/agents/{agent_id}/versions/0.1.0",
        headers=auth_headers(key),
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    direct_task = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "blocked"}, "version": "0.1.0"},
    )
    assert direct_task.status_code == 409
    assert direct_task.json()["error_code"] == "agent_version_not_ready"

    deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "production",
            "desired_status": "active",
        },
    )
    assert deployment.status_code == 409
    assert deployment.json()["error_code"] == "agent_version_not_ready"

    ready = client.patch(
        f"/v1/agents/{agent_id}/versions/0.1.0",
        headers=auth_headers(key),
        json={"status": "ready"},
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    direct_task_after_ready = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "allowed"}, "version": "0.1.0"},
    )
    assert direct_task_after_ready.status_code == 202


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
    assert isinstance(task_body["run_id"], int)
    assert isinstance(task_body["task_id"], int)
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

    global_events = client.get("/v1/events", headers=auth_headers(key))
    assert global_events.status_code == 200
    assert [event["type"] for event in global_events.json()] == ["run.created", "task.queued"]
    assert all(event["run_id"] == task_body["run_id"] for event in global_events.json())

    runs = client.get("/v1/runs", headers=auth_headers(key))
    assert runs.status_code == 200
    assert any(item["id"] == task_body["run_id"] for item in runs.json())

    tasks = client.get("/v1/tasks", headers=auth_headers(key))
    assert tasks.status_code == 200
    assert any(item["id"] == task_body["task_id"] for item in tasks.json())


def test_run_integration_evidence_is_written_through_real_api() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)
    task_body = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "integration proof"}},
    ).json()
    run_id = task_body["run_id"]

    recorded = client.post(
        f"/v1/runs/{run_id}/integration-evidence",
        headers=auth_headers(key),
        json={
            "source": "integration-proof-test",
            "trace_links": [
                {
                    "provider": "langfuse",
                    "url": "http://localhost:3000/project/demo/traces/trace_1001",
                    "trace_id": "trace_1001",
                    "label": "Langfuse trace",
                }
            ],
            "exporters": [
                {
                    "provider": "opentelemetry",
                    "exporter_type": "otlp",
                    "target_ref": "http://otel.local:4318",
                    "status": "delivered",
                    "request_id": "otel_req_1001",
                }
            ],
            "model_gateway": {
                "provider": "litellm",
                "gateway_name": "local-litellm",
                "gateway_request_id": "gw_req_1001",
                "model": "gpt-4.1-mini",
                "route": "support-policy",
                "prompt_tokens": 120,
                "completion_tokens": 40,
                "total_tokens": 160,
                "cost": 0.0042,
                "currency": "USD",
            },
            "failures": [
                {
                    "provider": "opentelemetry",
                    "error_code": "otlp_retry",
                    "message": "first export attempt retried, second delivered",
                    "retryable": True,
                }
            ],
        },
    )

    assert recorded.status_code == 200
    body = recorded.json()
    assert body["run_id"] == run_id
    assert body["trace_links"][0]["provider"] == "langfuse"
    assert body["exporters"][0]["provider"] == "opentelemetry"
    assert body["model_gateway"][0]["provider"] == "litellm"
    assert body["failures"][0]["error_code"] == "otlp_retry"

    fetched = client.get(
        f"/v1/runs/{run_id}/integration-evidence",
        headers=auth_headers(key),
    )
    assert fetched.status_code == 200
    assert fetched.json()["records"][0]["source"] == "integration-proof-test"

    events = client.get(f"/v1/runs/{run_id}/events", headers=auth_headers(key))
    assert events.status_code == 200
    assert any(event["type"] == "integration.evidence.recorded" for event in events.json())


def test_native_deployment_task_run_flow_uses_active_deployment_version() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read", "agent:write", "agent:deploy", "agent:invoke"})
    agent_id, version_id = create_agent_with_version(client, key)
    deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "production",
            "desired_status": "active",
            "replicas": 1,
        },
    )
    assert deployment.status_code == 201
    deployment_id = deployment.json()["id"]

    task_response = client.post(
        f"/v1/deployments/{deployment_id}/tasks",
        headers=auth_headers(key, idempotency_key="deployment_idem_1"),
        json={"input": {"message": "hello from deployment"}, "thread_id": "thread_1"},
    )

    assert task_response.status_code == 202
    task_body = task_response.json()
    assert task_body["status"] == "queued"
    assert task_body["replayed"] is False

    run = client.get(f"/v1/runs/{task_body['run_id']}", headers=auth_headers(key))
    assert run.status_code == 200
    run_body = run.json()
    assert run_body["agent_id"] == agent_id
    assert run_body["agent_version_id"] == version_id
    assert run_body["deployment_id"] == deployment_id
    assert run_body["thread_id"] == "thread_1"
    assert run_body["input"] == {"message": "hello from deployment"}


def test_native_deployment_task_rejects_inactive_deployment() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read", "agent:write", "agent:deploy", "agent:invoke"})
    agent_id, version_id = create_agent_with_version(client, key)
    deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "staging",
            "desired_status": "draft",
            "replicas": 1,
        },
    )
    assert deployment.status_code == 201

    response = client.post(
        f"/v1/deployments/{deployment.json()['id']}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "blocked"}},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "deployment_not_active"


def test_native_deployment_can_be_updated_and_archived() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read", "agent:write", "agent:deploy"})
    agent_id, version_id = create_agent_with_version(client, key)
    version_two = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "0.2.0",
            "package_uri": "file://support-agent-v2",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": validated_manifest(package_uri="file://support-agent-v2"),
            "status": "ready",
        },
    )
    assert version_two.status_code == 201
    deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "qa",
            "desired_status": "active",
            "replicas": 1,
        },
    )
    assert deployment.status_code == 201
    deployment_id = deployment.json()["id"]

    updated = client.patch(
        f"/v1/deployments/{deployment_id}",
        headers=auth_headers(key),
        json={
            "agent_version_id": version_two.json()["id"],
            "environment": "production",
            "replicas": 3,
            "config": {"max_concurrency": 4},
        },
    )

    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["agent_version_id"] == version_two.json()["id"]
    assert updated_body["environment"] == "production"
    assert updated_body["replicas"] == 3
    assert updated_body["config"] == {"max_concurrency": 4}

    archived = client.delete(f"/v1/deployments/{deployment_id}", headers=auth_headers(key))
    assert archived.status_code == 200
    assert archived.json()["desired_status"] == "archived"

    deployments = client.get("/v1/deployments", headers=auth_headers(key))
    assert deployments.status_code == 200
    assert all(item["id"] != deployment_id for item in deployments.json())


def test_native_run_read_exposes_persisted_lifecycle_fields() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)
    task_body = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "hello"}},
    ).json()

    run = client.get(f"/v1/runs/{task_body['run_id']}", headers=auth_headers(key))

    assert run.status_code == 200
    body = run.json()
    assert isinstance(body["created_at"], str)
    assert body["started_at"] is None
    assert body["finished_at"] is None
    assert body["latency_ms"] is None


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


def test_native_deployment_task_creation_is_idempotent() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read", "agent:write", "agent:deploy", "agent:invoke"})
    agent_id, version_id = create_agent_with_version(client, key)
    deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "production",
            "desired_status": "active",
            "replicas": 1,
        },
    ).json()

    first = client.post(
        f"/v1/deployments/{deployment['id']}/tasks",
        headers=auth_headers(key, idempotency_key="deployment_idem_1"),
        json={"input": {"message": "hello from deployment"}},
    )
    second = client.post(
        f"/v1/deployments/{deployment['id']}/tasks",
        headers=auth_headers(key, idempotency_key="deployment_idem_1"),
        json={"input": {"message": "hello from deployment"}},
    )
    conflict = client.post(
        f"/v1/deployments/{deployment['id']}/tasks",
        headers=auth_headers(key, idempotency_key="deployment_idem_1"),
        json={"input": {"message": "different deployment payload"}},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["run_id"] == first.json()["run_id"]
    assert second.json()["task_id"] == first.json()["task_id"]
    assert second.json()["replayed"] is True
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "idempotency_key_conflict"


def test_sqlalchemy_native_agent_task_idempotency_survives_runtime_restart(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'native-idempotency.db'}"
    os.environ["DATABASE_URL"] = database_url
    os.environ["DIMOORUN_NATIVE_RUNTIME_STORE"] = "sqlalchemy"
    reset_api_key_authenticator()
    reset_native_runtime()
    first_client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(first_client, key)

    first = first_client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key, idempotency_key="sql_idem_1"),
        json={"input": {"message": "hello durable"}},
    )

    reset_native_runtime()
    second_client = TestClient(create_app())
    second = second_client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key, idempotency_key="sql_idem_1"),
        json={"input": {"message": "hello durable"}},
    )
    conflict = second_client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key, idempotency_key="sql_idem_1"),
        json={"input": {"message": "hello durable but changed"}},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["run_id"] == first.json()["run_id"]
    assert second.json()["task_id"] == first.json()["task_id"]
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


def test_native_replay_creates_new_run_and_task_from_source() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)
    source = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "replay me"}},
    ).json()

    replay = client.post(
        f"/v1/runs/{source['run_id']}/replay",
        headers=auth_headers(key),
    )

    assert replay.status_code == 200
    replay_body = replay.json()
    assert replay_body["id"] != source["run_id"]
    assert replay_body["input"] == {"message": "replay me"}
    assert replay_body["status"] == "pending"

    tasks = client.get("/v1/tasks", headers=auth_headers(key))
    assert tasks.status_code == 200
    assert any(item["run_id"] == replay_body["id"] for item in tasks.json())

    events = client.get(f"/v1/runs/{replay_body['id']}/events", headers=auth_headers(key))
    assert events.status_code == 200
    assert any(event["type"] == "run.replayed" for event in events.json())


def test_native_replay_can_target_candidate_version() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, source_version_id = create_agent_with_version(client, key)
    source = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "replay me"}},
    ).json()
    candidate = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "0.2.0",
            "package_uri": "file://support-agent-v2",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
        },
    )
    assert candidate.status_code == 201

    replay = client.post(
        f"/v1/runs/{source['run_id']}/replay",
        headers=auth_headers(key),
        json={"agent_version_id": candidate.json()["id"]},
    )

    assert replay.status_code == 200
    assert replay.json()["agent_version_id"] != source_version_id
    assert replay.json()["agent_version_id"] == candidate.json()["id"]


def test_native_replay_rejects_unknown_candidate_version() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)
    source = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "replay me"}},
    ).json()

    replay = client.post(
        f"/v1/runs/{source['run_id']}/replay",
        headers=auth_headers(key),
        json={"agent_version_id": 999_999},
    )

    assert replay.status_code == 404
    assert replay.json()["error_code"] == "agent_version_not_found"


def test_native_run_attempts_endpoint_returns_persisted_attempts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DIMOORUN_NATIVE_RUNTIME_STORE", "sqlalchemy")
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _ = create_agent_with_version(client, key)
    task_body = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "hello"}},
    ).json()

    from dimoo_run.api.native.dependencies import _session_factory
    from dimoo_run.core.config import Settings
    from dimoo_run.domain.models import RunAttempt

    session_factory = _session_factory(Settings.from_env().database.url)
    session = session_factory()
    try:
        attempt = RunAttempt(
            run_id=task_body["run_id"],
            task_id=task_body["task_id"],
            attempt_no=1,
            worker_id="worker_1",
            status="succeeded",
        )
        session.add(attempt)
        session.commit()
        attempt_id = attempt.id
    finally:
        session.close()

    response = client.get(
        f"/v1/runs/{task_body['run_id']}/attempts",
        headers=auth_headers(key),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": attempt_id,
            "run_id": task_body["run_id"],
            "task_id": task_body["task_id"],
            "attempt_no": 1,
            "worker_id": "worker_1",
            "status": "succeeded",
            "error": None,
        }
    ]


def test_native_task_can_be_executed_by_worker_entrypoint(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database_url = f"sqlite:///{tmp_path / 'native-worker.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DIMOORUN_NATIVE_RUNTIME_STORE", "sqlalchemy")
    agent_package = tmp_path / "agent_package"
    agent_package.mkdir()
    (agent_package / "agent.py").write_text(
        "\n".join(
            [
                "class EchoAgent:",
                "    def invoke(self, input_data, config):",
                "        run_id = config['configurable']['run_id']",
                "        return {'echo': input_data['message'], 'run_id': run_id}",
                "",
                "def create_agent(config):",
                "    return EchoAgent()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(key),
        json={"name": "worker-agent"},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]
    version = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "0.1.0",
            "package_uri": str(agent_package),
            "adapter": "langgraph",
            "framework": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": validated_manifest(package_uri=str(agent_package)),
            "status": "ready",
        },
    )
    assert version.status_code == 201
    task = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "hello"}},
    )
    assert task.status_code == 202
    task_body = task.json()

    import sys

    project_root = Path(__file__).resolve().parents[2]
    root = str(project_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    from apps.worker.dimoo_run_worker import main

    assert main.run_once() == "executed"

    run = client.get(f"/v1/runs/{task_body['run_id']}", headers=auth_headers(key))
    assert run.status_code == 200
    assert run.json()["status"] == "succeeded"
    assert run.json()["output"] == {"echo": "hello", "run_id": task_body["run_id"]}

    events = client.get(f"/v1/runs/{task_body['run_id']}/events", headers=auth_headers(key))
    assert events.status_code == 200
    assert [event["type"] for event in events.json()] == [
        "run.created",
        "task.queued",
        "attempt.started",
        "run.completed",
        "stream.completed",
    ]

    attempts = client.get(
        f"/v1/runs/{task_body['run_id']}/attempts",
        headers=auth_headers(key),
    )
    assert attempts.status_code == 200
    assert attempts.json()[0]["status"] == "succeeded"
