import json
import subprocess
import sys
from pathlib import Path

from dimoo_run.server import create_app


def test_openapi_schema_contains_error_response_and_runtime_control_paths() -> None:
    schema = create_app().openapi()

    assert "ErrorResponse" in schema["components"]["schemas"]
    assert "/v1/deployments/{deployment_id}/activate" in schema["paths"]
    assert "/v1/deployments/{deployment_id}/instances" in schema["paths"]
    assert "/v1/human-tasks/{task_id}/approve" in schema["paths"]


def test_unimplemented_get_routes_document_501_response() -> None:
    schema = create_app().openapi()
    get_paths = [
        "/v1/agents",
        "/v1/agents/{agent_id}",
        "/v1/agents/{agent_id}/versions",
        "/v1/agents/{agent_id}/versions/{version}",
        "/v1/runs/{run_id}",
        "/v1/runs/{run_id}/events",
        "/v1/runs/{run_id}/attempts",
        "/v1/tasks/{task_id}",
        "/v1/policies",
        "/v1/artifacts/{artifact_id}",
        "/v1/human-tasks",
        "/v1/catalog/items",
    ]

    for path in get_paths:
        operation = schema["paths"][path]["get"]
        assert "501" in operation["responses"], path


def test_implemented_deployment_routes_do_not_document_501_response() -> None:
    schema = create_app().openapi()
    paths = [
        ("/v1/deployments", "get"),
        ("/v1/deployments/{deployment_id}", "get"),
        ("/v1/deployments/{deployment_id}/instances", "get"),
        ("/v1/deployments/{deployment_id}/activate", "post"),
        ("/v1/deployments/{deployment_id}/pause", "post"),
        ("/v1/deployments/{deployment_id}/resume", "post"),
        ("/v1/deployments/{deployment_id}/drain", "post"),
        ("/v1/deployments/{deployment_id}/stop", "post"),
        ("/v1/deployments/{deployment_id}/restart", "post"),
    ]

    for path, method in paths:
        assert "501" not in schema["paths"][path][method]["responses"], path


def test_deployment_routes_document_request_scope_headers() -> None:
    schema = create_app().openapi()
    operations = [
        schema["paths"]["/v1/deployments"]["get"],
        schema["paths"]["/v1/deployments/{deployment_id}"]["get"],
        schema["paths"]["/v1/deployments/{deployment_id}/instances"]["get"],
        schema["paths"]["/v1/deployments/{deployment_id}/activate"]["post"],
        schema["paths"]["/v1/deployments/{deployment_id}/pause"]["post"],
        schema["paths"]["/v1/deployments/{deployment_id}/resume"]["post"],
        schema["paths"]["/v1/deployments/{deployment_id}/drain"]["post"],
        schema["paths"]["/v1/deployments/{deployment_id}/stop"]["post"],
        schema["paths"]["/v1/deployments/{deployment_id}/restart"]["post"],
    ]

    for operation in operations:
        parameter_names = {parameter["name"] for parameter in operation["parameters"]}
        assert {"X-Tenant-Id", "X-Project-Id"} <= parameter_names
        assert "400" in operation["responses"]


def test_export_openapi_script_writes_contract_file() -> None:
    output_path = Path("openapi/dimoorun.openapi.json")
    if output_path.exists():
        output_path.unlink()

    result = subprocess.run(
        [sys.executable, "scripts/export_openapi.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    schema = json.loads(output_path.read_text(encoding="utf-8"))
    assert schema["info"]["title"] == "DimooRun API"
    assert "/v1/agents/{agent_id}/invoke" in schema["paths"]


def test_export_openapi_script_can_write_to_explicit_output(tmp_path) -> None:  # type: ignore[no-untyped-def]
    output_path = tmp_path / "dimoorun.openapi.json"

    result = subprocess.run(
        [sys.executable, "scripts/export_openapi.py", "--output", str(output_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    schema = json.loads(output_path.read_text(encoding="utf-8"))
    assert schema["info"]["title"] == "DimooRun API"
