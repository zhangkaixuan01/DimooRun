import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "sdk-python"))

from dimoo_run.api.dependencies import (  # noqa: E402
    default_api_key_authenticator,
    reset_api_key_authenticator,
)
from dimoo_run.api.native.runtime import reset_native_runtime  # noqa: E402
from dimoo_run.server import create_app  # noqa: E402
from dimoorun import DimooRun, DimooRunAPIError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def test_python_sdk_preserves_platform_error_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=409,
            json={
                "error_code": "idempotency_key_conflict",
                "message": "conflict",
                "request_id": "req_123",
                "details": {"run_id": "run_1"},
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
    assert exc.value.details == {"run_id": "run_1"}


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
        return httpx.Response(status_code=202, json={"run_id": "run_1"})

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
        tenant_id="tenant_1",
        project_id="project_1",
        name="sdk",
        permissions=scopes,
        created_by="admin_1",
    )
    api_key, _ = authenticator.create_key(
        tenant_id="tenant_1",
        project_id="project_1",
        name="sdk-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=scopes,
        created_by="admin_1",
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": "req_sdk_setup",
        "X-Tenant-Id": "tenant_1",
        "X-Project-Id": "project_1",
    }
    agent = test_client.post("/v1/agents", headers=headers, json={"name": "support-agent"}).json()
    test_client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers=headers,
        json={"version": "0.1.0"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        response = test_client.request(
            request.method,
            str(request.url).replace("https://api.example.test", ""),
            headers=dict(request.headers)
            | {
                "X-Tenant-Id": "tenant_1",
                "X-Project-Id": "project_1",
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

    assert payload["run_id"].startswith("run_")
    assert payload["task_id"].startswith("task_")
    assert payload["status"] == "queued"
