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
]


def test_native_api_paths_are_registered_in_openapi() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in NATIVE_PATHS:
        assert path in paths


def test_unimplemented_write_api_returns_stable_error_response() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/agents/agent_1/invoke",
        headers={"X-Request-Id": "req_123", "Idempotency-Key": "idem_123"},
        json={"input": {"message": "hello"}},
    )

    assert response.status_code == 501
    assert response.json() == {
        "error_code": "not_implemented",
        "message": "This API contract is registered but not implemented yet.",
        "request_id": "req_123",
        "details": {"path": "/v1/agents/agent_1/invoke"},
    }
