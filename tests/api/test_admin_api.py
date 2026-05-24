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
    "/v1/schedules",
    "/v1/batch-runs",
    "/v1/notifications/channels",
    "/v1/alerts/rules",
    "/v1/backups/plans",
]


def test_admin_api_paths_are_registered_in_openapi() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in ADMIN_PATHS:
        assert path in paths


def test_high_risk_admin_action_marks_audit_required() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/human-tasks/task_1/approve",
        headers={"X-Request-Id": "req_approve"},
        json={"decision_payload": {"approved": True}},
    )

    assert response.status_code == 501
    assert response.json()["details"]["audit_required"] is True


def test_unimplemented_admin_read_api_returns_stable_error_response() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/policies", headers={"X-Request-Id": "req_admin_read"})

    assert response.status_code == 501
    assert response.json() == {
        "error_code": "not_implemented",
        "message": "This API contract is registered but not implemented yet.",
        "request_id": "req_admin_read",
        "details": {"path": "/v1/policies"},
    }
