import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from dimoo_run.packages.validation import validation_token

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "sdk-python"))

from dimoo_run.api.dependencies import (  # noqa: E402
    default_api_key_authenticator,
    reset_api_key_authenticator,
)
from dimoo_run.api.native.runtime import reset_native_runtime  # noqa: E402
from dimoo_run.server import create_app  # noqa: E402
from dimoorun import DimooRun, DimooRunAPIError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = (
        f"sqlite:///{tempfile.gettempdir()}/dimoorun-sdk-{uuid4().hex}.db"
    )


def test_python_sdk_preserves_platform_error_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=409,
            json={
                "error_code": "idempotency_key_conflict",
                "message": "conflict",
                "request_id": "req_123",
                "details": {"run_id": 1},
            },
        )

    client = DimooRun(
        api_key="test-key",
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(DimooRunAPIError) as exc:
        client.create_run(agent_id="support-agent", input={"message": "hello"})

    assert exc.value.error_code == "idempotency_key_conflict"
    assert exc.value.request_id == "req_123"
    assert exc.value.details == {"run_id": 1}


def test_python_sdk_generates_unique_idempotency_key_per_create_run() -> None:
    keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        keys.append(request.headers["Idempotency-Key"])
        return httpx.Response(status_code=202, json={"run_id": f"run_{len(keys)}"})

    client = DimooRun(
        api_key="test-key",
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    client.create_run(agent_id="support-agent", input={"message": "one"})
    client.create_run(agent_id="support-agent", input={"message": "two"})

    assert len(set(keys)) == 2


def test_python_sdk_allows_caller_supplied_idempotency_key() -> None:
    keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        keys.append(request.headers["Idempotency-Key"])
        return httpx.Response(status_code=202, json={"run_id": 1})

    client = DimooRun(
        api_key="test-key",
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    client.create_run(
        agent_id="support-agent",
        input={"message": "hello"},
        idempotency_key="idem_custom",
    )

    assert keys == ["idem_custom"]


def test_python_sdk_can_create_run_against_native_api() -> None:
    reset_api_key_authenticator()
    reset_native_runtime()
    app = create_app()
    test_client = TestClient(app)
    authenticator = default_api_key_authenticator()
    scopes = {"agent:read", "agent:write", "agent:invoke"}
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="sdk",
        permissions=scopes,
        created_by="admin_1",
    )
    api_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="sdk-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=scopes,
        created_by="admin_1",
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": "req_sdk_setup",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
    }
    agent = test_client.post("/v1/agents", headers=headers, json={"name": "support-agent"}).json()
    test_client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers=headers,
        json={
            "version": "0.1.0",
            "package_uri": "file:///opt/dimoorun/agents/support-agent",
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
                    package_uri="file:///opt/dimoorun/agents/support-agent",
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

    def handler(request: httpx.Request) -> httpx.Response:
        response = test_client.request(
            request.method,
            str(request.url).replace("https://api.example.test", ""),
            headers=dict(request.headers)
            | {
                "X-Tenant-Id": "1",
                "X-Project-Id": "1",
                "X-Request-Id": "req_sdk",
            },
            content=request.content,
        )
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )

    client = DimooRun(
        api_key=api_key,
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    payload = client.create_run(agent_id=agent["id"], input={"message": "hello"})

    assert isinstance(payload["run_id"], int)
    assert payload["run_id"] > 0
    assert isinstance(payload["task_id"], int)
    assert payload["task_id"] > 0
    assert payload["status"] == "queued"


def test_python_sdk_sends_scope_headers_and_exposes_extended_native_api_surface() -> None:
    requests: list[tuple[str, str, dict[str, Any], dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        requests.append((request.method, request.url.path, body, dict(request.headers)))
        if request.url.path == "/v1/runs/41/events":
            return httpx.Response(status_code=200, json=[{"sequence": 1, "type": "run.started"}])
        return httpx.Response(status_code=200, json={"id": 41, "status": "queued"})

    client = DimooRun(
        api_key="test-key",
        base_url="https://api.example.test",
        tenant_id=7,
        project_id=9,
        environment="prod",
        actor_id="svc_release",
        transport=httpx.MockTransport(handler),
    )

    client.validate_package(
        package_uri="oci://registry.example/support",
        framework="langgraph",
        adapter="langgraph",
        entrypoint="agent:create_agent",
        manifest={"runtime": {"entrypoint": "agent:create_agent"}},
        required_secret_refs=["secret://model"],
    )
    client.create_agent(name="support-agent", description="prod")
    client.create_agent_version(
        agent_id=11,
        version="1.0.0",
        package_uri="oci://registry.example/support",
        framework="langgraph",
        adapter="langgraph",
        entrypoint="agent:create_agent",
        manifest={"validation_token": "tok_123"},
        capabilities={"invoke": True},
        status="ready",
    )
    client.create_deployment(
        agent_id=11,
        agent_version_id=21,
        environment="prod",
        desired_status="active",
        replicas=2,
        config={"traffic": "stable"},
    )
    client.submit_deployment_task(
        deployment_id=31,
        input={"message": "hello"},
        thread_id="thread_1",
        idempotency_key="idem_deploy",
    )
    run = client.get_run(41)
    events = client.list_run_events(41)
    replay = client.replay_run(41, agent_version_id=22)
    task = client.get_task(51)
    client.close()

    assert run["id"] == 41
    assert events == [{"sequence": 1, "type": "run.started"}]
    assert replay["status"] == "queued"
    assert task["id"] == 41
    assert [item[1] for item in requests] == [
        "/v1/packages/validate",
        "/v1/agents",
        "/v1/agents/11/versions",
        "/v1/deployments",
        "/v1/deployments/31/tasks",
        "/v1/runs/41",
        "/v1/runs/41/events",
        "/v1/runs/41/replay",
        "/v1/tasks/51",
    ]
    for _, _, _, headers in requests:
        assert headers["x-tenant-id"] == "7"
        assert headers["x-project-id"] == "9"
        assert headers["x-environment"] == "prod"
        assert headers["x-actor-id"] == "svc_release"
        assert headers["x-request-id"].startswith("req_sdk_")
    assert requests[4][3]["idempotency-key"] == "idem_deploy"


def test_python_sdk_can_drive_validate_publish_deploy_and_replay_against_native_api() -> None:
    reset_api_key_authenticator()
    reset_native_runtime()
    app = create_app()
    test_client = TestClient(app)
    authenticator = default_api_key_authenticator()
    scopes = {"agent:read", "agent:write", "agent:invoke", "agent:deploy"}
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="sdk-workflow",
        permissions=scopes,
        created_by="admin_1",
    )
    api_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="sdk-workflow-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=scopes,
        created_by="admin_1",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        response = test_client.request(
            request.method,
            str(request.url).replace("https://api.example.test", ""),
            headers=dict(request.headers),
            content=request.content,
        )
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )

    client = DimooRun(
        api_key=api_key,
        base_url="https://api.example.test",
        tenant_id=1,
        project_id=1,
        transport=httpx.MockTransport(handler),
    )

    validation = client.validate_package(
        package_uri="file:///opt/dimoorun/agents/support-agent",
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
    )
    agent = client.create_agent(name="support-agent")
    version = client.create_agent_version(
        agent_id=int(agent["id"]),
        version="1.0.0",
        package_uri="file:///opt/dimoorun/agents/support-agent",
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
            "validation_token": validation["validation_token"],
        },
        capabilities={"invoke": True},
        status="ready",
    )
    deployment = client.create_deployment(
        agent_id=int(agent["id"]),
        agent_version_id=int(version["id"]),
        environment="prod",
        desired_status="active",
        replicas=2,
    )
    run = client.submit_deployment_task(
        deployment_id=int(deployment["id"]),
        input={"message": "ship it"},
        thread_id="thread_sdk_phase11",
    )
    replay = client.replay_run(int(run["run_id"]))
    fetched_run = client.get_run(int(run["run_id"]))
    events = client.list_run_events(int(replay["id"]))

    assert validation["ready"] is True
    assert version["status"] == "ready"
    assert deployment["desired_status"] == "active"
    assert run["status"] == "queued"
    assert fetched_run["id"] == run["run_id"]
    assert replay["id"] != run["run_id"]
    assert any(event["type"] == "run.replayed" for event in events)
